"""Read-only MCU inspection using the application's unified algorithm catalog."""
from __future__ import annotations

from typing import Callable
import re


def _algorithm_details(algorithm):
    return {
        'algorithm_id': algorithm.algorithm_id, 'name': algorithm.file_name,
        'size': algorithm.flash_size, 'flash_base': algorithm.flash_start,
        'ram_base': algorithm.ram_start, 'ram_size': algorithm.ram_size,
        'page_size': algorithm.page_size, 'sector_sizes': list(algorithm.sector_sizes),
        'source_kind': algorithm.source_kind, 'source_name': algorithm.source_name,
    }


def missing_algorithm_details(target: str, *, paths=None) -> dict:
    """Search the unified catalog; a search match never selects a flash target."""
    from mklink.cmsis_dap.pack_catalog import PackCatalog
    from mklink.cmsis_dap.paths import PackPaths
    from mklink.cmsis_dap.algorithm_catalog import discover_flash_algorithms

    query = target.strip()
    literals = [part for part in re.split(r'[xX*?]+', query) if part]
    matches = []
    if literals:
        needle = max(literals, key=len)
        pattern = re.compile(''.join(
            '[a-z0-9]' if c in 'xX?' else '[a-z0-9]*' if c == '*' else re.escape(c)
            for c in query), re.IGNORECASE)
        records = PackCatalog(paths or PackPaths()).search(needle, limit=10000)
        seen = set()
        for record in records:
            key = record.part_number.casefold()
            if key in seen or not pattern.search(record.part_number):
                continue
            seen.add(key)
            algorithms = discover_flash_algorithms(record.part_number, paths=paths)
            matches.append({'device': record.part_number, 'vendor': record.vendor,
                            'source': record.source, 'installed': record.installed,
                            'candidates': [_algorithm_details(a) for a in algorithms]})
            if len(matches) == 20:
                break
    if matches:
        return {'status': 'matches', 'target_candidates': [m['device'] for m in matches],
                'target_matches': matches, 'match_limit': 20,
                'message': 'Catalog search matches found; inspect_mcu(device=...) exposes '
                'their details. Compare their algorithms with '
                'the project target, IDE/Pack mapping and known device memory geometry, '
                'then inspect the matching target. Ask the user only if that evidence '
                'cannot resolve the remaining ambiguity. Search results do not select '
                'a programming target; narrow the query if more detail is needed.'}
    return {'status': 'unsupported',
            'message': 'No local catalog match. Try a shorter model fragment or wildcard '
            'with inspect_mcu, check the project/Pack mapping, then install its Pack '
            'or configure a compatible custom algorithm if needed.'}


def _read_idcode(port: str | None) -> int | None:
    if not port:
        return None
    from mklink.runtime import query_probe
    return query_probe('probe_idcode', port=port)['idcode']


def inspect_mcu(*, project_root=".", device=None, flm=None, port=None,
                read_idcode=False, idcode_reader: Callable | None = None, paths=None):
    """Inspect a target or search model fragments/wildcards without changing devices.

    ``flm`` selects an algorithm ID or an unambiguous filename. IDCODE is optional
    diagnostic data, never used to guess an exact target or choose an algorithm.
    """
    from mklink.project_config import load_project_info
    from mklink.hpm_config import is_hpm_target
    from mklink.cmsis_dap.algorithm_catalog import discover_flash_algorithms

    project = (load_project_info(project_root) or {}) if not device else {}
    target = str(device or project.get('device') or project.get('target_part') or '').strip()
    if not target:
        return {'status': 'error', 'message': 'Specify --device or initialize a project with an exact target'}
    result = {'device': target, 'profile_written': False, 'flm_copied': False}
    if is_hpm_target(target):
        if flm:
            return {**result, 'status': 'error', 'message': 'HPM uses ROM API; FLM selection is unsupported'}
        result.update(status='detected', backend='hpm-rom', candidates=[])
    else:
        algorithms = discover_flash_algorithms(target, paths=paths)
        candidates = [_algorithm_details(a) for a in algorithms]
        result.update(backend='flm', candidates=candidates)
        if not candidates:
            result.update(missing_algorithm_details(target, paths=paths))
            if read_idcode:
                result['idcode'] = (idcode_reader or _read_idcode)(port)
            return result
        selected = candidates
        if flm:
            key = str(flm).casefold()
            selected = [c for c in candidates if key in {c['algorithm_id'].casefold(), c['name'].casefold()}]
            if not selected:
                return {**result, 'status': 'error', 'message': 'Requested algorithm is not a candidate for this target'}
        if len(selected) != 1:
            result.update(status='needs_selection', message='Select an explicit algorithm_id; inspection does not choose by order')
        else:
            result.update(status='detected', selected_algorithm=selected[0])
    if read_idcode:
        result['idcode'] = (idcode_reader or _read_idcode)(port)
    return result
