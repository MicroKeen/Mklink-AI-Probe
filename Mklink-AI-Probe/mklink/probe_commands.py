"""Bounded probe operations. Never evaluate caller-supplied firmware code."""
from __future__ import annotations

import json
import re


def validate(capability, args):
    args = dict(args)
    fields = {
        'probe_presence': {'interface'}, 'probe_diagnostics': {'index'},
        'probe_control': {'setting', 'enabled', 'confirm_user', 'voltage_mv'},
        'set_power_on': {'voltage_mv', 'confirm_user', 'confirm_5v'},
        'set_power_off': {'confirm_user'},
        'isp_link_probe': {'baud_rate', 'duration_ms', 'strict'},
    }
    if capability not in fields or args.keys() - fields[capability]:
        raise ValueError('Unsupported probe operation or arguments')
    if capability == 'probe_presence':
        if args.get('interface') not in ('SWD', 'JTAG'):
            raise ValueError('Select SWD or JTAG explicitly; this query never switches interfaces')
    elif capability == 'probe_diagnostics':
        if type(args.get('index', -1)) is not int or not -2 <= args.get('index', -1) <= 31:
            raise ValueError('Diagnostic index: -2 reset report, -1 heap, 0..31 thread stack')
    elif capability == 'probe_control':
        if args.get('setting') not in ('auto_scan', 'auto_follow_vref', 'beep') or type(args.get('enabled')) is not bool:
            raise ValueError('Select auto_scan, auto_follow_vref or beep and an explicit boolean enabled')
        if args.get('confirm_user') is not True:
            raise ValueError('Probe setting changes require explicit user confirmation')
        if args['setting'] == 'auto_follow_vref' and args['enabled']:
            # Following an external reference can change the supplied voltage.
            # A boolean setter has no reference-voltage readback contract yet.
            raise ValueError('Enabling automatic Vref following requires a firmware voltage/readback contract; no VCC change sent. Use explicit confirmed set_power_on instead')
        if 'voltage_mv' in args:
            raise ValueError('voltage_mv belongs to set_power_on, not a probe boolean setting')
    elif capability in ('set_power_on', 'set_power_off'):
        if args.get('confirm_user') is not True:
            raise ValueError('Confirm this specific VCC operation with the user first')
        if capability == 'set_power_on':
            if type(args.get('voltage_mv')) is not int or args['voltage_mv'] not in (1800, 3300, 5000):
                raise ValueError('Confirm an exact voltage: 1800, 3300 or 5000 mV')
            if args['voltage_mv'] == 5000 and args.get('confirm_5v') is not True:
                raise ValueError('5V additionally requires confirm_5v=true')
    elif capability == 'isp_link_probe':
        from mklink.hpm_isp import ISP_BAUD_RATES
        if type(args.get('baud_rate')) is not int or args['baud_rate'] not in ISP_BAUD_RATES:
            raise ValueError('Choose a supported HPM ISP baud rate')
        if type(args.get('duration_ms', 10000)) is not int or not 1000 <= args.get('duration_ms', 10000) <= 120000:
            raise ValueError('ISP link probe duration must be 1000..120000 ms')
        if type(args.get('strict', False)) is not bool:
            raise ValueError('strict must be a boolean')
    return args


def integer_reply(bridge, expression, *, timeout=5):
    """Anchor a single signed return value; echoes and empty/duplicate replies fail."""
    marker = 'MKLINK_HOST_RESULT'
    raw = bridge.send_command(f'print("{marker}", {expression})', timeout=timeout)
    values = re.findall(r'(?m)^\s*' + marker + r'\s+(-?\d+)\s*$', raw)
    if len(values) != 1:
        raise ValueError('Firmware did not return a unique result; upgrade matching probe firmware. Outcome unknown; do not replay a write')
    return int(values[0]), raw


def require_model_operation(bridge, operation):
    """Reject known V2 omissions before issuing an unsupported command."""
    from mklink.capture_clock import firmware_lines
    if getattr(bridge, '_firmware_capabilities', ()) is None:
        loader = getattr(bridge, '_get_firmware_capabilities', None)
        if callable(loader):
            loader()
    if any(re.search(r'\bV2\.\d+\.\d+\b', line) for line in firmware_lines(bridge)):
        raise ValueError(f'当前 V2 型号固件不支持 {operation}。Current V2 firmware does not support this operation; upgrading is not known to add it.')


def execute(bridge, capability, args):
    args = validate(capability, args)
    if capability in ('probe_diagnostics', 'probe_control', 'set_power_on', 'set_power_off'):
        require_model_operation(bridge, capability)
    if capability == 'probe_presence':
        interface = args['interface']
        if interface == 'JTAG':
            supported, _ = integer_reply(bridge, 'hpm.jtag_presence_supported()')
            if supported != 1:
                raise ValueError('Upgrade HPMLINK V4 firmware for live JTAG presence')
        code, _ = integer_reply(bridge, 'hpm.read_idcode()' if interface == 'JTAG' else 'cmd.read_swd_idcode()')
        if code < 0:
            return {'ok': False, 'interface': interface, 'code': code, 'present': None,
                    'message': {-2: 'Probe busy', -3: 'Another debug interface is selected',
                                -4: 'Unstable scan; presence unknown', -6: 'Cancelled',
                                -12: 'Unsupported firmware'}.get(code, 'Presence check failed')}
        return {'ok': True, 'interface': interface, 'present': code not in (0, 0xFFFFFFFF),
                'idcode': code, 'identity': 'debug transport only; does not identify the exact MCU'}
    if capability == 'probe_diagnostics':
        index = args.get('index', -1)
        raw = bridge.send_command(f'cmd.get_memory({index})', timeout=5)
        records = [line.strip() for line in raw.splitlines() if line.strip().startswith(('MEM_', 'RESET '))]
        pattern = (r'RESET flags=[0-9a-fA-F]+ status=[0-9a-fA-F]+ live=[0-9a-fA-F]+ ticks=\d+ port=\d+ idcode=[0-9a-fA-F]+'
                   if index == -2 else r'MEM_HEAP total=\d+ used=\d+ peak=\d+' if index == -1 else
                   r'(MEM_STACK id=[0-9a-fA-F]+ name=\S+ size=\d+ untouched=\d+|MEM_END|MEM_ERROR (index|stack|changed))')
        if len(records) != 1 or re.fullmatch(pattern, records[0]) is None:
            raise ValueError('No probe diagnostic record; upgrade matching firmware. This is not target RAM')
        return {'ok': not any(line.startswith('MEM_ERROR') for line in records),
                'index': index, 'records': records, 'scope': 'probe'}
    if capability == 'isp_link_probe':
        code, raw = integer_reply(bridge, f"hpm.isp_link_probe({args['baud_rate']}, {args.get('duration_ms', 10000)}, {int(args.get('strict', False))})",
                                  timeout=args.get('duration_ms', 10000) / 1000 + 10)
        events = [json.loads(line[len('HPM_ISP_DIAG_RESULT '):]) for line in raw.splitlines()
                  if line.startswith('HPM_ISP_DIAG_RESULT ')]
        if len(events) != 1 or events[0].get('schema') != 1 or events[0].get('code') != code or events[0].get('operation') != 'query_only':
            raise ValueError('Missing or inconsistent ISP diagnostic result; upgrade firmware; do not infer programming success')
        return {'ok': code == 0, 'code': code, 'diagnostic': events[0],
                'meaning': 'Observed link loss and reconnect only; no flash, OTP, reset or VCC operation'}
    if capability == 'probe_control':
        setting, enabled = args['setting'], args['enabled']
        expression = (f'cmd.set_beep_{"on" if enabled else "off"}()' if setting == 'beep' else
                      f'cmd.set_{setting}({enabled})')
        expected = 0 if setting == 'beep' else int(enabled)
    else:
        expression = f"cmd.set_power_on({args['voltage_mv']})" if capability == 'set_power_on' else 'cmd.set_power_off()'
        expected = 0
    code, _ = integer_reply(bridge, expression)
    return {'ok': code == expected, 'code': code, 'operation': capability, 'requested': args,
            'acknowledged': code == expected, 'measured': False}
