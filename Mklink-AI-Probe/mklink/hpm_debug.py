"""Checked host adapter for the opt-in HPM_DEBUG v1 console protocol.

Peripheral registers remain memory/SVD operations. This interface is RV32
hart 0 core/CSR control and never falls back to Cortex-M, reset, or replay.
"""
from __future__ import annotations

import json
import re

from mklink._types import DeviceState

ACTIONS = {'capabilities': 0, 'status': 1, 'halt': 2, 'resume': 3, 'step': 4,
           'read-register': 5, 'write-register': 6, 'breakpoint-query': 7,
           'breakpoint-set': 8, 'breakpoint-clear': 9}
MUTATIONS = {2, 3, 4, 6, 8, 9}
CSRS = dict(mstatus=0x300, misa=0x301, mie=0x304, mtvec=0x305,
            mscratch=0x340, mepc=0x341, mcause=0x342, mtval=0x343, mip=0x344,
            dcsr=0x7b0, mvendorid=0xf11, marchid=0xf12, mimpid=0xf13, mhartid=0xf14)
ERRORS = {-1: 'invalid arguments', -2: 'target busy', -3: 'unsupported target/register/trigger',
          -4: 'debug transport failed', -5: 'bounded wait expired', -6: 'cancelled',
          -7: 'hart must already be halted', -8: 'breakpoint slot/address conflict',
          -9: 'operation outcome uncertain', -12: 'firmware lacks HPM debug support'}


class HpmDebugError(RuntimeError):
    def __init__(self, message, *, record=None, uncertain=False):
        super().__init__(message)
        self.detail = {'error': 'hpm_debug', 'message': message,
                       'outcome_unknown': uncertain, 'record': record}


def _integer(value, label, maximum=0xffffffff, minimum=0):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f'{label} must be an integer in {minimum}..{maximum}')
    return value


def _register(name):
    if not isinstance(name, str):
        raise ValueError('Specify a RISC-V register name')
    name = name.lower()
    name = {'sp': 'x2', 'ra': 'x1', 'fp': 'x8', 'dpc': 'pc'}.get(name, name)
    if name == 'pc':
        return 0, 32
    if re.fullmatch(r'x(?:[0-9]|[12][0-9]|3[01])', name):
        return 0, int(name[1:])
    if name in CSRS:
        return 1, CSRS[name]
    raise ValueError('Use x0..x31, pc/dpc, sp/ra/fp or a supported RISC-V CSR; ARM register names are invalid')


def command_arguments(body):
    if not isinstance(body, dict) or body.keys() - {'action', 'timeout_ms', 'register', 'value', 'slot', 'address'}:
        raise ValueError('Invalid HPM debug arguments')
    action = body.get('action', 'status')
    if not isinstance(action, str) or action not in ACTIONS:
        raise ValueError('Unknown HPM debug action')
    op = ACTIONS[action]
    allowed = {'action'}
    args = [op]
    if op in (2, 3, 4):
        allowed.add('timeout_ms')
        args.append(_integer(body.get('timeout_ms', 500), 'timeout_ms', 1000, 1))
    elif op in (5, 6):
        allowed.add('register')
        kind, number = _register(body.get('register'))
        args += [kind, number]
        if op == 6:
            allowed.add('value')
            value = _integer(body.get('value'), 'value')
            if kind != 0 or number == 0:
                raise ValueError('Only x1..x31 and PC are writable; CSR/x0 writes are not supported')
            if number == 32 and value % 2:
                raise ValueError('PC must be 2-byte aligned')
            args.append(value)
    elif op in (7, 8, 9):
        allowed.add('slot')
        args.append(_integer(body.get('slot'), 'slot', 7))
        if op in (8, 9):
            allowed.add('address')
            address = _integer(body.get('address'), 'address')
            if address % 2:
                raise ValueError('Breakpoint address must be 2-byte aligned')
            args.append(address)
    if body.keys() - allowed:
        raise ValueError('Arguments do not apply to this HPM debug action')
    return args


def _record(response, op):
    records = [line[len('HPM_DEBUG '):] for line in response.splitlines()
               if line.startswith('HPM_DEBUG ')] if isinstance(response, str) else []
    try:
        if len(records) != 1:
            raise ValueError('Expected one result record')
        record = json.loads(records[0])
        fields = {'v', 'op', 'rc', 'issued', 'cleanup', 'value', 'dmstatus', 'state',
                  'slot', 'tdata1', 'tdata2', 'xlen', 'hart', 'max_slot'}
        if not isinstance(record, dict) or not fields <= record.keys():
            raise ValueError('Incomplete result')
        if any(type(record[key]) is not int for key in fields):
            raise ValueError('Non-integer result')
        if (record['v'] != 1 or record['op'] != op or record['xlen'] != 32 or record['hart'] != 0
                or record['issued'] not in (0, 1) or record['cleanup'] not in (0, 1)
                or record['state'] not in (0, 1, 2) or not 0 <= record['max_slot'] <= 7
                or not -12 <= record['rc'] <= 0):
            raise ValueError('Mismatched result')
        for key in ('value', 'dmstatus', 'slot', 'tdata1', 'tdata2'):
            _integer(record[key], key)
    except (ValueError, TypeError, KeyError) as error:
        raise HpmDebugError('Missing or invalid HPM debug receipt; do not replay the operation',
                            uncertain=op in MUTATIONS) from error
    if record['rc'] != 0 or record['cleanup']:
        raise HpmDebugError('HPM debug: ' + ERRORS.get(record['rc'], 'cleanup or protocol failure'),
                            record=record, uncertain=bool(record['issued'] or record['cleanup'] or record['rc'] == -9))
    return record


def execute(device, body):
    args = command_arguments(body)  # Reject injection and bad ranges before I/O.
    device._require_connected()
    bridge = device._bridge
    if bridge.state != DeviceState.READY:
        raise ValueError('Stop the active acquisition before HPM CPU debug; no automatic stop')
    def send(command, *, op=None):
        try:
            return bridge.send_command(command, timeout=3.0)
        except Exception as error:
            raise HpmDebugError('HPM debug transport failed; no replay or reset attempted',
                                uncertain=op in MUTATIONS if op is not None else False) from error
    version = send('hpm.debug_version()')
    values = [line.strip() for line in version.splitlines() if re.fullmatch(r'-?\d+', line.strip())] if isinstance(version, str) else []
    if values != ['1']:
        raise HpmDebugError('Probe firmware does not expose HPM_DEBUG v1; use compatible firmware or the configured HPM IDE debugger')
    capabilities = _record(send('hpm.debug(0)', op=0), 0)
    if args[0] == 0:
        return capabilities
    if not capabilities['value'] & (1 << (args[0] - 1)):
        raise HpmDebugError('Probe firmware does not advertise this HPM debug action')
    if args[0] in (7, 8, 9) and args[1] > capabilities['max_slot']:
        raise ValueError('Breakpoint slot exceeds the firmware probe range')
    command = 'hpm.debug(' + ','.join(str(value) for value in args) + ')'
    return _record(send(command, op=args[0]), args[0])
