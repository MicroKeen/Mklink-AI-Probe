import json
from types import SimpleNamespace

import pytest

from mklink.watch_profile import WatchProfile
from mklink.watch_preferences import PreferencesConflict


def manager(tmp_path, names=('gain',), offset=0):
    from mklink.remote.dashboards import SuperWatchStreamManager
    from mklink.dwarf_parser import DwarfInfo, DwarfVariable
    from mklink.symbol_catalog import SymbolCatalog
    info = DwarfInfo(base_types={1: ('float', 4)}, variables={
        name: DwarfVariable(name, i, 1, 0x20000000 + offset + i * 4, 4, 'float')
        for i, name in enumerate(names)})
    symbols = tmp_path / 'symbols.axf'
    symbols.touch()
    device = SimpleNamespace(symbol_catalog=SymbolCatalog.from_dwarf(info, axf_path=str(symbols),
        ram_ranges=[(0x20000000, 0x20010000)]), _dwarf_info=info)
    result = SuperWatchStreamManager()
    result.prepare(device)
    return result


def test_create_save_and_restore_names_against_new_catalog(tmp_path):
    axf = tmp_path / 'app.axf'
    axf.write_bytes(b'symbols')
    store = WatchProfile()
    sw = manager(tmp_path)
    store.activate(str(axf), sw)
    path = tmp_path / 'app.axf.superwatch.json'
    assert path.is_file()
    store.save('selected', ['gain', 'missing'])
    view = store.section('viewer')
    store.save('viewer', {**view['viewer'], 'bufferPoints': 500000, 'interval': .000001}, view['revision'])
    fresh = WatchProfile()
    rebound = manager(tmp_path, offset=64)
    fresh.activate(str(axf), rebound)
    assert rebound.list_watches()[0]['address'] == '0x20000040'
    assert fresh.status()['missing'] == ['missing']
    assert rebound._interval == .000001 and not rebound.running
    assert fresh.section('viewer')['viewer']['bufferPoints'] == 500000
    assert 'address' not in path.read_text()


def test_file_isolation_and_stale_window_cannot_overwrite(tmp_path):
    store = WatchProfile()
    sw = manager(tmp_path)
    for name in ('a.axf', 'b.elf'):
        (tmp_path / name).touch()
    store.activate(str(tmp_path / 'a.axf'), sw)
    old = store.section('workspace')
    store.save('selected', ['gain'])
    store.activate(str(tmp_path / 'b.elf'), sw)
    assert sw.list_watches() == []
    with pytest.raises(PreferencesConflict):
        store.save('workspace', old['workspace'], old['revision'])
    store.activate(str(tmp_path / 'a.axf'), sw)
    assert len(sw.list_watches()) == 1


def test_corrupt_and_external_changed_config_are_preserved(tmp_path):
    axf = tmp_path / 'bad.elf'
    axf.touch()
    path = tmp_path / 'bad.elf.superwatch.json'
    path.write_text('{broken')
    store = WatchProfile()
    store.activate(str(axf), manager(tmp_path))
    assert store.status()['error']
    with pytest.raises(ValueError):
        store.save('selected', ['gain'])
    assert path.read_text() == '{broken'
    path.unlink()
    store.activate(str(axf), manager(tmp_path))
    path.write_text('external edit')
    with pytest.raises(PreferencesConflict):
        store.save('selected', ['gain'])
    assert path.read_text() == 'external edit'


def test_viewer_whitelist_and_invalid_values(tmp_path):
    axf = tmp_path / 'app.axf'
    axf.touch()
    store = WatchProfile()
    store.activate(str(axf), manager(tmp_path))
    store.save('viewer', {'bufferPoints': 60000, 'interval': .002,
        'channels': [{'name': 'gain', 'address': 123, 'type': 'old', 'color': '#123456'}]})
    assert store.section('viewer')['viewer']['channels'] == [{'name': 'gain', 'color': '#123456'}]
    for bad in ({'bufferPoints': 2}, {'interval': float('nan')}, {'interval': 0},
                {'globalYView': {'zoom': {}}}, {'channels': [{'name': 'gain', 'color': 1}]}):
        with pytest.raises(ValueError):
            store.save('viewer', bad)


def test_gui_and_capability_routes_share_one_profile(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from mklink.remote.api import create_app
    from mklink.remote.dashboards import get_managers
    from mklink.runtime_capabilities import CAPABILITIES
    app = create_app(auth_token=None, project_root=str(tmp_path))
    sw = get_managers()['superwatch']
    prepared = manager(tmp_path)
    device = prepared._device
    axf = tmp_path / 'symbols.axf'
    device.axf_status = {'loaded': True, 'axf_path': str(axf)}
    device.connected = False
    app.state.mklink_state['symbol_device'] = device
    sw.prepare(device)
    monkeypatch.setattr(sw, 'reparse_symbols', lambda *a, **kw: {})
    with TestClient(app) as client:
        result = client.post('/api/device/parse-axf', json={'axf': str(axf)})
        assert result.status_code == 200, result.text
        assert axf.with_name(axf.name + '.superwatch.json').is_file()
        def call(action, data=None):
            method, route = CAPABILITIES['superwatch_' + action]
            return client.request(method, route, **({'json': data} if data else {}))
        initial = call('profile').json()
        result = call('add', {'name': 'gain', 'profile': initial['path']})
        assert result.status_code == 200 and not result.json().get('error')
        assert app.state.watch_profile.data['selected'] == ['gain']
        assert call('interval', {'interval': .000001}).status_code == 200
        # The same user's pending display save is not invalidated by interval.
        view = initial['viewer']
        result = call('profile_save', {'section': 'viewer', 'revision': view['revision'],
            'value': {**view['viewer'], 'bufferPoints': 500000}})
        assert result.status_code == 200, result.text
        assert result.json()['viewer']['interval'] == .000001
        workspace = call('workspace').json()
        workspace['workspace']['signals'] = {'gain': {'alias': '增益', 'color': '#123456'}}
        assert call('workspace_save', workspace).status_code == 200
        pins = call('pins').json()
        assert call('pins_save', {'pins': ['gain'], 'revision': pins['revision']}).status_code == 200
        saved = json.loads(axf.with_name(axf.name + '.superwatch.json').read_text(encoding='utf-8'))
        assert saved['viewer']['bufferPoints'] == 500000 and saved['viewer']['interval'] == .000001
        assert saved['workspace']['signals']['gain']['alias'] == '增益' and saved['pins'] == ['gain']
        stale = call('remove', {'name': 'gain', 'profile': 'another.elf.superwatch.json'})
        assert stale.status_code == 409 and len(sw.list_watches()) == 1
        assert call('interval', {'interval': .01, 'profile': 'another'}).status_code == 409
        assert sw._interval == .000001


def test_read_only_failure_is_visible_without_breaking_symbol_use(tmp_path, monkeypatch):
    from pathlib import Path
    axf = tmp_path / 'app.axf'
    axf.touch()
    original = Path.open
    def deny(path, mode='r', *args, **kwargs):
        if mode == 'xb' and path.name.endswith('.tmp'):
            raise PermissionError('directory read-only')
        return original(path, mode, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', deny)
    store = WatchProfile()
    sw = manager(tmp_path)
    store.activate(str(axf), sw)
    assert not store.status()['available'] and 'read-only' in store.status()['error']
    assert not sw.add_watch('gain').get('error')
    assert axf.read_bytes() == b''


def test_queued_display_write_preserves_latest_interval(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    axf = tmp_path / 'app.axf'
    axf.touch()
    store = WatchProfile()
    store.activate(str(axf), manager(tmp_path))
    initial = store.section('viewer')
    with ThreadPoolExecutor() as pool:
        with store.lock:
            pending = pool.submit(store.save_display, 'viewer',
                                  {**initial['viewer'], 'bufferPoints': 100000}, initial['revision'])
            store.save('viewer', {**initial['viewer'], 'interval': .00001})
        assert pending.result()['viewer']['interval'] == .00001
    assert json.loads(store.path.read_text())['viewer']['interval'] == .00001


def test_array_range_is_rebound_without_saved_addresses(tmp_path):
    from mklink.dwarf_parser import DwarfInfo, DwarfVariable
    from mklink.symbol_catalog import SymbolCatalog
    axf = tmp_path / 'app.elf'
    axf.touch()
    sw = manager(tmp_path)
    info = DwarfInfo(base_types={1: ('float', 4)}, arrays={2: (1, 64)}, variables={
        'wave': DwarfVariable('wave', 3, 2, 0x20000100, 64, 'float[]')})
    sw._device.symbol_catalog = SymbolCatalog.from_dwarf(info, axf_path=str(axf),
        ram_ranges=[(0x20000000, 0x20010000)])
    sw._device._dwarf_info = info
    sw.prepare(sw._device)
    assert 'error' not in sw.select_array_snapshot('wave', start_index=2, count=4)
    store = WatchProfile()
    store.activate(str(axf), sw)
    store.save('snapshot', {'name': 'wave', 'start_index': 2, 'count': 4})
    store.activate(str(axf), sw)
    restored = sw.get_array_snapshot()['snapshot']
    assert restored['name'] == 'wave' and restored['start_index'] == 2 and restored['count'] == 4
    assert not sw.running and 'address' not in store.path.read_text()
