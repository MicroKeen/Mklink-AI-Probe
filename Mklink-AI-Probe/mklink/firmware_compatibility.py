"""Capability-based upgrade guidance. Status inspection performs no device I/O.

Version text identifies the model only; it is never a feature threshold.
Missing/failed queries, target errors and unsupported hardware are not evidence
that a firmware upgrade will help.
"""
import re


def upgrade_message(feature, required):
    return (f'{feature}: 当前下载器未声明所需能力 {required}，请升级与下载器型号匹配的固件。'
            f' Probe firmware does not advertise {required}; upgrade the matching probe firmware.')


class FirmwareUpgradeRequired(RuntimeError):
    code = 'firmware_upgrade_required'

    def __init__(self, feature, required):
        self.feature, self.required = feature, required
        super().__init__(upgrade_message(feature, required))

    def to_detail(self):
        return dict(code=self.code, feature=self.feature, required=self.required,
                    message=str(self), action='upgrade_probe_firmware')


def compatibility_snapshot(bridge):
    """Report known V3/V4 compatibility limits from this connection's cache.

HELLO-only features stay unknown until negotiation. V2 and unidentified models
are excluded: upgrading those models is not known to supply these capabilities.
"""
    from mklink.capture_clock import firmware_lines, active_clock_interface, clock_options
    from mklink.uart_baud import baud_options
    lines = firmware_lines(bridge)
    versions = sorted(line for line in lines if re.fullmatch(r'V[34]\.\d+\.\d+', line))
    result = dict(checked=len(versions) == 1, version=versions[0] if len(versions) == 1 else None,
                  warnings=[])
    if not result['checked']:
        return result

    def missing(feature, zh, required):
        result['warnings'].append(dict(code='firmware_upgrade_required', feature=feature,
            feature_zh=zh, required=required, message=upgrade_message(feature, required),
            action='upgrade_probe_firmware'))

    if 'MUX_TARGET=1' not in lines:
        missing('Shared sampling, live writes and multi-channel RTT',
                '共享采集、采集中写入及多通道 RTT', 'MUX_TARGET=1')
    else:
        caps = getattr(bridge, '_mux_capabilities', None)
        if type(caps) is int:
            for mask, feature, zh in (
                (0x3, 'MUX target operations', 'MUX 目标操作'),
                (0x618, 'SuperWatch sampling', 'SuperWatch 采集'),
                (0x20, 'In-stream software reset', '采集中软件复位'),
                (0x40, '4096-byte block reads', '4096 字节块读取'),
                (0x80, 'Concurrent RTT / SystemView', 'RTT / SystemView 并行采集'),
                (0x100, '480-byte fast transfers', '480 字节快速传输'),
                (0x800, '4096-byte continuous sampling', '4096 字节连续采样'),
            ):
                if caps & mask != mask:
                    missing(feature, zh, f'MUX HELLO 0x{mask:X}')
            if active_clock_interface(bridge) == 'SWD' and not caps & 0x1000:
                missing('Atomic sleep access', '原子睡眠访问', 'MUX HELLO 0x1000')
    interface = active_clock_interface(bridge)
    if interface in ('SWD', 'JTAG') and not clock_options(bridge, interface=interface)['clock_source'].endswith('-advertised'):
        missing(f'{interface} clock selection and acknowledgement', f'{interface} 多档时钟及设置确认',
                f'{interface}_CLOCKS / {interface}_CLOCK_ACK=1')
    if baud_options(lines)['source'] != 'firmware':
        missing('Extended UART baud rates', '扩展串口波特率', 'UART_BAUD_PROFILE=1 / UART_BAUDS')
    if interface == 'SWD':
        for kind in ('BIN', 'HEX'):
            flag = f'OFFLINE_{kind}_VERIFY=1'
            if flag not in lines:
                missing(f'Offline {kind} verification', f'脱机 {kind} 校验', flag)
    return result
