"""Inventory the real registries without connecting hardware or running CLI commands."""
import argparse
import asyncio
import json
from pathlib import Path
import re
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from mklink.frontend_capabilities import capability_catalog, panel_operations
from mklink.runtime_capabilities import CAPABILITIES

# Wrapper aliases keep their original preconditions and nested action arguments.
MCP_ALIASES = {
    'list_target_profiles': 'target_profile_catalog',
    'ping': 'health gui_frontend_capabilities', 'gui_open': 'gui_windows gui_present',
    'gui_control': 'gui_windows gui_action gui_snapshot', 'gui_call': 'gui_frontend_capabilities',
    'connect': 'device_connect', 'disconnect': 'device_disconnect', 'detach': 'runtime_detach_client',
    'reboot_probe': 'device_reboot', 'get_power': 'power_read', 'search_symbols': 'symbol_search',
    'runtime_control': 'runtime_status runtime_stop_acquisition runtime_release_device runtime_stop_backend',
    'probe_firmware': 'probe_firmware_check probe_firmware_upgrade',
    'offline_download': 'offline_status offline_preview offline_deploy job_start',
    'hpm_otp': 'hpm_otp_jtag_read hpm_otp_jtag_plan hpm_otp_jtag_program hpm_otp_jtag_lock_plan hpm_otp_jtag_lock_program hpm_otp_isp_read hpm_otp_isp_plan hpm_otp_isp_program hpm_otp_isp_batch_plan hpm_otp_isp_batch_program',
    'security_lock': 'job_start', 'security_unlock': 'job_start', 'start_job': 'job_start',
    'rtt_write_hex': 'rtt_write',
    'superwatch': ' '.join('superwatch_' + action for action in ('status items values snapshot snapshot_select snapshot_clear add remove sampling start stop pause resume interval write recording_start recording_stop recording_status recording_export profile profile_save workspace workspace_save pins pins_save').split()),
    'systemview': ' '.join('systemview_' + action for action in 'status history start stop pause resume'.split()),
}
CLI_ALIASES = {
    'target-profiles': 'target_profile_catalog',
    'version': 'probe_version', 'gui': 'gui_windows gui_present gui_action', 'break': 'breakpoints',
    'configuration': 'configuration_description read_configuration configuration_script',
    'debug-speed': 'debug_speed set_debug_speed', 'device-status': 'device_status',
    'dump': 'capture_dump', 'dump-benchmark': 'measure_dump_memory', 'dump-memory': 'dump_memory',
    'erase': 'job_start', 'flash': 'flash_image_inspect flash_job_start flash_job', 'flush-memory': 'flush_memory',
    'hardfault': 'hardfault_check hardfault_decode fault_snapshot', 'mcu-detect': 'inspect_mcu',
    'memmap': 'memory_map', 'peripherals': 'peripheral_targets select_peripherals list_peripherals capture_peripherals',
    'power-read': 'power_read', 'probes': 'discover_probes', 'probes alias': 'set_probe_alias',
    'project-info': 'project', 'project-init': 'project_init', 'read-flash': 'read_memory',
    'read-ram': 'read_memory', 'read-reg': 'read_register', 'read-variable': 'read_variable',
    'reload-symbols': 'symbol_reload_sources', 'reset': 'job_start', 'security': 'security_status job_start',
    'resource': 'resources resources_release_all resources_release_serial', 'resources': 'resources resources_release_all resources_release_serial',
    'rtt': 'rtt_start rtt_history rtt_stop', 'rtt-find': 'rtt_find',
    'superwatch': 'superwatch_start superwatch_values superwatch_stop', 'systemview': 'systemview_start systemview_history systemview_stop',
    'systemview-analyze': 'systemview_analyze_events', 'symbols': 'symbol_search', 'typeinfo': 'symbol_typeinfo',
    'vofa': 'vofa_start vofa_history vofa_stop', 'write-ram': 'write_memory', 'write-variable': 'write_variable',
    'serial list': 'uart_ports', 'serial open': 'serial_start', 'serial send': 'serial_send',
    'serial log': 'serial_recording_start serial_recording_stop', 'serial monitor': 'serial_start serial_history',
    'serial dashboard': 'serial_status serial_start serial_history serial_send serial_stop',
    'modbus read': 'modbus_transaction', 'modbus write': 'modbus_transaction', 'modbus scan': 'modbus_probe',
    'modbus poll': 'modbus_loop_start modbus_loop_stop', 'modbus diag': 'modbus_probe',
    'modbus monitor': 'modbus_start modbus_history', 'modbus dashboard': 'modbus_start modbus_history modbus_transaction',
    'runtime status': 'runtime_status', 'runtime jobs': 'jobs job_status', 'runtime firmware': 'probe_firmware_check probe_firmware_upgrade',
    'runtime control': 'runtime_status runtime_stop_acquisition runtime_release_device runtime_stop_backend',
    'runtime call': 'gui_frontend_capabilities',
}


def inventory(project):
    from mklink.remote.api import create_app
    from mklink.runtime_api import install_runtime
    from mklink.runtime_mcp import build_server
    from mklink.remote.cli import build_parser
    from mklink.cli import main
    app = create_app(auth_token='inventory-only', project_root=str(project))
    install_runtime(app, {'instance_id': 'inventory', 'runtime_id': 'inventory', 'port': 8765, 'token': 'inventory-only'})
    catalog = capability_catalog(app)['capabilities']
    assert all(item['available'] for item in catalog), 'A panel operation no longer resolves to a real route'
    names = {item['name'] for item in catalog}
    commands = {}
    def visit(parser, prefix=''):
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                for name, child in action.choices.items():
                    key = (prefix + ' ' + name).strip()
                    commands[key] = {'group': any(isinstance(item, argparse._SubParsersAction) for item in child._actions),
                                     'parameters': [{'name': item.dest, 'flags': item.option_strings,
                                                     'required': item.required, 'choices': list(item.choices) if item.choices else None}
                                                    for item in child._actions if item.dest not in ('help', argparse.SUPPRESS)]}
                    visit(child, key)
    class Captured(Exception):
        pass
    def capture(parser, *args, **kwargs):
        visit(parser)
        raise Captured()
    with patch.object(argparse.ArgumentParser, 'parse_args', capture), patch.object(sys, 'argv', ['mklink']):
        try:
            main()
        except Captured:
            pass
    visit(build_parser(), 'remote')
    async def tools():
        from fastmcp import Client
        async with Client(build_server()) as client:
            return {tool.name: tool.inputSchema for tool in await client.list_tools()}
    mcp_schemas = asyncio.run(tools())
    mcp = {}
    for name in sorted(mcp_schemas):
        target = name if name in names else MCP_ALIASES[name]
        assert set(target.split()) <= names, (name, target)
        mcp[name] = target
    cli = {}
    for name, command in sorted(commands.items()):
        target = CLI_ALIASES.get(name, name.replace('-', '_') if name.replace('-', '_') in names else '')
        if not target and name.split()[0] in ('security', 'resource', 'resources', 'probes'):
            target = CLI_ALIASES[name.split()[0]]
        assert set(target.split()) <= names, (name, target)
        cli[name] = {'mode': 'group' if command['group'] else 'panel' if target else 'agent-cli', 'target': target,
                     'parameters': command['parameters']}
    http = {}
    def collect(application, prefix=''):
        if not hasattr(application, 'openapi'):
            return
        for path, methods in application.openapi().get('paths', {}).items():
            for method in methods:
                if method not in ('get', 'post', 'put', 'delete', 'patch'):
                    continue
                full = prefix + path
                matching = [name for name, (verb, route) in panel_operations().items()
                            if verb == method.upper() and (route == full or re.fullmatch(re.sub(r'\{[^}]+\}', '[^/]+', full), route))]
                mode = 'panel' if matching else 'protocol' if full.startswith(('/_runtime/', '/api/runtime/', '/api/browser-session/', '/assets/')) or full in ('/', '/{full_path}', '/api/desktop/shutdown') else 'original-ui'
                http[method.upper() + ' ' + full] = {'mode': mode, 'target': ' '.join(matching)}
        for route in application.routes:
            if hasattr(route, 'app') and hasattr(route.app, 'routes'):
                collect(route.app, prefix + route.path)
    collect(app)
    return {'shared_count': len(CAPABILITIES), 'catalog': catalog, 'mcp': mcp, 'mcp_schemas': mcp_schemas, 'cli': cli, 'http': http}


def markdown(data):
    lines = ['# MKLink 能力入口矩阵（源码自动盘点）', '',
             '由 `_maintainer/testing/frontend_capability_matrix.py` 从实际注册表、CLI parser 和 OpenAPI 生成。',
             '这是接入与路由契约清单，不是逐项真机通过证明。场景证据见 [验证报告](v050-capability-validation.md)。', '',
             '生成的 `inventory.json` 同时保留 MCP 参数 schema 和 CLI 参数/choices，便于检查同一命令下的动作分支。命名布局的 HTTP 存储端点归为 protocol，对应的页面操作为 layout.save、layout.search、layout.load。映射列是业务能力对应关系，包装工具的参数必须按原入口转换，不能原样互换。', '',
             f"共享调用 {data['shared_count']}；灵活面板直接操作 {len(data['catalog'])}；MCP 工具 {len(data['mcp'])}；CLI 命令节点（含分组、别名及 remote 子命令）{len(data['cli'])}；HTTP 操作 {len(data['http'])}。", '',
             '`panel`：能力面板选择后执行，原校验/确认/任务边界不变。`agent-cli`：灵活面板 Agent 请求交给当前会话，使用原 CLI 并回复结果，尚不是可绑定的直接按钮。',
             '`original-ui`：文件上传、下载、流及兼容业务入口仍在原页面，通过 gui_control 导航/原控件使用；未宣称均已成为独立子面板。`protocol`：认证、会话、代理、静态资源和控制协议，不作为任意 URL 代理开放。', '',
             '## 灵活面板直接操作', '', '| 名称 | 方法与原入口 | 验证层级 |', '| --- | --- | --- |']
    for item in sorted(data['catalog'], key=lambda item: item['name']):
        lines.append(f"| `{item['name']}` | `{item['method']} {item['path']}` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |")
    for title, entries in [('MCP 工具映射', data['mcp']), ('CLI 命令映射', data['cli']), ('HTTP 入口审计', data['http'])]:
        lines += ['', '## ' + title, '', '| 入口 | 模式 | 对应能力 |', '| --- | --- | --- |']
        for name, value in sorted(entries.items()):
            mode, target = ('panel', value) if isinstance(value, str) else (value['mode'], value['target'])
            lines.append(f"| `{name}` | {mode} | {target or '沿用原入口；见上方模式说明'} |")
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='Ignored evidence directory, never the source tree')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    data = inventory(args.output / 'project')
    (args.output / 'inventory.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    (args.output / 'matrix.md').write_text(markdown(data), encoding='utf-8')
    print(json.dumps({key: len(data[key]) for key in ('catalog', 'mcp', 'cli', 'http')}))
