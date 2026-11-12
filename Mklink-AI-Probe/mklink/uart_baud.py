"""Ordinary UART baud choices; capability inspection never changes a target."""
from mklink.usb_interfaces import canonical_serial_port

COMMON_RATES = (9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600)
PROFILE_1_RATES = (300, 600, 1200, 2400, 4800, 9600, 14400, 19200, 38400,
                   56000, 57600, 115200, 128000, 230400, 256000, 460800,
                   512000, 750000, 921600, 1000000, 1500000, 2000000,
                   2500000, 3000000, 3500000, 4000000, 4500000, 5000000,
                   6000000, 7000000, 7500000, 8000000, 9000000, 10000000)


def baud_options(lines=()):
    """Unknown/partial capability declarations offer common choices only."""
    common = {'profile': None, 'rates': list(COMMON_RATES), 'source': 'common'}
    lines = [line.strip() for line in lines if isinstance(line, str)]
    profiles = [line for line in lines if line.startswith('UART_BAUD_PROFILE=')]
    if not profiles:
        import re
        if any(re.fullmatch(r'V[34]\.\d+\.\d+', line) for line in lines):
            from mklink.firmware_compatibility import upgrade_message
            common['firmware_warning'] = upgrade_message('Extended UART baud rates', 'UART_BAUD_PROFILE=1')
    lists = [line.removeprefix('UART_BAUDS=') for line in lines if line.startswith('UART_BAUDS=')]
    if profiles != ['UART_BAUD_PROFILE=1'] or len(lists) != 1 or len(lists[0]) > 512:
        return common
    values = lists[0].split(',')
    if not values or any(not item.isascii() or not item.isdigit() for item in values):
        return common
    rates = [int(item) for item in values]
    if len(set(rates)) != len(rates) or any(rate not in PROFILE_1_RATES for rate in rates):
        return common
    return {'profile': 1, 'rates': sorted(rates), 'source': 'firmware'}


def cached_options(state, port):
    """Use only the connected bridge's already-negotiated version lines."""
    if port.get('uart_kind') != 'mklink_uart' or not port.get('command_port'):
        return baud_options()
    device = state.get('device')
    bridge = getattr(device, '_bridge', None)
    if (device is None or not device.connected or device.port != port['command_port']
            or bridge is None or getattr(bridge, '_transport_error', None) is not None):
        return baud_options()
    from mklink.probes import inventory
    candidates = [p for p in inventory() if p['port'] == port['command_port']]
    if len(candidates) != 1 or candidates[0]['probe_id'] != state.get('shared_probe_id'):
        return baud_options()
    from mklink.capture_clock import firmware_lines
    return baud_options(firmware_lines(bridge))


def describe_ports(state, ports):
    return [{**port, 'uart_baud': cached_options(state, port)} for port in ports]


def read_options(state, port_name):
    """Explicit probe-only query through the same physical probe's owner.

    Never select another target in this window, stop a capture, or open CDC
    directly. A busy shared backend refuses through its existing admission.
    """
    from mklink.serial._port import list_uart_ports
    from mklink.probes import inventory
    from mklink.runtime import query_probe
    port_name = canonical_serial_port(port_name)
    matches = [p for p in list_uart_ports() if canonical_serial_port(p['device']) == port_name]
    if len(matches) != 1 or matches[0].get('uart_kind') != 'mklink_uart':
        raise ValueError('Select an identified ordinary MKLink UART port')
    port = matches[0]
    if not port.get('command_port'):
        raise ValueError('Cannot uniquely pair the UART with its command interface')
    cached = cached_options(state, port)
    if cached['source'] == 'firmware':
        return {**port, 'uart_baud': cached}
    candidates = [p for p in inventory() if p['port'] == port['command_port']]
    if len(candidates) != 1 or not candidates[0]['identity_stable']:
        raise ValueError('Cannot uniquely identify the UART probe')
    result = query_probe('probe_version', probe=candidates[0]['probe_id'])
    # Re-enumerate after the query so a changed COM assignment is not accepted.
    fresh = [p for p in list_uart_ports() if canonical_serial_port(p['device']) == port_name]
    if fresh != [port]:
        raise ValueError('UART identity changed while reading baud capabilities; refresh ports')
    return {**port, 'uart_baud': baud_options(result['raw'].splitlines())}
