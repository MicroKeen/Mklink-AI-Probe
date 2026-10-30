"""One firmware RTT engine, bounded independent consumers, no COM reader."""
from collections import deque
import struct
import time


class MuxRTTManager:
    """Mutations take commands then condition; feed only takes condition.

    Register before configuration so events arriving with the ACK are retained.
    Rejected changes discard only the new consumer; unknown outcomes poison the
    transport. No fallback, reset, or replay can erase another consumer's cursor.
    """
    QUEUE_BYTES = 256 * 1024
    MAX_CONSUMERS = 16

    def __init__(self, transport):
        self.transport = transport
        self.consumers = {}
        self.address = None
        self.up = self.down = 0
        self.recorders = set()

    def _configure(self, op, data=b'', *, info=None):
        answer = self.transport.request(op, data)
        valid = answer == b''
        if op == 0x20:
            # Legacy START returns descriptor counts, NOT selected masks.
            valid = (len(answer) == 2 and 1 <= answer[0] <= 32 and answer[1] <= 32
                     and not data[4] >> answer[0] and not data[5] >> answer[1])
            if valid and info is not None:
                valid = all(info.get(key, value) == value for key, value in
                            zip(('max_up_buffers', 'max_down_buffers'), answer))
        if not valid:
            self.transport.fail('Invalid RTT configuration response; outcome unknown, do not replay')
            self.transport._check()

    def subscribe(self, session, address, up, down):
        t = self.transport
        with t._commands:
            t._check()
            if session in self.consumers:
                raise RuntimeError('RTT consumer is already subscribed')
            if len(self.consumers) >= self.MAX_CONSUMERS:
                raise RuntimeError('Too many RTT consumers')
            if self.consumers:
                if self.address != address:
                    raise RuntimeError('RTT control-block conflict: active consumers use a different control block')
                if not t.capabilities & t.RTT_UPDATE_CAPABILITY:
                    raise RuntimeError('Concurrent RTT/SystemView requires incremental RTT firmware support; update the probe firmware')
            new_up, new_down = self.up | up, self.down | down
            with t._condition:
                session._queues.clear()
                session._sizes.clear()
                session._status = 0
                session.dropped_bytes.clear()
                self.consumers[session] = (up, down)
            try:
                if self.address is None:
                    self._configure(0x20, struct.pack('<IBB', address, up, down), info=session.info)
                elif (new_up, new_down) != (self.up, self.down):
                    self._configure(0x23, bytes([new_up, new_down]))
            except BaseException:
                with t._condition:
                    self.consumers.pop(session)
                raise
            self.address = address
            self.up, self.down = new_up, new_down
            t.rtt_mask = new_up

    def start_recorder(self, session):
        with self.transport._commands:
            if session._channel not in self.recorders:
                session.send_input(b'\x01')
                self.recorders.add(session._channel)

    def unsubscribe(self, session):
        t = self.transport
        with t._commands:
            if session not in self.consumers:
                return
            up = down = 0
            for consumer, (u, d) in self.consumers.items():
                if consumer is not session:
                    up |= u
                    down |= d
            # An observer on the same channel still needs its target recorder.
            # Defer STOP until the final consumer of that channel is released.
            for channel in tuple(self.recorders):
                if up & (1 << channel):
                    down |= 1 << channel
                else:
                    session.send_input(b'\x02', channel=channel)
                    self.recorders.discard(channel)
            if len(self.consumers) == 1:
                self._configure(0x22)
            elif (up, down) != (self.up, self.down):
                self._configure(0x23, bytes([up, down]))
            with t._condition:
                del self.consumers[session]
                session._running = False
                session._queues.clear()
                session._sizes.clear()
                t._condition.notify_all()
            self.up, self.down = up, down
            t.rtt_mask = up
            if not self.consumers:
                self.address = None

    def publish(self, payload):
        """Called by the sole transport reader with its condition held."""
        channel = payload[0]
        for session, (up, _) in self.consumers.items():
            if not up & (1 << channel):
                continue
            if payload[1]:
                # Errors cannot disappear when a slow observer's queue overflows.
                session._status = payload[1]
                continue
            queue = session._queues.setdefault(channel, deque())
            size = session._sizes.get(channel, 0)
            while queue and size + len(payload) > self.QUEUE_BYTES:
                removed = queue.popleft()
                size -= len(removed)
                lost = len(removed) - 6
                session.dropped_bytes[channel] = session.dropped_bytes.get(channel, 0) + lost
                key = (0x40, channel)
                self.transport.dropped_bytes[key] = self.transport.dropped_bytes.get(key, 0) + lost
            queue.append(payload)
            session._sizes[channel] = size + len(payload)


class MuxRTTSession:
    def __init__(self, transport, info, channel=0, channels=None):
        self.transport = transport
        self.info = info
        self._channel = channel
        self.channels = list(channels if channels is not None else [channel])
        if (not self.channels or len(set(self.channels)) != len(self.channels)
                or any(type(ch) is not int or not 0 <= ch < 8 for ch in self.channels)
                or channel not in self.channels):
            raise ValueError('RTT channels must be unique integers 0..7 and include channel')
        self._running = False
        self._queues = {}
        self._sizes = {}
        self._status = 0
        self.dropped_bytes = {}
        with transport._commands:
            if transport._rtt_manager is None:
                transport._rtt_manager = MuxRTTManager(transport)
            self.manager = transport._rtt_manager

    def start(self, addr, **unused):
        up = sum(1 << ch for ch in self.channels)
        down = sum(1 << item['channel'] for item in self.info['down_buffers']
                   if item['active'] and item['channel'] in self.channels)
        self.manager.subscribe(self, int(str(addr), 0), up, down)
        self._running = True
        return {'control_block_addr': addr, 'transport': 'cdc-mux', 'channels': self.channels}

    def read_channels(self, duration=.01, *, max_bytes=None):
        deadline = time.monotonic() + max(0, duration)
        t = self.transport
        with t._condition:
            while True:
                t._check()
                if not self._running:
                    raise RuntimeError('RTT not started')
                if self._status == 7:
                    raise RuntimeError('DAP changed the target; RTT capture was invalidated. Restart capture after debugging.')
                if self._status == 8:
                    raise RuntimeError('MCU reset recovery timed out; RTT control block did not recover within 5 seconds. The reset was not repeated.')
                if self._status:
                    raise RuntimeError(f'RTT target read failed (status {self._status})')
                result = {ch: bytearray() for ch in self.channels}
                budget = max_bytes
                for ch in self.channels:
                    queue = self._queues.get(ch)
                    while queue and (budget is None or budget > 0):
                        frame = queue.popleft()
                        self._sizes[ch] -= len(frame)
                        data = frame[6:]
                        take = len(data) if budget is None else min(len(data), budget)
                        result[ch].extend(data[:take])
                        if take < len(data):
                            tail = frame[:6] + data[take:]
                            queue.appendleft(tail)
                            self._sizes[ch] += len(tail)
                        if budget is not None:
                            budget -= take
                remaining = deadline - time.monotonic()
                if remaining <= 0 or any(result.values()) or budget == 0:
                    return {ch: bytes(data) for ch, data in result.items()}
                t._condition.wait(remaining)

    def read_output_bytes(self, duration=10):
        return self.read_channels(duration).get(self._channel, b'')

    def read_output(self, duration=10):
        return self.read_output_bytes(duration).decode('utf-8', 'replace')

    def send_input(self, data, channel=None):
        channel = self._channel if channel is None else channel
        if channel not in self.channels:
            raise ValueError('RTT channel is not subscribed')
        offset = 0
        deadline = time.monotonic() + 3
        while offset < len(data):
            # Yield the command slot between blocks and during backpressure so
            # memory/Watch requests keep progressing. Stop prevents further writes.
            with self.transport._commands:
                if not self._running:
                    raise RuntimeError(f'RTT stopped; {offset} bytes accepted, do not replay')
                size = self.transport.transfer_quantum
                fast = size == self.transport.FAST_TRANSFER_BYTES
                answer = self.transport.request(0x24 if fast else 0x21, bytes([channel]) + data[offset:offset+size])
                accepted = int.from_bytes(answer, 'little')
                if len(answer) != (2 if fast else 1) or accepted > min(size, len(data)-offset):
                    self.transport.fail('Invalid RTT acceptance count; do not replay')
                    self.transport._check()
                offset += accepted
            if not accepted:
                if time.monotonic() >= deadline:
                    raise RuntimeError(f'RTT target buffer full; {offset} bytes accepted, do not replay the whole request')
                time.sleep(.005)
        return True

    def stop(self):
        if self._running:
            self.manager.unsubscribe(self)
            self._running = False
        return ''

    def reset_failed_start(self):
        return ''  # No raw recovery or automatic replay after a framed failure.
