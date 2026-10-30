"""Exercise real RTT workers with discovery held behind a deterministic gate."""
import asyncio
import threading
import time
from types import SimpleNamespace

import pytest

from mklink.remote.acquisition import suspend_acquisition
from mklink.remote.dashboards import RttStreamManager
from mklink.remote.resource_manager import ResourceManager


class Target:
    connected = True

    def __init__(self):
        self.channels = [0, 1]
        self.gate = threading.Event()
        self.entered = threading.Event()
        self.reading = threading.Event()
        self.starts = 0
        self.failure = None

    def rtt_start(self, *args, **kwargs):
        self.starts += 1
        self.entered.set()
        assert self.gate.wait(2), 'test did not release RTT discovery'
        if self.failure:
            raise RuntimeError(self.failure)
        return dict(channels=list(self.channels), transport='cdc-mux',
                    control_block_addr='0x00088188')

    def rtt_read_channels(self, **kwargs):
        self.reading.set()
        time.sleep(.002)
        return {}

    def rtt_stop(self):
        pass


async def wait_until(predicate):
    for _ in range(200):
        if predicate():
            return
        await asyncio.sleep(.005)
    pytest.fail('worker did not reach expected state')


@pytest.mark.parametrize('channels', [[0, 1], [0, 2], [1]])
@pytest.mark.parametrize('paused', [False, True])
def test_download_restores_delayed_auto_channels_and_live_encoding(monkeypatch, channels, paused):
    manager, target = RttStreamManager(), Target()
    state = {'device': target, 'resource_manager': ResourceManager()}
    monkeypatch.setattr('mklink.remote.dashboards.get_managers', lambda: {'rtt': manager})
    monkeypatch.setattr('mklink.remote.api.acquire_dashboard_resources', lambda *args: [])

    async def run():
        target.gate.set()
        manager.start(target, all_channels=True)
        await wait_until(target.reading.is_set)
        manager.set_encoding('gb18030')
        manager.set_encoding('gbk', 1)
        manager._restart_after_operation = lambda: manager.start(target, all_channels=True)
        if paused:
            manager.pause()
        # Repeat to catch stale restart closures and settings lost on round two.
        for _ in range(2):
            async with suspend_acquisition(state) as report:
                assert not manager.running
                target.channels = channels
                target.gate.clear()
                target.entered.clear()
                target.reading.clear()
            assert report == dict(state='restored', paused=['rtt'], restored=['rtt'], errors=[])
            assert target.entered.wait(1) and not target.reading.is_set()
            assert manager.running and manager.paused == paused
            target.gate.set()
            await wait_until(lambda: bool(manager.get_status()['control_block_addr']))
            assert set(manager._channel_decoders) == set(channels)
            assert manager._line_assembler.encoding == 'gb18030'
            for ch in channels:
                expected = 'gbk' if ch == 1 else 'utf-8' if ch == 0 else 'gb18030'
                assert manager._channel_decoders[ch]._line_assembler.encoding == expected
            assert manager.paused == paused
            if not paused:
                await wait_until(target.reading.is_set)

    try:
        asyncio.run(run())
    finally:
        target.gate.set()
        manager.stop()


def test_rtt_start_keeps_real_target_errors_and_live_unknown_channel_rejection():
    manager, target = RttStreamManager(), Target()
    target.failure = 'RTT control block was not found in target RAM'
    target.gate.set()
    try:
        manager.start(target, all_channels=True, channel_encodings={1: 'gbk'})
        asyncio.run(wait_until(lambda: manager.get_status()['error'] is not None))
        assert manager.get_status()['error'] == target.failure
        assert not manager.running
        with pytest.raises(ValueError, match='RTT channel is not active'):
            manager.set_encoding('gbk', 7)
    finally:
        manager.stop()


def test_restart_snapshot_does_not_alias_saved_lists_or_encoding_map():
    manager = RttStreamManager()
    manager._start_options = {'channels': [0, 1], 'channel_encodings': {1: 'gbk'}}
    options = manager.restart_options()
    options['channels'].append(2)
    options['channel_encodings'][1] = 'big5'
    assert manager._start_options == {'channels': [0, 1], 'channel_encodings': {1: 'gbk'}}


def test_usb_recovery_plan_also_passes_encoding_during_start(monkeypatch):
    from mklink.runtime_recovery import TransportRecovery
    manager = RttStreamManager()
    manager._running = True
    manager._start_options = {'all_channels': True, 'channel_encodings': {1: 'gbk'}}
    manager._restart_after_operation = lambda: pytest.fail('stale start callback')
    device = SimpleNamespace(connected=True, idcode=123, clock_hz=10_000_000)
    state = {'device': device}
    control = SimpleNamespace(info={'probe_id': 'fixture'}, stopping=False,
                              target_sessions={'owner'}, state=state, prune=lambda: None)
    # TransportRecovery reads the same app state shape as the real runtime.
    control.app = SimpleNamespace(state=SimpleNamespace(mklink_state=state))
    monkeypatch.setattr('mklink.remote.dashboards.get_managers', lambda: {'rtt': manager})
    recovery = TransportRecovery(control)
    calls = []
    manager.start = lambda dev, **options: calls.append((dev, options))
    asyncio.run(recovery.tick())
    recovery.plan[0][2]()
    assert calls == [(device, {'all_channels': True, 'encoding': 'utf-8', 'channel_encodings': {1: 'gbk'}})]
