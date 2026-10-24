from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from mklink import dap_recovery as recovery


IDENTITY = (0x0d28, 0x0202, 'probe-a')


class Api:
    def __init__(self, rows=None, answer=b'\x01\x00', busy=False):
        self.rows = [('selected', IDENTITY)] if rows is None else rows
        self.answer, self.busy = answer, busy
        self.events = []
        self.held = False

    def interfaces(self):
        return iter(self.rows)

    @contextmanager
    def exclusive(self, path):
        self.events.append(('exclusive', path))
        if self.busy:
            raise OSError('owned by idle or paused IDE')
        self.held = True
        try:
            yield self
        finally:
            self.held = False
            self.events.append('close')

    def drain(self):
        assert self.held
        self.events.append('drain')

    def write(self, packet):
        assert self.held
        self.events.append(('write', packet))

    def read(self):
        assert self.held
        self.events.append('read')
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def test_identity_bound_cleanup_holds_exclusivity_through_ack():
    api = Api([('other', (0x0d28, 0x0202, 'other')), ('selected', IDENTITY)])
    assert recovery._reconcile(IDENTITY, api) == 'reconciled'
    assert api.events == [('exclusive', 'selected'), 'drain',
                          ('write', b'\x01\x00\x00'), 'read', 'close']


@pytest.mark.parametrize('rows', [[], [('wrong', (1, 2, 'probe-a'))],
                                  [('one', IDENTITY), ('two', IDENTITY)]])
def test_missing_wrong_or_duplicate_identity_never_opens(rows):
    api = Api(rows)
    assert recovery._reconcile(IDENTITY, api) == 'unverified'
    assert not api.events


def test_live_debugger_including_idle_or_paused_is_never_touched():
    api = Api(busy=True)
    with pytest.raises(OSError):
        recovery._reconcile(IDENTITY, api)
    assert api.events == [('exclusive', 'selected')]


@pytest.mark.parametrize('answer', [b'', b'\x01', b'\x01\xff', b'\x03\x00',
                                     b'\x01\x00\x05', OSError('timeout')])
def test_unconfirmed_ack_closes_and_never_replays(answer):
    api = Api(answer=answer)
    with pytest.raises((OSError, RuntimeError)):
        recovery._reconcile(IDENTITY, api)
    assert api.events.count(('write', b'\x01\x00\x00')) == 1
    assert api.events[-1] == 'close' and not api.held


@pytest.mark.parametrize('platform', ['linux', 'darwin'])
def test_other_platforms_keep_existing_path(monkeypatch, platform):
    monkeypatch.setattr(recovery.sys, 'platform', platform)
    factory = Mock(side_effect=AssertionError('must not enumerate'))
    monkeypatch.setattr(recovery, '_WindowsDap', factory)
    assert recovery.reconcile_dap_owner('COM1') == 'unsupported'
    factory.assert_not_called()


def test_failure_preserves_firmware_arbitration(monkeypatch):
    monkeypatch.setattr(recovery.sys, 'platform', 'win32')
    monkeypatch.setattr(recovery, '_port_identity', lambda _: IDENTITY)
    monkeypatch.setattr(recovery, '_WindowsDap', lambda: Api(busy=True))
    assert recovery.reconcile_dap_owner('COM1').startswith('unavailable:')


def port(**changes):
    fields = dict(device='COM1', vid=0x0d28, pid=0x0202, serial_number='Probe-A',
                  hwid=r'USB\VID_0D28&PID_0202&MI_04\node', location='')
    fields.update(changes)
    return SimpleNamespace(**fields)


@pytest.mark.parametrize('ports', [[], [port(), port()], [port(vid=1)],
    [port(serial_number=None)], [port(hwid='')],
    [port(hwid=r'USB\VID_0D28&PID_0202&MI_02\node')]])
def test_unverified_command_port_does_not_select_dap(monkeypatch, ports):
    from serial.tools import list_ports
    monkeypatch.setattr(list_ports, 'comports', lambda: ports)
    assert recovery._port_identity('COM1') is None


def test_normalized_port_and_serial(monkeypatch):
    from serial.tools import list_ports
    monkeypatch.setattr(list_ports, 'comports', lambda: [port(), port(device='COM2')])
    assert recovery._port_identity(r'\\.\com01') == IDENTITY


def test_channel_uses_zero_share_mode_and_fails_before_usb_commands(monkeypatch):
    monkeypatch.setattr(recovery.c, 'WinError', lambda _: OSError('initialization failed'), raising=False)
    monkeypatch.setattr(recovery.c, 'get_last_error', lambda: 5, raising=False)
    api = SimpleNamespace(os=SimpleNamespace(open=Mock(return_value=101), invalid=-1,
                          close=Mock()), initialize=Mock(return_value=False), free=Mock())
    channel = recovery._Channel(api, 'identity-bound-path')
    with pytest.raises(OSError):
        channel.__enter__()
    api.os.open.assert_called_once_with('identity-bound-path', 0xc0000000, 0,
                                       None, 3, 0x40000000, None)
    api.os.close.assert_called_once_with(101)
    api.free.assert_not_called()


def test_drain_is_bounded_and_does_not_write():
    channel = recovery._Channel(None, '')
    channel.in_ep = 0x81
    channel.timeout = Mock()
    channel.read = Mock(return_value=b'old')
    channel.write = Mock()
    with pytest.raises(RuntimeError, match='did not drain'):
        channel.drain()
    assert channel.read.call_count == 32
    channel.write.assert_not_called()
    assert channel.timeout.call_args.args == (0x81, 200)


def test_drain_transport_failure_is_not_empty_queue():
    channel = recovery._Channel(None, '')
    channel.in_ep = 0x81
    channel.timeout = Mock()
    error = OSError('device removed'); error.winerror = 1167
    channel.read = Mock(side_effect=error)
    with pytest.raises(OSError):
        channel.drain()
    assert channel.timeout.call_args.args == (0x81, 200)
