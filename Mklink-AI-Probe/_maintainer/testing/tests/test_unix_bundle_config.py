import importlib.util
import json
from pathlib import Path

import pytest


@pytest.mark.parametrize('system', ['Darwin', 'Linux'])
def test_native_candidate_signing_is_scoped_and_config_is_restored(tmp_path, monkeypatch, system):
    directory = Path(__file__).resolve().parents[3] / 'skills/tauri-gui-builder/scripts'
    monkeypatch.syspath_prepend(str(directory))
    spec = importlib.util.spec_from_file_location('review_unix_builder', directory / 'build_unix.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = {'bundle': {'targets': ['nsis'], 'windows': {'nsis': {'installMode': 'currentUser'}},
                           'createUpdaterArtifacts': True, 'icon': ['icons/icon.ico', 'icons/32x32.png']}}
    path = tmp_path / 'tauri.conf.json'
    content = json.dumps(original).encode()
    path.write_bytes(content)
    with pytest.raises(RuntimeError, match='simulated build failure'):
        with module.unix_bundle_config(path, system):
            config = json.loads(path.read_text())
            assert config['bundle']['windows'] == original['bundle']['windows']
            if system == 'Darwin':
                assert config['bundle']['macOS']['signingIdentity'] == '-'
                assert config['bundle']['macOS']['hardenedRuntime'] is False
                assert config['bundle']['targets'] == ['app', 'dmg']
            else:
                assert 'macOS' not in config['bundle']
            raise RuntimeError('simulated build failure')
    assert path.read_bytes() == content
