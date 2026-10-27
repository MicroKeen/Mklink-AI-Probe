"""Thin workbench launcher for the existing runtime and Site Agent protocol.

stdin/stdout are private control frames; no S3 bytes are brokered by the GUI.
The backend survives this client while another local/remote client is attached.
"""
import contextlib
import json
from pathlib import Path
import secrets
import hashlib
import socket
import sys


class Workbench:
    def __init__(self):
        self.client = None
        self.info = None
        self.site_name = None

    def attach(self, request):
        from mklink.s3_registry import register_node, load_nodes, validate_node
        from mklink.runtime import RuntimeClient, ensure_runtime, request as rpc, browser_url
        from mklink.remote.sites import SiteRegistry, SiteError
        node = validate_node(request['node'])
        key = 's3-' + node['node_id']
        project = Path(request['project_root']).resolve(strict=True)
        if not project.is_dir():
            raise ValueError('Select an existing project directory')
        current = load_nodes().get(key)
        if current != node:
            register_node(node)
        self.info = ensure_runtime(project_root=str(project), probe=key, port=0)
        self.client = RuntimeClient(info=self.info, project_root=str(project), kind='sdk', name='Mklink wireless workbench')
        try:
            self.client.connect(probe=key, axf=request.get('axf') or None)
            service = rpc(self.info, 'GET', '/_runtime/remote-service')
            self.site_name = 's3-' + node['node_id']
            registry = SiteRegistry()
            if not service.get('running'):
                token = secrets.token_urlsafe(32)
                with socket.socket() as listener:
                    listener.bind(('127.0.0.1', 0))
                    port = listener.getsockname()[1]
                service = rpc(self.info, 'POST', '/_runtime/remote-service',
                              dict(enabled=True, host='127.0.0.1', port=port, allow_lan=False, token=token))
                registry.add(self.site_name, 'ws://127.0.0.1:' + str(port), token,
                             note='S3 adapter; existing shared backend and Site Agent',
                             timeout=60.0, flash_timeout=1200.0)
            else:
                try:
                    saved = registry.get(self.site_name)
                    expected = 'ws://' + service['host'] + ':' + str(service['port'])
                    if (saved.url != expected or hashlib.sha256(saved.token.encode()).hexdigest()[:8]
                            != service.get('token_fingerprint')):
                        self.site_name = None
                except (RuntimeError, KeyError, ValueError, SiteError):
                    self.site_name = None
            # Never rotate another client's live service token. Existing users
            # can continue their configured endpoint if it was started elsewhere.
            return dict(instance_id=self.info['instance_id'], probe_id=key,
                        site=self.site_name, browser_url=browser_url(self.info),
                        skill_entry_ready=self.site_name is not None,
                        service=service, status=self.client.call('device_status'))
        except BaseException:
            self.close()
            raise

    def dispatch(self, frame):
        method = frame.get('method')
        if method == 'attach':
            if self.client:
                raise ValueError('Detach this client before attaching another node')
            return self.attach(frame['params'])
        if not self.client:
            raise ValueError('Attach the shared backend first')
        if method == 'status':
            from mklink.runtime import request
            status = request(self.info, 'GET', '/api/runtime/control/status')
            status.update(site=self.site_name, skill_entry_ready=self.site_name is not None)
            return status
        if method == 'call':
            args = frame.get('params') or {}
            return self.client.call(args['capability'], args.get('arguments'))
        if method == 'detach':
            self.close()
            return {'detached': True}
        raise ValueError('Unsupported workbench control')

    def close(self):
        if self.client:
            self.client.close()
            self.client = None


def main():
    # Frozen sidecars retain the runtime's existing detached-process entrypoint.
    if len(sys.argv) > 1 and sys.argv[1] == 'runtime':
        from mklink.cli import main as cli
        return cli()
    sink = sys.stdout
    workbench = Workbench()
    try:
        for line in sys.stdin:
            if len(line) > 65536:
                raise ValueError('Oversized workbench control frame')
            frame = json.loads(line)
            try:
                with contextlib.redirect_stdout(sys.stderr):
                    data = workbench.dispatch(frame)
                result = dict(id=frame.get('id'), ok=True, data=data)
            except Exception as error:
                result = dict(id=frame.get('id'), ok=False, error=str(error))
            sink.write(json.dumps(result, ensure_ascii=False) + '\n')
            sink.flush()
    finally:
        workbench.close()


if __name__ == '__main__':
    main()
