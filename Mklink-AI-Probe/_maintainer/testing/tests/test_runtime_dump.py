"""Shared dump contracts reuse the actual route, parser and admission gate."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading
from unittest.mock import Mock

import pytest
from fastmcp import Client
from mklink import dump_memory, runtime_mcp
from mklink.runtime import RuntimeClient, RuntimeErrorResponse
from test_runtime_memory import batch
from types import SimpleNamespace
import struct
from test_sampling_contract import memory_bridge
from test_mux_block_read import peer as memory_peer, reply
from test_watch_timing_v2 import peer as watch_peer, bridge_for
from mklink.mux import packet


@pytest.mark.parametrize('overrides',[{'regions':[]},{'regions':[{'address':True,'size':4}]},
    {'regions':[{'address':-1,'size':4}]},{'regions':[{'address':2**32,'size':4}]},{'regions':[{'address':0,'size':True}]},
    {'regions':[{'address':2**64-1,'size':2}]},{'regions':[{'address':0,'size':524289}]},
    {'regions':[{'address':0,'size':1}]*9},{'regions':[{'address':0,'size':4,'extra':1}]},
    {'regions':[{'address':0,'size':4096}],'sample_count':129},
    {'regions':[{'address':0,'size':524288}],'sample_count':2},
    {'sample_count':True},{'sample_count':0},{'timeout':True},{'timeout':0},{'timeout':61},
    {'speed_profile':'unknown'},{'extra':True}])
def test_dump_validates_entire_request_before_clock_or_capture(batch,monkeypatch,overrides):
    client,_,device,_,_=batch
    read=Mock();monkeypatch.setattr(dump_memory,'read_dump_memory_regions_once',read)
    device.set_debug_speed=Mock()
    response=client.post('/api/device/dump-memory',json={'regions':[{'address':0,'size':4}],'speed_profile':'low',**overrides})
    assert response.status_code==422,response.text
    read.assert_not_called();device.set_debug_speed.assert_not_called()


def test_shared_dump_does_not_preempt_gui_or_change_clock(batch,monkeypatch):
    client,_,device,_,managers=batch
    managers['rtt'].running=True
    read=Mock();monkeypatch.setattr(dump_memory,'read_dump_memory_regions_once',read)
    device.set_debug_speed=Mock()
    response=client.post('/api/device/dump-memory',json={'regions':[{'address':0,'size':4}],'speed_profile':'low'})
    assert response.status_code==409 and managers['rtt'].running
    read.assert_not_called();device.set_debug_speed.assert_not_called()


def test_shared_dump_holds_operation_and_lease_for_all_samples(batch,monkeypatch):
    client,state,device,control,_=batch
    entered,release=threading.Event(),threading.Event()
    def read(*args,**kwargs):
        entered.set();assert release.wait(5);return (b'abcd',)
    reader=Mock(side_effect=read)
    monkeypatch.setattr(dump_memory,'read_dump_memory_regions_once',reader)
    with ThreadPoolExecutor() as pool:
        result=pool.submit(client.post,'/api/device/dump-memory',json={'regions':[{'address':0,'size':4}],'sample_count':2})
        assert entered.wait(5)
        try:
            assert control.operation_lock.locked() and state['resource_manager'].get_status()
            assert client.post('/api/dash/rtt/start',json={}).status_code==409
        finally: release.set()
        response=result.result(timeout=5)
    assert response.status_code==200 and response.json()['sample_count']==2
    assert reader.call_count==2
    assert not control.operation_lock.locked() and not state['resource_manager'].get_status()


def test_runtime_budget_covers_explicit_samples_and_never_retries(monkeypatch):
    calls=[]
    def request(*args,**kwargs):
        calls.append(kwargs)
        raise RuntimeErrorResponse('response lost')
    monkeypatch.setattr('mklink.runtime.request',request)
    client=RuntimeClient(info={'port':8765});client.session_id='one'
    with pytest.raises(RuntimeErrorResponse,match='lost'):
        client.call('dump_memory',{'regions':[{'address':0,'size':4}],'sample_count':2,'timeout':60})
    assert calls==[{'timeout':145}]
    with pytest.raises(ValueError):
        client.call('dump_memory',{'regions':[{'address':0,'size':4}],'sample_count':65})
    assert len(calls)==1


def test_active_mcp_dump_is_shared_thin_adapter(monkeypatch):
    calls=[]
    class FakeClient:
        info={}
        def __init__(self,**kwargs): calls.append('new')
        def connect(self,**kwargs): return {}
        def call(self,name,arguments): calls.append((name,arguments));return {'sample_count':1}
        def close(self):pass
    monkeypatch.setattr(runtime_mcp,'RuntimeClient',FakeClient)
    body={'regions':[{'address':0,'size':4}]}
    async def run():
        async with Client(runtime_mcp.build_server()) as mcp:
            assert (await mcp.call_tool('dump_memory',body,raise_on_error=False)).is_error
            assert not calls
            await mcp.call_tool('connect',{'probe':'chosen'})
            assert not (await mcp.call_tool('dump_memory',body)).is_error
    asyncio.run(run())
    assert calls==['new',('dump_memory',{**body,'sample_count':1,'timeout':10.0,'speed_profile':None})]


@pytest.mark.parametrize('options', [
    {'period':-1},{'period':True},{'duration':301},{'duration':True},
    {'frames':True},{'frames':100001},{'frames':0,'duration':0},{'period':0,'frames':2},
    {'speed_profile':'bad'},{'regions':[{'address':0,'size':4}]*16},
])
def test_periodic_capture_invalid_arguments_never_start_or_change_clock(batch,options):
    client,_,device,_,_=batch
    device.set_debug_speed=Mock()
    device._bridge=Mock()
    response=client.post('/api/device/dump-memory/capture',json={'regions':[{'address':0,'size':4}],**options})
    assert response.status_code==422,response.text
    device.set_debug_speed.assert_not_called()
    device._bridge._enter_stream.assert_not_called()


@pytest.mark.parametrize('byte_limit_delta', [0, -1])
def test_packed_capture_keeps_payloads_timestamps_and_exact_json_limit(monkeypatch, byte_limit_delta):
    import json
    from types import SimpleNamespace
    from mklink.mux_watch import PackedWatchSample
    expected = [{'sample_index': 0, 'timestamp_us': 2**32 + 12, 'regions': [
        {'address': '0x20000000', 'size': 4, 'data_hex': '0001feff'},
        {'address': '0x20000010', 'size': 4, 'data_hex': '10203040'}]}]
    session = Mock()
    session.stats = {'parser_dropped_bytes': 0}
    session.read_frames.return_value = [PackedWatchSample(2**32 + 12,
        bytes.fromhex('aabb0001feff10203040'), 2)]
    monkeypatch.setattr(dump_memory, 'DumpMemoryStreamSession', lambda *a, **k: session)
    exact = len(json.dumps(expected[0], separators=(',', ':')).encode()) + 1
    monkeypatch.setattr(dump_memory, 'MAX_DUMP_RESULT_JSON_BYTES', exact + byte_limit_delta)
    def capture():
        return dump_memory.capture_dump_stream(SimpleNamespace(_bridge=None),
            [{'address': 0x20000000, 'size': 4}, {'address': 0x20000010, 'size': 4}],
            period=.000001, frames=1)
    if byte_limit_delta:
        with pytest.raises(ValueError, match='16 MiB'): capture()
    else:
        result = capture()
        assert result['samples'] == expected
        assert not result['incomplete_tail']
    assert session.packed_frames is True
    session.stop.assert_called_once()


def test_periodic_capture_rejects_queue_loss_after_confirmed_stop(monkeypatch):
    from types import SimpleNamespace
    from mklink.mux_watch import PackedWatchSample
    session = Mock()
    session.stats = {'parser_dropped_bytes': 1024}
    session.read_frames.return_value = [PackedWatchSample(1, b'abcd', 0)]
    monkeypatch.setattr(dump_memory, 'DumpMemoryStreamSession', lambda *a, **k: session)
    with pytest.raises(RuntimeError, match='integrity failure'):
        dump_memory.capture_dump_stream(SimpleNamespace(_bridge=None),
            [{'address': 0x20000000, 'size': 4}], period=.000001, frames=1)
    session.stop.assert_called_once()


def test_capture_owner_lease_check_ignores_other_clients():
    from types import SimpleNamespace
    import time
    from mklink.runtime_api import active_operation, operation_session_ended
    owner=SimpleNamespace(expires=time.monotonic()+10)
    control=SimpleNamespace(sessions={'owner':owner})
    token=active_operation.set((control,'owner'))
    try:
        assert not operation_session_ended()
        owner.expires=time.monotonic()-1
        control.sessions['other']=SimpleNamespace(expires=time.monotonic()+10)
        assert operation_session_ended()
        owner.expires=time.monotonic()+10
        assert not operation_session_ended()
        del control.sessions['owner']
        assert operation_session_ended()
    finally:
        active_operation.reset(token)
    assert not operation_session_ended()


@pytest.mark.parametrize('path,implementation', [
    ('','mklink.dump_memory.capture_memory'),
    ('capture','mklink.dump_memory.capture_dump_stream'),
    ('measure','mklink.dump_benchmark.measure'),
])
def test_disconnected_capture_holds_admission_until_worker_cleanup(batch, monkeypatch, path, implementation):
    import time
    from starlette.requests import Request
    client,state,device,control,_=batch
    entered,disconnect,cleaning,release=(threading.Event() for _ in range(4))
    async def receive_disconnect():
        while not disconnect.is_set():
            await asyncio.sleep(.005)
        return {'type':'http.disconnect'}
    monkeypatch.setattr(Request,'receive',property(lambda self: receive_disconnect))
    def worker(*args,cancelled,**kwargs):
        entered.set()
        deadline=time.monotonic()+5
        while not cancelled():
            assert time.monotonic()<deadline
            time.sleep(.005)
        cleaning.set()
        assert release.wait(5)
        raise InterruptedError('cancelled after cleanup')
    monkeypatch.setattr(implementation,worker)
    with ThreadPoolExecutor() as pool:
        result=pool.submit(client.post,'/api/device/dump-memory'+('/'+path if path else ''),
                           json={'regions':[{'address':0,'size':4}]})
        assert entered.wait(5)
        try:
            disconnect.set()
            assert cleaning.wait(5)
            assert control.operation_lock.locked()
            assert state['resource_manager'].get_status()
            assert client.post('/api/dash/rtt/start',json={}).status_code==409
        finally:
            release.set()
        response=result.result(timeout=5)
    assert response.status_code==500 and 'cancelled after cleanup' in response.text
    assert not control.operation_lock.locked()
    assert not state['resource_manager'].get_status()


def test_periodic_capture_busy_rejects_without_stopping_gui(batch):
    client,_,device,_,managers=batch
    managers['rtt'].running=True
    device._bridge=Mock()
    response=client.post('/api/device/dump-memory/capture',json={'regions':[{'address':0,'size':4}]})
    assert response.status_code==409 and managers['rtt'].running
    device._bridge._enter_stream.assert_not_called()


def test_periodic_transport_budget_covers_count_only_request(monkeypatch):
    call=Mock(return_value={})
    monkeypatch.setattr('mklink.runtime.request',call)
    client=RuntimeClient(info={'port':8765});client.session_id='one'
    client.call('capture_dump',{'regions':[{'address':0,'size':4}],'period':.001,'frames':10,'duration':0})
    assert call.call_args.kwargs['timeout']==320


def test_shared_route_reads_full_mux_blocks_and_releases_lease(batch):
    client, state, device, _, _ = batch
    transport, calls = memory_peer()
    device._bridge = memory_bridge(transport)
    response = client.post('/api/device/dump-memory', json={'regions':[{'address':0x80000000,'size':32769}]})
    assert response.status_code == 200, response.text
    assert bytes.fromhex(response.json()['samples'][0]['regions'][0]['data_hex']) == bytes(range(256))*128 + b'\0'
    assert len([op for op, _ in calls if op == 0x16]) == 9
    assert not state['resource_manager'].get_status()


@pytest.mark.parametrize('failure', ['crc', 'short', 'epoch'])
def test_bad_memory_response_never_retries_or_publishes(batch, failure):
    client, state, device, _, _ = batch
    def corrupt(op, seq, data):
        wire = reply(op | 0x80, 18 if failure == 'epoch' else 17, seq,
                     b'\0' + (data[:-1] if failure == 'short' else data))
        return wire[:-1] + bytes([wire[-1] ^ 255]) if failure == 'crc' else wire
    transport, calls = memory_peer(failure=corrupt)
    device._bridge = memory_bridge(transport)
    response = client.post('/api/device/dump-memory', json={'regions':[{'address':0,'size':8192}], 'sample_count':2})
    assert response.status_code == 500, response.text
    assert [op for op, _ in calls] == [1, 4, 0x16]
    assert 'samples' not in response.json() and not state['resource_manager'].get_status()


def sample_peer(*, payloads=(), stop_status=0):
    transport, calls = watch_peer(stop_status=stop_status)
    original = transport.request
    def request(op, *a, **kw):
        result = original(op, *a, **kw)
        if op == 0x32:
            for seq, payload in enumerate(payloads, 1):
                transport.feed(packet(0x41, 17, seq, payload))
        return result
    transport.request = request
    return transport, calls, bridge_for(transport)


def test_periodic_route_preserves_samples_and_discards_only_unrequested_tail(batch):
    client, state, device, _, _ = batch
    payload = bytes([0,9,3,4]) + b''.join(struct.pack('<I', t)+v for t,v in [(1,b'AAAA'),(47,b'BBBB'),(51,b'CCCC')])
    transport, calls, device._bridge = sample_peer(payloads=[payload])
    response=client.post('/api/device/dump-memory/capture',json={'regions':[{'address':0,'size':4}],'period':.001,'frames':2})
    assert response.status_code == 200, response.text
    result = response.json()
    assert [s['timestamp_us'] for s in result['samples']] == [1,47]
    assert [bytes.fromhex(s['regions'][0]['data_hex']) for s in result['samples']] == [b'AAAA',b'BBBB']
    assert [op for op, _ in calls] == [1,4,0x32,0x31]
    assert not transport.watch_running and not state['resource_manager'].get_status()


@pytest.mark.parametrize('case', ['short', 'width', 'invalidated', 'reset_timeout', 'limit', 'stop'])
def test_capture_failure_returns_no_partial_samples_and_never_replays(batch, monkeypatch, case):
    client, state, device, _, _ = batch
    payload = bytes([0,9,1,4])+struct.pack('<I',1)+b'AAAA'
    if case == 'short': payload = payload[:-1]
    if case == 'width': payload = payload[:3]+bytes([8])+payload[4:]
    if case in ('invalidated','reset_timeout'): payload = struct.pack('<BBI',0,7 if case=='invalidated' else 8,1)
    if case == 'limit': monkeypatch.setattr(dump_memory, 'MAX_DUMP_RESULT_JSON_BYTES', 20)
    transport, calls, device._bridge = sample_peer(payloads=[payload], stop_status=6 if case=='stop' else 0)
    response = client.post('/api/device/dump-memory/capture',json={'regions':[{'address':0,'size':4}],'period':.001,'frames':1})
    assert response.status_code == (422 if case=='limit' else 500), response.text
    assert [op for op,_ in calls] == [1,4,0x32,0x31]
    assert 'samples' not in response.json() and not state['resource_manager'].get_status()


@pytest.mark.parametrize('before_start,stop_fails', [(True,False),(False,False),(False,True)])
def test_capture_cancel_is_not_success_and_stop_failure_remains_visible(before_start, stop_fails):
    transport, calls, bridge = sample_peer(stop_status=6 if stop_fails else 0)
    checks = iter([before_start, True])
    with pytest.raises(RuntimeError if stop_fails else InterruptedError):
        dump_memory.capture_dump_stream(SimpleNamespace(_bridge=bridge), [{'address':0,'size':4}],
            period=.001, frames=0, duration=1, cancelled=lambda:next(checks))
    assert [op for op,_ in calls] == ([1,4] if before_start else [1,4,0x32,0x31])


def test_snapshot_cancel_between_samples_never_reads_next_sample():
    transport, calls = memory_peer()
    ended = [False]
    def published(*a): ended[0] = True; return True
    with pytest.raises(InterruptedError):
        dump_memory.capture_memory(SimpleNamespace(_bridge=memory_bridge(transport)), [{'address':0,'size':4}],
            sample_count=2, publish_sample=published, cancelled=lambda:ended[0])
    assert [op for op,_ in calls] == [1,4,0x16]


def test_capture_startup_does_not_consume_requested_duration(monkeypatch):
    session = Mock()
    session.stats = {}
    session.read_frames.side_effect = [[{'format':'mux','flags':0,'timestamp_us':1,'regions':[(0,b'AAAA')]}],
                                      [{'format':'mux','flags':0,'timestamp_us':2,'regions':[(0,b'BBBB')]}]]
    ticks = iter([0,.5,.5,.6,.9])
    monkeypatch.setattr(dump_memory, 'time', SimpleNamespace(monotonic=lambda:next(ticks)))
    monkeypatch.setattr(dump_memory, 'DumpMemoryStreamSession', lambda *a,**k:session)
    result = dump_memory.capture_dump_stream(SimpleNamespace(_bridge=None), [{'address':0,'size':4}], period=.01, frames=0,duration=.25)
    assert result['sample_count'] == 2 and result['stopped_by'] == 'duration'
    session.stop.assert_called_once()


def test_duration_reports_current_single_region_frames_with_incomplete_tail():
    payloads = [struct.pack('<BBI', index, 0, ts) + data for index, ts, data in (
        (0, 1, b'AAAA'), (1, 2, b'BBBB'), (0, 3, b'CCCC'))]
    transport, calls, bridge = sample_peer(payloads=payloads)
    result = dump_memory.capture_dump_stream(SimpleNamespace(_bridge=bridge),
        [{'address':0x20010000,'size':4},{'address':0x20020000,'size':4}], period=.001, frames=0, duration=.005)
    assert result['sample_count'] == 1 and result['incomplete_tail']
    assert [r['data_hex'] for r in result['samples'][0]['regions']] == ['41414141','42424242']
    assert [op for op,_ in calls] == [1,4,0x32,0x31]
