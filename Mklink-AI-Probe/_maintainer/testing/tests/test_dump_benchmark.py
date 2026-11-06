from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from mklink.dump_benchmark import measure


def run_frames(monkeypatch,frames,size):
    session=Mock()
    session.read_frames.return_value=frames
    session.stats={'parser_crc_errors':0,'parser_dropped_frames':0,'firmware_flagged_frames':0}
    monkeypatch.setattr('mklink.dump_memory.DumpMemoryStreamSession',lambda *a,**k:session)
    ticks=iter([0,.1,.1,3])
    monkeypatch.setattr('mklink.dump_benchmark.time.monotonic',lambda:next(ticks))
    dev=SimpleNamespace(_require_connected=Mock(),set_debug_speed=Mock(),
        _bridge=SimpleNamespace(_ctx=SimpleNamespace(swd_clock_hz=20000000)))
    return dev,session


def test_current_single_frames_keep_device_time_and_sample_count(monkeypatch):
    frames = [{'format':'mux','flags':0,'timestamp_us':t,'regions':[(0,b'x'*128)]}
              for t in (0,100000,200000,300000,400000)]
    dev, session = run_frames(monkeypatch, frames, 128)
    result = measure(dev, [(0x90000,128)], duration=1)
    assert result['samples'] == 3 and result['sample_hz'] == 10
    assert result['payload_bytes_per_second'] == 1280
    session.stop.assert_called_once()


def test_oversized_continuous_sample_rejected_before_io():
    dev = Mock()
    with pytest.raises(ValueError, match='4096 bytes'):
        measure(dev, [(0x90000,4097)], duration=1)
    dev._require_connected.assert_not_called()


def test_packed_measurement_preserves_cross_batch_timestamp_gaps(monkeypatch):
    from mklink.mux_watch import PackedWatchSample
    frames = [PackedWatchSample(t, b'abcd', 0) for t in (0, 200000, 200004, 208417)]
    dev, session = run_frames(monkeypatch, frames, 4)
    result = measure(dev, [(0x20000000, 4)], duration=1)
    assert session.packed_frames is True
    assert result['samples'] == 3
    assert result['max_interval_us'] == 8413
    assert result['incomplete_tail'] is False
    session.stop.assert_called_once()


def test_queue_byte_loss_cannot_return_success(monkeypatch):
    from mklink.mux_watch import PackedWatchSample
    dev, session = run_frames(monkeypatch,
        [PackedWatchSample(t, b'abcd', 0) for t in (0, 200000, 210000)], 4)
    session.stats['parser_dropped_bytes'] = 1024
    with pytest.raises(RuntimeError, match='max_interval_us=10000'):
        measure(dev, [(0x20000000, 4)], duration=1)
    session.stop.assert_called_once()


@pytest.mark.parametrize('kwargs',[{'duration':31},{'duration':float('nan')},{'period':0},{'period':float('inf')}])
def test_invalid_measurement_never_touches_device(kwargs):
    dev=Mock()
    with pytest.raises(ValueError):measure(dev,[(0x90000,4)],**kwargs)
    dev._require_connected.assert_not_called()
    dev.set_debug_speed.assert_not_called()


@pytest.mark.parametrize('before_start', [False, True])
def test_measurement_cooperative_cancel_confirms_stop(monkeypatch, before_start):
    dev, session = run_frames(monkeypatch, [], 4)
    checks = iter([before_start, True])
    with pytest.raises(InterruptedError, match='cancelled'):
        measure(dev, [(0x90000,4)], duration=1, cancelled=lambda: next(checks))
    if before_start:
        session.start.assert_not_called()
        session.stop.assert_not_called()
        dev._require_connected.assert_not_called()
    else:
        session.stop.assert_called_once()
