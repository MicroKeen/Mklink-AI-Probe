"""Native MKLink SDK over the authenticated S3 byte/file relay.

Only transport and file delivery are adapted. Device, Pika parsing, FLM,
memory access and RTT/MUX implementation come from the pinned MKLink runtime.
No OS WLAN calls, SWD implementation, retries, or global runtime edits.
"""
from __future__ import annotations

import base64
from collections import deque
import hashlib
from pathlib import Path
import threading
import time

from mklink.bridge import MKLinkSerialBridge
from mklink._types import DeviceState



class _FifoRLock:
    """One RPC at a time, without a polling reader starving queued writes."""
    def __init__(self):
        self.condition=threading.Condition()
        self.waiters=deque()
        self.owner=None
        self.depth=0

    def __enter__(self):
        ident=threading.get_ident()
        with self.condition:
            if self.owner==ident:
                self.depth+=1
                return self
            ticket=object();self.waiters.append(ticket)
            try:
                self.condition.wait_for(lambda:self.owner is None and self.waiters[0] is ticket)
            except BaseException:
                self.waiters.remove(ticket);self.condition.notify_all();raise
            self.waiters.popleft();self.owner=ident;self.depth=1
        return self

    def __exit__(self,*_):
        with self.condition:
            if self.owner!=threading.get_ident():raise RuntimeError('RPC lock owner mismatch')
            self.depth-=1
            if not self.depth:
                self.owner=None;self.condition.notify_all()


class WirelessLink:
    def __init__(self, rpc, node_id, *, owner='Mklink wireless target'):
        if len(node_id) != 12 or any(c not in '0123456789abcdef' for c in node_id):
            raise ValueError('Exact S3 device identity required')
        self.rpc = rpc
        self.node_id = node_id
        self.owner = owner
        self.lock = _FifoRLock()
        self.lease = ''
        self.generation = None
        self.sequence = None
        self.poisoned = False
        self.opened = False
        self.renewed = 0
        self.recent_rpc = deque(maxlen=8)
        self.read_limit_supported=False;self.read_max=1024;self.file_chunk=1024
        self.rpc_samples={};self.accepted_native_bytes=0;self.received_native_bytes=0;self.staged_file_bytes=0
        self.started=time.monotonic()

    def _timing(self,method,started,ok):
        ms=round((time.monotonic()-started)*1000,3)
        self.recent_rpc.append(dict(method=method,ms=ms,ok=ok))
        entry=self.rpc_samples.setdefault(method,dict(count=0,failures=0,total_ms=0.0,samples=[]))
        entry['count']+=1;entry['failures']+=not ok;entry['total_ms']+=ms
        if len(entry['samples'])<50000:entry['samples'].append(ms)

    def performance(self):
        import math
        methods={}
        for name,item in self.rpc_samples.items():
            values=sorted(item['samples']);n=len(values)
            methods[name]=dict(count=item['count'],failures=item['failures'],total_ms=round(item['total_ms'],3),
                p50_ms=values[max(0,math.ceil(n*.50)-1)],p95_ms=values[max(0,math.ceil(n*.95)-1)],
                max_ms=values[-1],samples_omitted=item['count']-n)
        return dict(scope='owned authenticated RPC session, payload bytes exclude JSON/encryption overhead',
            elapsed_s=round(time.monotonic()-self.started,3),read_window_bytes=self.read_max,file_chunk_bytes=self.file_chunk,
            native_tx_accepted_bytes=self.accepted_native_bytes,native_rx_bytes=self.received_native_bytes,
            file_payload_accepted_bytes=self.staged_file_bytes,methods=methods)

    def acquire(self):
        with self.lock:
            status = self.rpc('get_status', {})
            if status['device']['id'] != self.node_id or not status['probe']['ready']:
                raise RuntimeError('Selected S3/V4 identity is not ready')
            self.lease = self.rpc('control.acquire', {'owner': self.owner})['lease_token']
            self.renewed = time.monotonic()
            state = self.call('get_probe_transport')
            if not state.get('binary_streaming') or state.get('stream_active') or state['state'] != 'ready':
                self.close()
                raise RuntimeError('Native stream requires compatible S3 firmware and an idle V4')
            self.generation = state['generation']
            self.sequence = state['next_sequence']
            self.read_limit_supported=state.get('read_limit_supported') is True
            if self.read_limit_supported:
                legacy=state.get('max_read_payload',1024)
                if type(legacy) is not int or not 1<=legacy<=4096:raise ValueError('Invalid legacy read window')
                self.read_max=state.get('bulk_read_max',legacy)
                if type(self.read_max) is not int or not legacy<=self.read_max<=32768:raise ValueError('Invalid negotiated read window')
            self.usb_metrics_supported=state.get('usb_metrics_supported') is True
            self.native_binary_bulk=self.usb_metrics_supported and status['probe'].get('version')=='V4.7.2'
            self.file_chunk=state.get('file_chunk_max',1024)
            if type(self.file_chunk) is not int or not 1<=self.file_chunk<=2048:raise ValueError('Invalid negotiated file window')

    def call(self, method, params=None):
        with self.lock:
            if not self.lease:
                raise RuntimeError('No wireless target lease')
            if time.monotonic() - self.renewed > 3:
                self.rpc('control.renew', {'lease_token': self.lease})
                self.renewed = time.monotonic()
            started=time.monotonic()
            try:
                result=self.rpc(method, dict(params or {}, lease_token=self.lease))
            except Exception:
                self._timing(method,started,False)
                raise
            self._timing(method,started,True)
            return result

    def stream(self, action, data=None):
        with self.lock:
            if self.poisoned:
                raise ConnectionError('Native stream outcome unknown; no replay')
            params = dict(generation=self.generation, sequence=self.sequence)
            if action=='read' and self.read_limit_supported:params['max_bytes']=self.read_max
            if data is not None:
                if not 1 <= len(data) <= 1024:
                    raise ValueError('Native byte chunk must contain 1..1024 bytes')
                params['request_base64'] = base64.b64encode(data).decode('ascii')
            self.sequence += 1
            try:
                result = self.call('probe.stream.' + action, params)
                if result['generation'] != self.generation:
                    raise ConnectionError('V4 generation changed during native stream')
                if data is not None and result['accepted_bytes'] != len(data):
                    raise ConnectionError('Partial native write; outcome unknown')
                reply = base64.b64decode(result['reply_base64'], validate=True)
                if len(reply) > (self.read_max if action=='read' else 1024):
                    raise ConnectionError('Oversized native stream response')
                self.received_native_bytes+=len(reply)
                if data is not None:self.accepted_native_bytes+=len(data)
                if action == 'open':
                    self.opened = True
                elif action == 'close':
                    self.opened = False
                return reply
            except Exception as error:
                self.poisoned = True
                raise ConnectionError('Native transport failed; no replay') from error

    def upload_file(self, path, kind, progress=None, expected_sha256=None):
        path = Path(path)
        if kind not in ('BIN', 'FLM') or not 1 <= path.stat().st_size <= 1048576:
            raise ValueError('Bounded BIN/FLM file required')
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if not 1<=len(data)<=1048576 or (expected_sha256 is not None and digest!=expected_sha256):
            raise RuntimeError('Staging input changed from the acknowledged image; no file request sent')
        if progress:progress('upload',0,len(data))
        result = self.call('probe.files.begin', dict(kind=kind, size=len(data), sha256=digest))
        if result['complete']:
            if result['sha256'] != digest:
                raise RuntimeError('Cached file digest mismatch')
            if progress:progress('complete',len(data),len(data))
            return result['path']
        ident = result['upload_id']
        # Every file chunk has a unique increasing offset. A timeout is never
        # replayed; programming cannot begin before SHA256-verified commit.
        for offset in range(0, len(data), self.file_chunk):
            chunk = data[offset:offset + self.file_chunk]
            result = self.call('probe.files.write', dict(upload_id=ident, offset=offset,
                               data_base64=base64.b64encode(chunk).decode('ascii')))
            if result['offset'] != offset + len(chunk):
                raise RuntimeError('File offset mismatch; upload not repeated')
            self.staged_file_bytes+=len(chunk)
            if progress:progress('upload',result['offset'],len(data))
        if progress:progress('verify',0,0)
        result = self.call('probe.files.commit', dict(upload_id=ident))
        if result['sha256'] != digest or result['bytes'] != len(data):
            raise RuntimeError('Committed file identity mismatch')
        if progress:progress('complete',len(data),len(data))
        return result['path']

    def close(self):
        with self.lock:
            if self.opened:
                if self.poisoned:
                    # Explicitly quarantine; never inject a text stop into a
                    # possible binary packet or continue using another lease.
                    try:
                        self.call('probe.stream.abort')
                    except Exception:
                        pass
                    raise ConnectionError('Native session quarantined; explicit USB recovery required')
                self.stream('close')
            if self.lease:
                self.call('control.release')
                self.lease = ''


class WirelessSerial:
    """Minimal serial-shaped transport consumed by the SDK's sole reader."""
    def __init__(self, link):
        self.link = link
        self.timeout = .01
        self.write_timeout = 3
        self.buffer = bytearray()
        self.is_open = False
        self.safe_close = lambda: True
        link.stream('open')
        self.is_open = True

    @property
    def in_waiting(self):
        return len(self.buffer) or 1024

    def read(self, size=1):
        if not self.is_open:
            raise ConnectionError('Wireless stream closed')
        if not self.buffer:
            self.buffer.extend(self.link.stream('read'))
        result = bytes(self.buffer[:size])
        del self.buffer[:size]
        return result

    def write(self, data):
        if not self.is_open:
            raise ConnectionError('Wireless stream closed')
        for offset in range(0, len(data), 1024):
            self.link.stream('write', data[offset:offset + 1024])
        return len(data)

    def flush(self):
        # Each write is acknowledged after the complete USB transmission.
        return None

    def reset_input_buffer(self):
        raise RuntimeError('Discarding an active native stream is forbidden')

    def reset_output_buffer(self):
        return None  # No queued or retried writes exist.

    def close(self):
        if self.is_open:
            if not self.safe_close():
                self.link.poisoned = True
            if not self.link.poisoned:
                self.link.stream('close')
            self.is_open = False


class WirelessBridge(MKLinkSerialBridge):
    def __init__(self, link):
        super().__init__('s3-' + link.node_id)
        self.auto_recovery = False
        self.capture_stop_timeout = 30.0
        self.reader_close_timeout = 35.0
        self.mux_timeout = 60.0
        self.stream_stop_attempts = 1
        self.stream_stop_timeout = 5.0
        self.stream_identity_timeout = 10.0
        from mklink.hil_lock import HilFileLock
        self._hil_locks = [HilFileLock('device_mklink-wireless-' + link.node_id, lease_s=60),
                           HilFileLock('transport_mklink-rpc_' + link.node_id, lease_s=60)]
        self._held_locks = []
        self._endpoint = None
        self._lease_stop = threading.Event()
        self._lease_thread = None
        self.link = link
        self._staged_firmware = None
        self._retired = False

    def send_command(self,cmd,timeout=5.0,**kwargs):
        # The native USB default10s can expire while a valid radio RPC still
        # has up to30s to finish. Choose the radio budget before sending once.
        budget=max(float(timeout),60.0)
        try:
            return super().send_command(cmd,timeout=budget,**kwargs)
        except Exception as error:
            if hasattr(error, 'add_note'):
                error.add_note('Wireless RPC timings (no payloads): '+str(list(self.link.recent_rpc)))
            raise

    def _connect(self, *, recover_stream=False):
        # Physical identity is already established by the authenticated S3 and
        # V4 descriptor/marker/version handshake. Do not discover a PC USB port,
        # reconcile DAP ownership on another device, or recover an old stream.
        from mklink.probes import require_runtime_port
        require_runtime_port(self._port)
        for lock in self._hil_locks:
            lock.acquire()
            self._held_locks.append(lock)
        if not self._port_lock.acquire():
            raise ConnectionError('S3 transport already owned')
        if self._endpoint is not None:
            self._endpoint.open()
        self.link.acquire()
        def renew():
            while not self._lease_stop.wait(2):
                try:
                    if not all(lock.renew() for lock in self._held_locks):
                        raise ConnectionError('Wireless hardware ownership lost')
                    self.link.call('get_probe_transport')
                except Exception:
                    self.link.poisoned = True
                    return
        self._lease_thread = threading.Thread(target=renew, daemon=True)
        self._lease_thread.start()
        self._serial = WirelessSerial(self.link)
        self._ctx.state = DeviceState.CONNECTING
        self._running = True
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()
        self._prompt_event.clear()
        self._serial.write(b'\n')
        if not self._prompt_event.wait(30):
            self.link.poisoned = True
            raise ConnectionError('Wireless Pika synchronization timed out; no replay')
        self._ctx.state = DeviceState.READY
        if not self._verify_identity():
            raise ConnectionError('Native MKLink identity verification failed')
        self.last_connect_error = None
        return True

    def close(self):
        if self._retired:
            return
        mux = self._mux
        if self._serial is not None:
            self._serial.safe_close = lambda: self._transport_error is None and self._ctx.state is not DeviceState.ERROR and (mux is None or mux._error is None)
        if self._transport_error is not None or self._ctx.state is DeviceState.ERROR or (mux is not None and mux._error is not None):
            self.link.poisoned = True
        self._lease_stop.set()
        if self._lease_thread:
            self._lease_thread.join(timeout=35)
            if self._lease_thread.is_alive():
                raise ConnectionError('Wireless lease worker still owns IO')
        # Do not close the event loop or release HIL ownership if the reader
        # failed to exit. The caller can inspect and explicitly recover it.
        super().close()
        try:
            self.link.close()
        except ConnectionError:
            if not self.link.poisoned:
                raise
            # Remote quarantine is retained by S3. It must not prevent retiring
            # a fully stopped local owner after an explicit physical recovery.
            self.last_connect_error = 'Remote session quarantined; explicit USB recovery required'
        finally:
            if self._endpoint:
                self._endpoint.close()
            for lock in reversed(self._held_locks):
                lock.release()
            self._held_locks.clear()
            self._retired = True

    @classmethod
    def from_node(cls, node):
        from mklink.s3_rpc import Endpoint
        endpoint = Endpoint(node)
        bridge = cls(WirelessLink(endpoint.rpc, node['node_id'], owner='MKLink shared backend'))
        bridge._endpoint = endpoint
        return bridge

    def upload_algorithm(self, algorithm):
        from mklink.cmsis_dap.algorithm_catalog import _extract_bytes
        import tempfile
        with tempfile.TemporaryDirectory(prefix='s3-flm-') as directory:
            path = Path(directory) / 'algorithm.flm'
            path.write_bytes(_extract_bytes(algorithm))
            return self.link.upload_file(path, 'FLM')

    def prepare_firmware(self, path):
        path = Path(path).resolve(strict=True)
        if path.suffix.lower() != '.bin':
            raise ValueError('S3 relay currently supports BIN firmware; HEX must be converted explicitly')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        remote = self.link.upload_file(path, 'BIN', expected_sha256=digest)
        self._staged_firmware = (path, digest, remote)

    def upload_firmware(self, path):
        path = Path(path).resolve(strict=True)
        if self._staged_firmware is None:
            self.prepare_firmware(path)
        staged, digest, remote = self._staged_firmware
        if path != staged or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise RuntimeError('Firmware changed after staging; no program command sent')
        return remote
