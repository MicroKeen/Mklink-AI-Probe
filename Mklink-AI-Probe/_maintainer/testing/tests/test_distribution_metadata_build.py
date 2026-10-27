import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest


def load_builder():
    path = Path(__file__).resolve().parents[3] / 'skills/tauri-gui-builder/scripts/build.py'
    spec = importlib.util.spec_from_file_location('metadata_builder', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_refresh_replaces_stale_editable_metadata_and_controls_freezer_lookup(tmp_path):
    builder = load_builder()
    builder.SKILL_DIR = tmp_path
    (tmp_path / 'pyproject.toml').write_text('''[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"
[project]
name = "mklink"
version = "9.8.7"
[tool.setuptools]
packages = ["mklink"]
''', encoding='utf-8')
    (tmp_path / 'mklink').mkdir()
    (tmp_path / 'mklink/__init__.py').write_text('')
    (tmp_path / 'mklink.egg-info').mkdir()
    (tmp_path / 'mklink.egg-info/PKG-INFO').write_text('Name: mklink\nVersion: 0.3.6\n')
    env = builder.refresh_distribution_metadata()
    result = subprocess.run([sys.executable, '-c', 'import importlib.metadata; print(importlib.metadata.version("mklink"))'],
                            cwd=tmp_path.parent, env=env, text=True, capture_output=True, check=True)
    assert result.stdout.strip() == '9.8.7'
    assert env['PYTHONPATH'].split(os.pathsep)[0] == str(tmp_path)


def test_build_rejects_metadata_that_was_not_refreshed(tmp_path, monkeypatch):
    builder = load_builder()
    builder.SKILL_DIR = tmp_path
    (tmp_path / 'pyproject.toml').write_text('[project]\nversion="9.8.7"\n')
    (tmp_path / 'mklink.egg-info').mkdir()
    (tmp_path / 'mklink.egg-info/PKG-INFO').write_text('Name: mklink\nVersion: 0.3.6\n')
    monkeypatch.setattr(builder, 'run', lambda *args, **kwargs: 0)
    with pytest.raises(RuntimeError, match='does not match'):
        builder.refresh_distribution_metadata()
