"""Read a window of shared RTT bytes with a private subscription per channel."""
import codecs
from contextlib import ExitStack
import json
import time

from mklink.remote.dashboards import RttChannelDecoder
from mklink.rtt_cache import RttChannelCache
from mklink.runtime import RuntimeErrorResponse


class ChannelWindow:
    def __init__(self, channel, cursor, session, encoding):
        self.channel = channel
        self.cursor = cursor
        self.session = session
        self.encoding = encoding
        self.pending = bytearray()
        self.byte_count = self.lost = 0
        self.emitted = 0
        self.previous_points = []
        self.reset_decoders()

    def reset_decoders(self):
        self.text_decoder = codecs.getincrementaldecoder(self.encoding)(errors='replace')
        self.wave = RttChannelDecoder()
        self.wave.set_encoding(self.encoding)

    def block(self, final=False):
        data = bytes(self.pending)
        self.pending.clear()
        return dict(channel=self.channel, session=self.session, cursor=self.cursor,
                    text=self.text_decoder.decode(data, final=final), data_hex=data.hex(),
                    lost_bytes=self.lost)

    def emit(self, final=False):
        self.emitted += len(self.pending)
        print(json.dumps({'rtt_chunk': self.block(final)}, ensure_ascii=False), flush=True)

    def consume(self, data, start, end, live):
        if start > self.cursor:
            if self.pending or self.text_decoder.getstate()[0]:
                self.emit(final=True)
            self.previous_points = self.points()
            self.reset_decoders()
            self.lost += min(start, end) - self.cursor
            self.cursor = min(start, end)
        data = data[max(0, self.cursor - start):max(0, end - start)]
        self.cursor += len(data)
        self.byte_count += len(data)
        self.pending.extend(data)
        self.wave.feed_rtt_bytes(data)
        self.wave.flush_pending()
        if self.pending and (live or len(self.pending) >= RttChannelCache.LIMIT):
            self.emit()

    def read_to(self, client, end, live):
        """Recover a gap or the final tail from the same capture's bounded cache."""
        while self.cursor < end:
            page = client.call('rtt_read_channel', dict(channel=self.channel, session=self.session,
                                                        cursor=self.cursor))
            if page['reset'] or page['session'] != self.session:
                raise RuntimeErrorResponse('RTT capture changed during this read')
            data = bytes.fromhex(page['data_hex'])
            start = page['cursor'] - len(data)
            if start < self.cursor or page['available_end'] < end or page['cursor'] <= self.cursor:
                raise RuntimeErrorResponse('RTT channel cursor did not advance within this capture')
            self.consume(data, start, end, live)

    def receive(self, client, reader, live, limit=None):
        batch = reader.read(timeout=0)
        data = batch['data']
        if not data:
            return False
        end = batch['cursor'] if limit is None else min(limit, batch['cursor'])
        if end > self.cursor:
            start = batch['cursor'] - len(data)
            if start > self.cursor:
                self.read_to(client, min(end, start), live)
            self.consume(data, start, end, live)
        return True

    def points(self):
        return (self.previous_points + self.wave.get_history())[-500:]

    def finish(self):
        return {**self.block(final=True), 'available_end': self.cursor, 'reset': False,
                'bytes_read': self.byte_count, 'emitted_bytes': self.emitted,
                'points': self.points()}


def positions(client, status, channels):
    # Protocol 53 backends released before channel_cursors still have paged reads.
    if 'channel_cursors' in status:
        return {ch: status['channel_cursors'][str(ch)] for ch in channels}
    ends = {}
    for ch in channels:
        page = client.call('rtt_read_channel', {'channel': ch, 'session': status['session']})
        if page['reset'] or page['session'] != status['session']:
            raise RuntimeErrorResponse('RTT capture changed while selecting channels')
        ends[ch] = page['available_end']
    return ends


def capture_status(client, session=None):
    status = client.call('rtt_status')
    if not status.get('session') or (session and session != status['session']) or not status.get('running'):
        raise RuntimeErrorResponse(status.get('error') or 'RTT capture stopped or changed')
    return status


def collect(client, started, channels, address, duration):
    status = capture_status(client)
    session = status['session']
    # All-channel discovery can replace its provisional channel list at startup.
    while status.get('progress_state') == 'starting':
        time.sleep(.05)
        status = capture_status(client, session)
    if started.get('reused') and address is not None:
        actual = status.get('control_block_addr')
        if actual is None or int(str(actual), 0) != int(address, 0):
            raise RuntimeErrorResponse('Requested RTT address differs from the running capture')
    primary = status.get('primary_channel', status['channels'][0] if status['channels'] else None)
    channels = channels or status['channels']
    if not channels or not set(channels).issubset(status['channels']):
        raise RuntimeErrorResponse('Requested RTT channel is not active in this capture')
    original = client.call('rtt_history')['points'] if primary in channels else []
    with ExitStack() as stack:
        readers = {ch: stack.enter_context(client.rtt_subscribe_bytes(ch, session=session)) for ch in channels}
        status = capture_status(client, session)
        ends = positions(client, status, channels)
        windows = [ChannelWindow(ch, ends[ch] if started.get('reused') else 0, session,
                                 status.get('channel_status', {}).get(str(ch), {}).get('encoding')
                                 or status.get('encoding') or 'utf-8') for ch in channels]
        now = time.monotonic()
        deadline = now + duration if duration else None
        next_status = now + 1
        live = deadline is None
        print(json.dumps({'capture': 'rtt', 'shared': True, **started, 'channels': channels}), flush=True)
        try:
            for window in windows:
                window.read_to(client, ends[window.channel], live)
            while deadline is None or time.monotonic() < deadline:
                received = False
                for window in windows:
                    if window.receive(client, readers[window.channel], live):
                        received = True
                now = time.monotonic()
                if now >= next_status:
                    capture_status(client, session)
                    next_status = now + 1
                if not received:
                    time.sleep(.01 if live else min(.01, max(0, deadline - now)))
        except KeyboardInterrupt:
            pass
        # Snapshot the cutoff once. Later traffic must not extend a finite command.
        ends = positions(client, capture_status(client, session), channels)
        for window in windows:
            end = ends[window.channel]
            while window.cursor < end and window.receive(client, readers[window.channel], live, limit=end):
                pass
            window.read_to(client, end, live)
        rows = [{**w.finish(), 'missing_batches': readers[w.channel].missing_batches,
                 'mux_dropped_bytes': readers[w.channel].mux_dropped_bytes} for w in windows]
    history = client.call('rtt_history')['points'] if primary in channels else []
    if client.call('rtt_status')['session'] != session:
        raise RuntimeErrorResponse('RTT capture changed while reading waveform history')
    # The backend's historical points have their original timestamps. A GUI in
    # terminal mode may have no active waveform parser for the current window.
    if primary in channels and history == original:
        history = (history + rows[channels.index(primary)]['points'])[-500:]
    return {'points': history if primary in channels else rows[0]['points'], 'channels': rows}
