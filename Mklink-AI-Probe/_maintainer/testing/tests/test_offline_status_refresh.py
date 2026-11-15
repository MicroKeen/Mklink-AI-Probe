from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mklink.firmware_check import Version
from mklink.remote.offline_download_api import create_offline_download_router


def test_passive_status_caches_only_version_and_refreshes_after_removal(monkeypatch, tmp_path):
    app = FastAPI()
    app.include_router(create_offline_download_router(SimpleNamespace(), None))
    app.state.shared_runtime = SimpleNamespace(info={'probe_id': 'one'})
    selected = {'probe_id': 'one', 'port': 'COM1'}
    present = [True]
    clock = [0.0]
    monkeypatch.setattr('mklink.remote.offline_download_api.time', SimpleNamespace(monotonic=lambda: clock[0]))
    reads, resolutions = [], []
    monkeypatch.setattr('mklink.probes.inventory', lambda: [selected] if present[0] else [])
    def select(_):
        if not present[0]:
            raise ConnectionError('removed')
        return selected
    monkeypatch.setattr('mklink.probes.select_probe', select)
    def resolve(probe):
        resolutions.append(probe)
        return {'root': tmp_path}
    monkeypatch.setattr('mklink.probe_volumes.resolve_volume', resolve)
    def version(root):
        reads.append(root)
        return Version(4, 7, 4)
    monkeypatch.setattr('mklink.firmware_check.read_microkeen_version', version)
    with TestClient(app) as client:
        for _ in range(3):
            assert client.get('/api/offline-download/status').json()['version'] == 'V4.7.4'
        assert len(reads) == 1 and len(resolutions) == 3
        assert client.get('/api/offline-download/status?refresh=true').json()['available']
        assert len(reads) == 2
        present[0] = False
        assert client.get('/api/offline-download/status').json()['available'] is False
        present[0] = True
        assert client.get('/api/offline-download/status').json()['available']
        assert len(reads) == 3
        clock[0] = 31
        assert client.get('/api/offline-download/status').json()['version'] == 'V4.7.4'
        assert len(reads) == 4
        selected['probe_id'] = 'two'
        assert client.get('/api/offline-download/status?probe=two').json()['version'] == 'V4.7.4'
        assert len(reads) == 5
