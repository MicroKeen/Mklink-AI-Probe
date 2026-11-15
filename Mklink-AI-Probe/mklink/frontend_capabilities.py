"""Workbench access to the existing shared capability allowlist and handlers."""
from __future__ import annotations

import copy
import hashlib
import inspect
import json
import re
from urllib.parse import quote

from fastapi import APIRouter, Request
from pydantic import ValidationError, create_model
from starlette.concurrency import run_in_threadpool
from starlette.routing import compile_path

from .frontend_contract import bounded_json, identifier, keys, require
from .runtime_capabilities import CAPABILITIES

# Existing public GUI operations omitted from the shared call table. No URL comes from a layout.
GUI_OPERATIONS = {
    'device_connect': ('POST', '/api/device/connect'),
    'device_disconnect': ('POST', '/api/device/disconnect'),
    'device_reboot': ('POST', '/api/device/reboot'),
    'symbols_load': ('POST', '/api/device/parse-axf'),
    'symbols_browse': ('GET', '/api/symbols/browse'),
    'symbols_resolve': ('GET', '/api/symbols/resolve'),
    'configuration_description': ('GET', '/api/device/configuration'),
    'inspect_mcu': ('POST', '/api/mcu-detect'),
    'discover_probes': ('GET', '/api/ports/discover'),
    'set_probe_alias': ('POST', '/api/runtime/alias'),
    'select_probe': ('POST', '/api/runtime/select'),
    'uart_baudrates': ('POST', '/api/runtime/uart-baudrates'),
    'probe_firmware_check': ('GET', '/api/probe/firmware-check'),
    'probe_firmware_upgrade': ('POST', '/api/probe/firmware-upgrade'),
    'runtime_status': ('GET', '/api/runtime/control/status'),
    'runtime_volume': ('GET', '/api/runtime/control/volume'),
    'runtime_detach_client': ('POST', '/api/runtime/control/detach-client'),
    'runtime_stop_acquisition': ('POST', '/api/runtime/control/stop-acquisition'),
    'runtime_release_device': ('POST', '/api/runtime/control/release-device'),
    'runtime_stop_backend': ('POST', '/api/runtime/control/stop-backend'),
    'job_start': ('POST', '/api/runtime/jobs/'),
    'jobs': ('GET', '/api/runtime/jobs/'),
    'job_status': ('GET', '/api/runtime/jobs/{job_id}'),
    'security_status': ('GET', '/api/online-flash/targets/{part_number}/security'),
    'flash_targets': ('GET', '/api/online-flash/targets'),
    'flash_algorithms': ('GET', '/api/online-flash/algorithms'),
    'flash_algorithm_remove': ('DELETE', '/api/online-flash/algorithms/{algorithm_id}'),
    'flash_target_algorithms': ('GET', '/api/online-flash/targets/{part_number}/algorithms'),
    'flash_target_memory_map': ('GET', '/api/online-flash/targets/{part_number}/memory-map'),
    'flash_image_inspect': ('POST', '/api/online-flash/images/inspect-path'),
    'flash_image_source_status': ('GET', '/api/online-flash/images/source-status'),
    'flash_image_preview': ('GET', '/api/online-flash/images/{image_id}/preview'),
    'flash_job_start': ('POST', '/api/online-flash/jobs'),
    'flash_jobs': ('GET', '/api/online-flash/jobs/active'),
    'flash_job': ('GET', '/api/online-flash/jobs/{job_id}'),
    'flash_job_stop': ('POST', '/api/online-flash/jobs/{job_id}/stop'),
    'flash_memory_read': ('POST', '/api/online-flash/memory/read'),
    'pack_status': ('GET', '/api/online-flash/packs/status'),
    'pack_index_update': ('POST', '/api/online-flash/packs/index/update'),
    'pack_install': ('POST', '/api/online-flash/packs/install'),
    'pack_cancel': ('POST', '/api/online-flash/packs/cancel'),
    'pack_remove': ('DELETE', '/api/online-flash/packs/{pack_id}/{version}'),
    'offline_algorithms': ('GET', '/api/offline-download/algorithms'),
    'offline_security': ('GET', '/api/offline-download/security'),
    'project': ('GET', '/api/project'),
    'project_root': ('GET', '/api/project-root'),
    'project_init': ('POST', '/api/project-init'),
    'config_read': ('GET', '/api/config'),
    'config_save': ('PUT', '/api/config'),
    'config_status': ('GET', '/api/config/status'),
    'profiles': ('GET', '/api/profiles'),
    'project_history': ('GET', '/api/project-history'),
    'project_history_save': ('POST', '/api/project-history'),
    'project_history_remove': ('DELETE', '/api/project-history'),
    'project_browse': ('GET', '/api/project-root/browse'),
    'ports': ('GET', '/api/ports'),
    'flash_probes': ('GET', '/api/online-flash/probes'),
    'microkeen': ('GET', '/api/microkeen'),
    'health': ('GET', '/api/health'),
    'site_agent_status': ('GET', '/api/site-agent/status'),
    'dash_conflict_check': ('GET', '/api/dash/conflict-check'),
    'superwatch_inspect': ('GET', '/api/dash/superwatch/inspect'),
    'modbus_read': ('POST', '/api/dash/modbus/read'),
    'modbus_write': ('POST', '/api/dash/modbus/write'),
    'rtt_config': ('GET', '/api/rtt-config'),
    'rtt_config_save': ('PUT', '/api/rtt-config'),
    'rtt_find': ('POST', '/api/rtt-find'),
    'rtt_encoding': ('POST', '/api/dash/rtt/encoding'),
    'systemview_recording_start': ('POST', '/api/dash/systemview/recording/start'),
    'systemview_recording_stop': ('POST', '/api/dash/systemview/recording/stop'),
    'systemview_logs': ('GET', '/api/dash/systemview/logs'),
    'vofa_interval': ('POST', '/api/dash/vofa/interval'),
    'resources_release': ('POST', '/api/resources/release'),
    'resources_release_serial': ('POST', '/api/resources/release-serial'),
    'resources_release_all': ('POST', '/api/resources/release-all'),
    'diagnostic_events': ('POST', '/api/runtime/diagnostics/events'),
}


def panel_operations():
    return {**CAPABILITIES, **GUI_OPERATIONS}


def offline_tools():
    from types import SimpleNamespace
    from .mcp_analysis import register_systemview_offline_tools
    from .mcp_configuration import register_configuration_offline_tools
    functions = {}

    def register(function):
        fields = {name: (parameter.annotation, ... if parameter.default is inspect.Parameter.empty else parameter.default)
                  for name, parameter in inspect.signature(function).parameters.items()}
        functions[function.__name__] = (function, create_model(function.__name__, __config__={'extra': 'forbid', 'strict': True}, **fields))
        return function

    registry = SimpleNamespace(tool=lambda: register)
    register_systemview_offline_tools(registry)
    register_configuration_offline_tools(registry)
    return functions


def capability_catalog(app):
    operations = {}

    def collect(application, prefix=''):
        if not hasattr(application, 'openapi'):
            return
        schema = application.openapi()
        definitions = schema.get('components', {}).get('schemas', {})

        def expand(value, seen=()):
            if isinstance(value, list):
                return [expand(item, seen) for item in value]
            if not isinstance(value, dict):
                return value
            ref = value.get('$ref', '').removeprefix('#/components/schemas/')
            if ref in definitions and ref not in seen:
                return expand(definitions[ref], (*seen, ref))
            return {key: expand(item, seen) for key, item in value.items()}

        # OpenAPI includes nested routers even when FastAPI keeps opaque route wrappers.
        for path, methods in schema.get('paths', {}).items():
            for method, operation in methods.items():
                if method not in ('get', 'post', 'put', 'patch', 'delete', 'head', 'options'):
                    continue
                full_path = prefix + path
                operations[(method.upper(), full_path)] = (compile_path(full_path)[0], expand(operation))
        for route in application.routes:
            if hasattr(route, 'app') and hasattr(route.app, 'routes'):
                collect(route.app, prefix + route.path)

    collect(app)
    result = []
    for name, (method, path) in panel_operations().items():
        found = operations.get((method, path))
        if found is None:
            found = next((entry for (verb, pattern), entry in operations.items()
                          if verb == method and '{' in pattern and entry[0].fullmatch(path)), None)
        operation = found[1] if found else {}
        operation = {**operation, 'parameters': [parameter for parameter in operation.get('parameters', [])
                     if parameter['in'] != 'path' or '{' + parameter['name'] + '}' in path]}
        if name in ('offline_deploy', 'job_start'):
            properties = {'request_id': {'type': 'string', 'minLength': 1, 'maxLength': 128},
                          'confirm': {'type': 'boolean', 'const': True}}
            if name == 'offline_deploy':
                properties['config'] = {'type': 'object', 'description': 'Existing offline download configuration; file uploads use the original GUI.'}
            else:
                from .runtime_jobs import PATHS
                properties.update(action={'type': 'string', 'enum': list(PATHS)}, arguments={'type': 'object'})
            operation['requestBody'] = {'required': True, 'content': {'application/json': {'schema': {
                'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}}}}
        if name == 'flash_job_start':
            operation = {**operation, 'parameters': [*operation.get('parameters', []),
                {'name': 'request_id', 'in': 'arguments', 'required': True, 'schema': {'type': 'string', 'maxLength': 128},
                 'description': 'Stable submission ID; transported in X-MKLink-Request-Id, not the job body.'}]}
        contract = {'method': method, 'path': path, 'parameters': operation.get('parameters', []),
                    'requestBody': operation.get('requestBody')}
        result.append({'name': name, 'method': method, 'path': path, 'available': found is not None,
                       'description': operation.get('description') or operation.get('summary') or name,
                       'parameters': operation.get('parameters', []),
                       'requestBody': operation.get('requestBody'),
                       'revision': hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest(),
                       'effect': 'device' if method != 'GET' or path.startswith('/api/device/') else 'view'})
    for name, (function, model) in offline_tools().items():
        if name in panel_operations():
            continue
        schema = model.model_json_schema()
        result.append({'name': name, 'method': 'OFFLINE', 'path': '', 'available': True,
                       'description': inspect.getdoc(function), 'parameters': [],
                       'requestBody': {'content': {'application/json': {'schema': schema}}}, 'effect': 'view',
                       'revision': hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()})
    return {'capabilities': result, 'count': len(result),
            'guidance': 'Use the published capability arguments. Existing device, job, confirmation and identity guards still apply. A returned job is not its completion.'}


def install_capability_panel(app, control, broker, read_body):
    router = APIRouter(prefix='/api/runtime/capabilities')
    cached = None

    @router.get('')
    async def catalog():
        nonlocal cached
        if cached is None:
            cached = capability_catalog(app)
        return copy.deepcopy(cached)

    @router.post('/call')
    async def call(request: Request):
        session = request.headers.get('X-MKLink-Frontend-Session')
        require(identifier(session), message='A current frontend target session is required')
        broker.check_target(session)
        body = await read_body(request, 1024 * 1024 + 4096)
        keys(body, {'capability', 'arguments'})
        name, arguments = body['capability'], body['arguments']
        local = offline_tools()
        require(isinstance(name, str) and name in panel_operations().keys() | local.keys(), message='Unsupported MKLink capability')
        require(isinstance(arguments, dict), message='Capability arguments must be an object')
        if name in CAPABILITIES:
            arguments = control.prepare_arguments(name, arguments)
        else:
            bounded_json(arguments, limit=64 * 1024)
        if name in local and name not in panel_operations():
            function, model = local[name]
            if name == 'systemview_analyze_events':
                require(isinstance(arguments.get('events'), list) and all(isinstance(event, dict) for event in arguments['events']),
                        message='SystemView events must be a list of event objects')
            try:
                validated = model.model_validate(arguments).model_dump()
                result = await run_in_threadpool(function, **validated)
            except (ValidationError, ValueError, TypeError) as exc:
                require(False, message=str(exc))
            broker.check_target(session)
            return result
        method, path = panel_operations()[name]
        arguments = dict(arguments)
        request_id = None
        if name == 'flash_job_start':
            request_id = arguments.pop('request_id', None)
            require(isinstance(request_id, str) and 1 <= len(request_id) <= 128, message='A stable request_id is required')
        for key in re.findall(r'\{(\w+)\}', path):
            value = arguments.pop(key, None)
            require(isinstance(value, str) and 1 <= len(value) <= 512 and not any(char in value for char in '/\\?#\x00')
                    and value not in ('.', '..'), message=f'Invalid path parameter: {key}')
            path = path.replace('{' + key + '}', quote(value, safe=''))
        # The inner request must retain the original target fence, including after awaits.
        return await control.invoke(method, path, arguments, frontend_session=session, request_id=request_id)

    app.router.routes[0:0] = router.routes
