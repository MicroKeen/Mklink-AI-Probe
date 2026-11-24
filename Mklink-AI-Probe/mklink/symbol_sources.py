"""Find previously opened, backend-local symbol files for a browser upload."""
import hashlib
import json
import os
from pathlib import Path
import tempfile


class AmbiguousSymbolSource(ValueError):
    pass


def _directory(root, name):
    key = hashlib.sha256(os.path.normcase(name).encode('utf-8')).hexdigest()
    return Path(root).resolve() / '.mklink' / 'symbol-sources' / key


def remember_source(root, source):
    path = Path(source).resolve()
    uploads = Path(root).resolve() / '.mklink' / 'uploads'
    if path.is_relative_to(uploads) or not path.is_file():
        return
    directory = _directory(root, path.name)
    key = hashlib.sha256(os.path.normcase(str(path)).encode('utf-8')).hexdigest()
    record = directory / (key + '.json')
    # Immutable per path; simultaneous instances can register the same source.
    if record.is_file():
        return
    directory.mkdir(parents=True, exist_ok=True)
    stream = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=directory,
                                         suffix='.tmp', delete=False)
    temporary = Path(stream.name)
    try:
        with stream:
            json.dump(str(path), stream, ensure_ascii=False)
        os.replace(temporary, record)
    finally:
        temporary.unlink(missing_ok=True)


def match_upload(root, uploaded):
    directory = _directory(root, uploaded['name'])
    from mklink.project_config import load_project_info

    # Existing installations may already have a project and sidecar, before
    # the per-workspace list of explicitly opened files was introduced.
    project = load_project_info(str(root)) or {}
    candidates = {Path(root).resolve() / uploaded['name']}
    for key in ('axf_path', 'elf_path', 'out_path'):
        if isinstance(project.get(key), str) and project[key]:
            candidates.add((Path(root) / project[key]).resolve())
    for record in directory.glob('*.json'):
        try:
            candidates.add(Path(json.loads(record.read_text(encoding='utf-8'))))
        except (ValueError, TypeError, OSError):
            continue
    matches = set()
    for path in candidates:
        try:
            if (not path.is_absolute() or os.path.normcase(path.name) != os.path.normcase(uploaded['name'])
                    or path.stat().st_size != uploaded['size']):
                continue
            with path.open('rb') as source:
                digest = hashlib.sha256()
                for chunk in iter(lambda: source.read(1024 * 1024), b''):
                    digest.update(chunk)
            if digest.hexdigest() == uploaded['sha256']:
                matches.add(str(path))
        except (ValueError, TypeError, OSError):
            continue
    if len(matches) > 1:
        raise AmbiguousSymbolSource('同一份符号文件对应多个已打开的工程。请在“配置 → 文件来源”输入所需工程的 AXF/ELF 完整路径，然后点击“解析符号”。\n'
                                    + '\n'.join(sorted(matches)))
    return {**uploaded, 'path': next(iter(matches)), 'source_kind': 'local'} if matches else uploaded
