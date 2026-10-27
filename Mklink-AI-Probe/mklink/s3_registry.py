"""Explicit host-local S3 registrations. Discovery never scans radios or opens USB."""
import json
import os
import re
from urllib.parse import urlsplit


def validate_node(value):
    if not isinstance(value, dict):
        raise ValueError('S3 registration must be an object')
    node = dict(value)
    if not re.fullmatch('[0-9a-f]{12}', str(node.get('node_id', ''))):
        raise ValueError('Exact lowercase S3 MAC identity required')
    if not re.fullmatch('[0-9a-f]{32}', str(node.get('token', ''))):
        raise ValueError('USB-paired S3 credential required')
    if not isinstance(node.get('address'), str):
        raise ValueError('S3 address must be a string')
    if node.get('transport') == 'http':
        url = urlsplit(node.get('address', ''))
        if (url.scheme not in ('http', 'https') or not url.hostname or url.username
                or url.password or url.query or url.fragment or url.path not in ('', '/')):
            raise ValueError('Use an explicit HTTP(S) origin without credentials/path')
        node['address'] = node['address'].rstrip('/')
    elif node.get('transport') == 'ble':
        if not re.fullmatch(r'[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}', str(node.get('address', ''))):
            raise ValueError('Explicit BLE device address required')
    else:
        raise ValueError('S3 transport must be http or ble')
    return {k: node[k] for k in ('node_id', 'transport', 'address', 'token')}


def _path():
    from mklink.runtime import _private_dir
    return _private_dir() / 's3-nodes.json'


def load_nodes():
    try:
        rows = json.loads(_path().read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}
    if not isinstance(rows, dict):
        raise ValueError('Invalid local S3 registry; preserve it for inspection')
    result = {}
    for key, row in rows.items():
        node = validate_node(row)
        if key != 's3-' + node['node_id']:
            raise ValueError('S3 registry identity mismatch')
        result[key] = node
    return result


def register_node(value):
    from mklink.runtime import runtime_lock, discover
    node = validate_node(value)
    key = 's3-' + node['node_id']
    # Same identity across AP, STA and BLE. Never mutate a live owner's route.
    with runtime_lock('startup.lock', key):
        with runtime_lock('owner.lock', key):
            if discover(key):
                raise RuntimeError('Disconnect the S3 backend before changing its route')
            with runtime_lock('s3-registry.lock'):
                rows = load_nodes()
                rows[key] = node
                from mklink.remote.sites import _atomic_json
                _atomic_json(_path(), rows)
    return public_node(key, node)


def public_node(key, node):
    return dict(probe_id=key, port=key, vid=None, pid=None,
                serial_number='', description='ESP32-S3 wireless MKLink',
                location=node['transport'], transport='s3-' + node['transport'],
                identity_stable=True, node_id=node['node_id'], alias='')


def inventory():
    return [public_node(key, node) for key, node in load_nodes().items()]


def main():
    """Read credentials from stdin, never command-line arguments or diagnostics."""
    import sys
    try:
        result = register_node(json.load(sys.stdin))
    except Exception:
        print(json.dumps({'ok': False, 'error': 'Registration rejected; validate identity, transport and inactive backend'}))
        raise SystemExit(1)
    print(json.dumps({'ok': True, 'probe': result}))


if __name__ == '__main__':
    main()
