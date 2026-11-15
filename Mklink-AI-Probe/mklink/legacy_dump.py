"""Explicit DMPM compatibility capture through the existing bridge owner.

Never selected as a MUX fallback. Live writes and shared RTT stay on MUX.
"""
import math

from mklink._types import DeviceState
from mklink.dump_memory import (DumpMemoryParser, DumpMemoryBusyError,
                                DumpMemoryUnsupported, validate_dump_regions)


def command_for(regions, period):
    validate_dump_regions(regions)
    if type(period) not in (int, float) or not math.isfinite(period) or period < -1:
        raise ValueError('DMPM period must be -1, 0, or positive and finite')
    if -1 < period < 0 or 0 < period < .000001:
        raise ValueError('DMPM positive period must be at least 1 us')
    args = [value for address, size in regions for value in (f'0x{address:08X}', str(size))]
    # Pika's arg_getFloat reads the stored bits; a positive integer token is
    # not converted to float. Keep the decimal point even for whole seconds.
    period_text = f'{period:.6f}'.rstrip('0')
    args.append(period_text + '0' if period_text.endswith('.') else period_text)
    command = 'cmd.dump_memory(' + ', '.join(args) + ')'
    if len(command.encode('ascii')) > 511:
        raise ValueError('DMPM command exceeds the 511-byte console limit')
    return command


class LegacyDumpSession:
    """Read-only, bounded OLD/B1 capture with a verified single stop."""

    def __init__(self, bridge, regions, period):
        self.bridge, self.regions, self.period = bridge, regions, period
        self.command = command_for(regions, period)
        self.parser = DumpMemoryParser([size for _, size in regions], startup_command=self.command)
        self.started = False
        self.protocol_frames = self.complete_samples = self.flagged = self.drops = 0

    def start(self):
        bridge = self.bridge
        with bridge._cmd_lock:
            if bridge.state is not DeviceState.READY or getattr(getattr(bridge, '_mux', None), 'sampling', False):
                raise DumpMemoryBusyError('DMPM requires an idle connection; existing streams were not stopped')
            capabilities = bridge._get_firmware_capabilities()
            if not {'DUMP_MEMORY=1', 'DUMP_STOP=1'} <= capabilities:
                raise DumpMemoryUnsupported('Explicit DMPM capture requires firmware advertising DUMP_MEMORY=1 and DUMP_STOP=1; 请升级匹配的下载器固件 / upgrade the matching probe firmware')
            bridge._leave_multiplex()
            if not bridge._try_enter_stream(DeviceState.DUMP_STREAM):
                raise DumpMemoryBusyError('DMPM requires an idle READY bridge')
            self.started = True  # Even an uncertain START must be stopped, never replayed.
            bridge._write_raw((self.command + '\n').encode('ascii'))

    @property
    def timing(self):
        return {'protocol': 'dmpm', 'mode': 'single' if self.period == 0 else 'periodic',
                'requested_period_us': round(self.period * 1000000),
                'accepted_period_us': None, 'timebase_hz': None}

    def read_frames(self, max_bytes=None):
        if not self.started:
            raise RuntimeError('DMPM stream is not started')
        raw = self.bridge.drain_stream_bytes(max_bytes=max_bytes)
        frames = self.parser.feed(raw) if raw else []
        for frame in frames:
            if frame.get('format') == 'WRITE_ACK':
                raise RuntimeError('Unexpected write reply in read-only DMPM capture')
            self.protocol_frames += 1
            self.flagged += bool(frame.get('flags', 0))
            self.drops += bool(frame.get('flags', 0) & 8)
            self.complete_samples += frame.get('format') != 'B1' or frame['block_index'] + 1 == frame['block_count']
        return frames

    def stop(self):
        if not self.started:
            return
        from mklink.dump_control import stop_dump_and_sync
        try:
            with self.bridge._cmd_lock:
                if not stop_dump_and_sync(self.bridge, (command_for(self.regions, -1) + '\n').encode('ascii'),
                                          self.parser.pending_bytes):
                    raise RuntimeError(self.bridge.last_stream_stop_error or 'DMPM stop unconfirmed')
        finally:
            self.started = False

    @property
    def stats(self):
        return {'protocol_frames': self.protocol_frames, 'complete_samples': self.complete_samples,
                'parser_dropped_bytes': self.parser.dropped_bytes, 'parser_dropped_frames': self.parser.dropped_frames,
                'parser_crc_errors': self.parser.crc_errors, 'startup_control_bytes': self.parser.startup_control_bytes,
                'firmware_flagged_frames': self.flagged, 'firmware_sample_drop_flags': self.drops,
                'firmware_read_errors': 0, 'incomplete_samples': int(bool(self.parser.pending_bytes))}
