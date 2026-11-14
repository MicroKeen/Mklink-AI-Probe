"""SystemView report readers share one history and detect incomplete captures."""
import pytest
from mklink.remote.dashboards import SystemViewStreamManager


def test_independent_readers_open_at_tail_and_page_without_consuming_events():
    manager = SystemViewStreamManager()
    manager._process_events([{'kind': 'init'}], now=0)
    first = manager.read_history()
    second = manager.read_history()
    assert first['next_seq'] == 1 and first['points'] == []
    events = [{'kind': 'task_start_exec', 'task_id': n} for n in range(3)]
    manager._process_events(events, now=0)
    page = manager.read_history(first['session'], first['next_seq'], 2)
    assert [p['task_id'] for p in page['points']] == [0, 1]
    assert page['dropped'] == 0 and page['next_seq'] == 3
    tail = manager.read_history(page['session'], page['next_seq'])
    assert [p['task_id'] for p in tail['points']] == [2]
    assert len(manager.read_history(second['session'], second['next_seq'])['points']) == 3
    page['points'][0]['task_id'] = 99
    assert manager.get_history()[1]['task_id'] == 0
    assert all('capture_seq' not in e for e in events)


def test_eviction_reports_gaps_including_nonprefix_time_trimming():
    manager = SystemViewStreamManager()
    manager._history_buffer_us = 10
    cursor = manager.read_history()
    manager._process_events([{'kind': 'init'}, {'t_us': 0}, {'t_us': 20}], now=0)
    page = manager.read_history(cursor['session'], 0)
    assert [e['capture_seq'] for e in page['points']] == [1, 3]
    assert page['dropped'] == 1
    manager._max_history = 1
    manager._process_events([{'t_us': 21}, {'t_us': 22}], now=0)
    page = manager.read_history(cursor['session'], 3)
    assert page['next_seq'] == 5 and page['dropped'] == 1


def test_reset_invalidates_old_cursor_even_when_new_sequence_matches():
    manager = SystemViewStreamManager()
    before = manager.read_history()
    manager._reset_history()
    with pytest.raises(RuntimeError, match='capture changed'):
        manager.read_history(before['session'], 0)
    assert manager.read_history()['session'] != before['session']


def test_incremental_eviction_matches_legacy_with_metadata_and_time_regressions():
    import random
    from mklink.remote.systemview_history import SystemViewHistory
    rng = random.Random(581)
    history = SystemViewHistory()
    expected = []
    for index in range(3000):
        event = {'index': index}
        if index % 7:
            event['t_us'] = index + rng.randint(-80, 10)
        history.append(event)
        expected.append(event)
        if index % 13:
            continue
        latest = next((e['t_us'] for e in reversed(expected) if 't_us' in e), None)
        if latest is not None:
            expected = [e for e in expected if 't_us' not in e or e['t_us'] >= latest - 50]
        expected = expected[-70:]
        history.trim(max_count=70, window_us=50)
        assert list(history) == expected
        assert len(history) == len(expected)


def test_time_hint_reindexes_retained_events_and_reset_drops_old_index():
    from mklink.remote.systemview_history import SystemViewHistory
    history = SystemViewHistory()
    events = [{'t_ticks': value} for value in (0, 20)]
    for event in events:
        history.append(event)
        event['t_us'] = event['t_ticks']
    history.reindex_times()
    history.trim(max_count=10, window_us=10)
    assert list(history) == [events[1]]
    history.clear()
    history.append({'t_us': 1})
    history.trim(max_count=10, window_us=10)
    assert list(history) == [{'t_us': 1}]


def test_retained_history_is_not_rescanned_on_every_small_batch():
    from mklink.remote.systemview_history import SystemViewHistory
    class CountedEvent(dict):
        reads = 0
        def get(self, *args):
            CountedEvent.reads += 1
            return super().get(*args)
    history = SystemViewHistory()
    for index in range(100_000):
        history.append(CountedEvent(t_us=index))
    CountedEvent.reads = 0
    for index in range(100_000, 100_100):
        history.append(CountedEvent(t_us=index))
        history.trim(max_count=100_000, window_us=60_000_000)
    assert CountedEvent.reads == 100
    assert len(history) == 100_000
    assert next(iter(history))['t_us'] == 100


def test_timestamp_index_is_bounded_after_repeated_count_evictions():
    from mklink.remote.systemview_history import SystemViewHistory
    history = SystemViewHistory()
    for index in range(10_000):
        history.append({'t_us': index})
        history.trim(max_count=10, window_us=0)
    assert len(history) == 10
    assert len(history._heap) <= 2 * len(history) + 1024


@pytest.mark.parametrize('times', [[0, float('nan')], [float('nan'), 20],
                                  [float('inf'), 0], [0, float('-inf')]])
def test_nonfinite_times_keep_legacy_retention_semantics(times):
    from mklink.remote.systemview_history import SystemViewHistory
    history = SystemViewHistory()
    events = [{'kind': 'init'}, *[{'t_us': t} for t in times]]
    for event in events:
        history.append(event)
    cutoff = times[-1] - 10
    expected = [e for e in events if 't_us' not in e or e['t_us'] >= cutoff]
    history.trim(max_count=100, window_us=10)
    assert list(history) == expected


@pytest.mark.parametrize('arguments', [{'after': 0}, {'session': 'x'}, {'limit': 0},
                                      {'limit': 501}, {'limit': True}])
def test_invalid_cursor_arguments_are_rejected(arguments):
    with pytest.raises(ValueError):
        SystemViewStreamManager().read_history(**arguments)


def test_history_cursor_api_and_runtime_dispatch_use_same_manager(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from fastapi.testclient import TestClient
    from mklink.remote.api import create_app
    from mklink.remote import dashboards
    from mklink.runtime_api import install_runtime
    from test_shared_runtime import attach, call
    monkeypatch.setattr(dashboards, '_managers', {})
    monkeypatch.setattr('mklink.probes.inventory', lambda: [])
    app = create_app(project_root=str(tmp_path))
    app.state.mklink_state['device'] = SimpleNamespace(
        connected=True, port='TEST', axf_status={'loaded': False}, state=None,
        mcu_name='test', idcode=0, close=lambda: None)
    control = install_runtime(app, {'port': 8765, 'token': 'test-secret', 'instance_id': 'sv-history'})
    with TestClient(app, base_url='http://127.0.0.1:8765', headers={'X-Auth-Token': 'test-secret'}) as client:
        session = attach(client)
        cursor = call(client, session, 'systemview_capture_history').json()
        manager = dashboards.get_managers()['systemview']
        manager._process_events([{'kind': 'task_start_exec', 'task_id': 7}], now=0)
        args = {'session': cursor['session'], 'after': cursor['next_seq']}
        result = call(client, session, 'systemview_capture_history', args)
        assert result.status_code == 200, result.text
        assert result.json()['points'][0]['task_id'] == 7
        assert client.get('/api/dash/systemview/history').json()['points'][0]['task_id'] == 7
        assert call(client, session, 'systemview_capture_history', {'after': 0}).status_code == 422
        manager._reset_history()
        assert call(client, session, 'systemview_capture_history', args).status_code == 409
        client.post('/_runtime/detach', json={'session_id': session})
        assert not control.sessions
