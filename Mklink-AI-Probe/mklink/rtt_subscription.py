"""Loss-detecting binary subscription to the shared backend, never the probe."""
import json
import socket

from mklink.remote.stream_protocol import (
    decode_frame, StreamType, RTT_CHANNEL_BYTES, RTT_BYTES_HEADER,
    MAX_PAYLOAD_SIZE, HEADER_SIZE,
)


class RttByteSubscription:
    """Read one channel over one authenticated WebSocket connection.

    A byte offset is scoped to a capture UUID. Overflow, channel replacement and
    transport loss are reported, never hidden by reconnecting or text decoding.
    The caller drains/writes batches promptly; no unbounded background queue.
    """
    def __init__(self, info, channel=0, *, session=None):
        from websockets.sync.client import connect
        if type(channel) is not int or not 0 <= channel < 8:
            raise ValueError('RTT channel must be 0..7')
        self.session = session
        self.cursor = None
        self.missing_batches = self.lost_bytes = self.mux_dropped_bytes = 0
        self._sequence = 0
        self._socket = None
        raw = socket.create_connection(('127.0.0.1', info['port']), timeout=3)
        try:
            self._socket = connect(
                f"ws://127.0.0.1:{info['port']}/ws/streams/rtt-bytes-{channel}",
                sock=raw, additional_headers={'Authorization': 'Bearer '+info['token']},
                compression=None, open_timeout=3, close_timeout=1,
                max_size=MAX_PAYLOAD_SIZE+HEADER_SIZE,
            )
            ready = decode_frame(self._socket.recv(timeout=3))
            if ready.stream_type != StreamType.CONTROL or ready.stream_id != int(StreamType.RTT_RAW):
                raise RuntimeError('Missing RTT byte subscription-ready frame')
            self._sequence = ready.sequence
        except BaseException:
            if self._socket is not None:
                self._socket.close()
            raw.close()
            raise

    def read(self, timeout=1.0):
        """Return a binary batch and cumulative losses; timeout returns empty data."""
        data = b''
        try:
            frame = decode_frame(self._socket.recv(timeout=timeout))
        except TimeoutError:
            frame = None
        if frame is not None:
            if frame.stream_id != int(StreamType.RTT_RAW):
                raise RuntimeError('Wrong RTT stream identity')
            if frame.stream_type == StreamType.CONTROL:
                if not isinstance(json.loads(frame.payload), dict):
                    raise RuntimeError('Invalid RTT stream status')
            else:
                if frame.stream_type != StreamType.RTT_RAW or frame.flags != RTT_CHANNEL_BYTES:
                    raise RuntimeError('Wrong RTT byte encoding')
                if frame.sequence <= self._sequence or len(frame.payload) < RTT_BYTES_HEADER.size:
                    raise RuntimeError('Invalid RTT byte frame')
                self.missing_batches += frame.sequence - self._sequence - 1
                self._sequence = frame.sequence
                session, offset, lost = RTT_BYTES_HEADER.unpack_from(frame.payload)
                capture = session.hex()
                if self.session is not None and capture != self.session:
                    raise RuntimeError('RTT capture changed; subscribe again explicitly')
                self.session = capture
                if self.cursor is not None:
                    if offset < self.cursor:
                        raise RuntimeError('RTT byte offset moved backwards')
                    self.lost_bytes += offset - self.cursor
                data = frame.payload[RTT_BYTES_HEADER.size:]
                if frame.item_count != len(data):
                    raise RuntimeError('Invalid RTT byte count')
                self.cursor = offset + len(data)
                self.mux_dropped_bytes = lost
        return {'data': data, 'session': self.session, 'cursor': self.cursor,
                'missing_batches': self.missing_batches, 'lost_bytes': self.lost_bytes,
                'mux_dropped_bytes': self.mux_dropped_bytes}

    def close(self):
        if self._socket is not None:
            self._socket.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
