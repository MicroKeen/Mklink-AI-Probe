"""Native V0.5.0 acceptance against immutable artifacts; never opens hardware.

The updater library uses a synthetic old-version AppHandle. This exercises real
signature verification and installation, not an actual old client's WebView.
"""
from __future__ import annotations

import asyncio
import functools
import hashlib
import http.server
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import threading
import time
import urllib.request

SOURCE = "1097f98eb9025b38b16cd32095bced7dd65ecdcd"
REPO = "MicroKeen/Mklink-AI-Probe"
ROOT = Path(__file__).resolve().parents[2]
TARGET = os.environ["NATIVE_TARGET"]
OUT = Path(os.environ["MKLINK_BUILD_OUTPUT_DIR"]) / "native-acceptance"
OUT.mkdir(parents=True, exist_ok=True)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def run(*args, **kwargs):
    return subprocess.run(list(map(str, args)), check=True, **kwargs)


def download():
    run_id = os.environ['SOURCE_RUN']
    assert run_id.isdecimal()
    data = json.loads(subprocess.check_output(['gh', 'api', f'repos/{REPO}/actions/runs/{run_id}']))
    assert data['head_sha'] == SOURCE and data['conclusion'] == 'success'
    assert data['path'] == '.github/workflows/desktop-unix.yml'
    destination = OUT / 'inputs'
    destination.mkdir()
    run('gh', 'run', 'download', run_id, '--repo', REPO,
        '--name', f'mklink-desktop-{TARGET}-{SOURCE}', '--dir', destination)
    manifests = list(destination.rglob('build-manifest.json'))
    assert len(manifests) == 1
    manifest_path = manifests[0]
    data = json.loads(manifest_path.read_text())
    assert data['source_commit'] == SOURCE and data['target'] == TARGET and data['version'] == '0.5.0'
    for item in data['files']:
        file = manifest_path.parent / item['name']
        assert file.stat().st_size == item['size'] and digest(file) == item['sha256']
    qualification = json.loads((manifest_path.parent / 'qualification.json').read_text())
    assert qualification['frozen_cli'] == qualification['frozen_mcp'] == qualification['graceful_shutdown'] == 'passed'
    signatures = json.loads(os.environ['PUBLIC_SIGNATURES'])
    for name in data['updater_platforms'].values():
        signature = signatures[name]
        assert isinstance(signature, str) and 100 < len(signature) < 2000
        (manifest_path.parent / (name + '.sig')).write_text(signature, encoding='ascii')
    (OUT / 'input.json').write_text(json.dumps({'manifest': str(manifest_path), 'source_run': run_id}))
    print('Exact source artifacts, native smoke, sizes/hashes and public signatures staged')


def local_request(origin, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(origin + path, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=10) as response:
        return json.load(response)


async def native_gui(command, sidecar, work, label):
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport
    scratch = work / label
    scratch.mkdir()
    env = dict(os.environ, MKLINK_RUNTIME_DIR=str(scratch / 'registry'), TMPDIR=str(scratch),
               PATH='/usr/bin:/bin:/usr/sbin:/sbin', APPIMAGE_EXTRACT_AND_RUN='1')
    for key in ('PYTHONPATH', 'PYTHONHOME', 'MKLINK_STCP_LIBRARY', 'MKLINK_BUILTIN_FLM_ROOT'):
        env.pop(key, None)
    log = (OUT / f'{label}.log').open('w')
    process = subprocess.Popen(command, cwd=scratch, env=env, stdout=log, stderr=log, stdin=subprocess.DEVNULL)
    info = None
    result = {'label': label, 'pages': [], 'tabs': []}
    try:
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f'{label}: native application exited {process.returncode}')
            paths = list(scratch.glob('mklink-ai-probe-runtime-*.json'))
            paths = [p for p in paths if not p.name.endswith('.timing.json')]
            if paths:
                info = json.loads(paths[0].read_text())
                break
            await asyncio.sleep(.2)
        assert info, 'Native application did not publish endpoint'
        origin = f"http://127.0.0.1:{info['port']}"
        while True:
            try:
                result['health'] = local_request(origin, '/api/health')
                break
            except (OSError, ValueError):
                if process.poll() is not None or time.monotonic() > deadline:
                    raise
                await asyncio.sleep(.2)
        assert result['health']['status'] == 'ok'
        transport = StdioTransport(str(sidecar), ['mcp'], env=env, cwd=str(scratch),
                                   keep_alive=False, log_file=OUT / f'{label}-mcp.log')
        async with Client(transport) as client:
            for _ in range(60):
                opened = (await client.call_tool('gui_open', {'open_browser': False})).data
                if opened.get('status') == 'ready':
                    break
                await asyncio.sleep(.5)
            for _ in range(60):
                windows = (await client.call_tool('gui_control', {'action': 'windows'})).data['windows']
                windows = [w for w in windows if w.get('gui_protocol') == 2]
                if windows:
                    break
                await asyncio.sleep(.5)
            assert len(windows) == 1 and windows[0]['kind'] == 'desktop', windows
            wid = windows[0]['window_id']

            async def gui(action, **args):
                response = (await client.call_tool('gui_control', {'action': action, 'window_id': wid, **args})).data
                assert response['status'] == 'applied', response
                return response['state']

            for page in ('config', 'online-flash', 'offline-flash', 'remote-service'):
                state = await gui('navigate', page=page)
                assert state['page'] == page
                await asyncio.sleep(.15)
                controls = await gui('controls')
                assert controls['result']['controls']
                result['pages'].append(page)
            for tab in ('rtt', 'superwatch', 'hardfault', 'memory', 'serial', 'modbus', 'systemview', 'symbols'):
                state = await gui('navigate', page='dashboard', tab=tab)
                assert state['tab'] == tab
                result['tabs'].append(tab)
            await gui('navigate', page='config')
        result['native_webview_and_mcp_controls'] = 'passed'
        return result
    finally:
        if info:
            try:
                local_request(f"http://127.0.0.1:{info['port']}", '/api/desktop/shutdown', {'instance_id': info['instanceId']})
            except Exception:
                pass
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        log.close()
        # Backend uses the normal shutdown API; only this test's window is terminated.
        await asyncio.sleep(7)


def qualify():
    entry = json.loads((OUT / 'input.json').read_text())
    manifest_path = Path(entry['manifest'])
    manifest = json.loads(manifest_path.read_text())
    packages = manifest_path.parent
    work = Path(os.environ['MKLINK_BUILD_WORK_DIR'])
    report = {'source': SOURCE, 'target': TARGET, 'source_run': entry['source_run'],
              'updater_library': '2.10.1', 'updater_app_handle': 'synthetic 0.4.3; not the historical client',
              'usb_hardware': 'not available', 'gatekeeper_quarantine': 'not tested',
              'interactive_admin_prompt': 'not tested', 'checks': []}
    report_path = OUT / f'acceptance-{TARGET}.json'

    class Handler(http.server.SimpleHTTPRequestHandler):
        bad = False
        requests = []

        def log_message(self, *_args):
            pass

        def do_GET(self):
            self.requests.append(self.path)
            if self.path == '/unavailable':
                self.send_error(503)
                return
            if self.path == '/latest.json':
                platforms = {}
                for key, name in manifest['updater_platforms'].items():
                    signature = (packages / (name + '.sig')).read_text().strip()
                    platforms[key] = {'url': f'{origin}/{name}', 'signature': 'invalid' if self.bad else signature}
                body = json.dumps({'version': '0.5.0', 'platforms': platforms}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            super().do_GET()

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(packages)))
    origin = f'http://127.0.0.1:{server.server_port}'
    threading.Thread(target=server.serve_forever, daemon=True).start()
    harness = Path(os.environ['CARGO_TARGET_DIR']) / 'release/mklink-native-updater-check'
    config = ROOT / 'gui/src-tauri/tauri.conf.json'

    def update(executable, filename, kind):
        tool = work / f'updater-{kind}'
        shutil.copy2(harness, tool)
        tool.chmod(0o755)
        env = os.environ.copy()
        if platform.system() == 'Linux':
            data = tool.read_bytes()
            marker = b'__TAURI_BUNDLE_TYPE_VAR_UNK'
            assert data.count(marker) == 1, 'Ambiguous test-harness bundle marker'
            tool.write_bytes(data.replace(marker, b'__TAURI_BUNDLE_TYPE_VAR_DEB' if kind == 'deb' else b'__TAURI_BUNDLE_TYPE_VAR_APP'))
            if kind == 'deb':
                # Existing CI passwordless sudo; no GUI credential prompts or host policy changes.
                helpers = work / 'installer-tools'
                helpers.mkdir()
                (helpers / 'sudo').symlink_to(shutil.which('sudo'))
                env['PATH'] = str(helpers)
        for mode, version in [('bad-signature', '0.4.3'), ('install', '0.4.3'), ('current', '0.5.0')]:
            Handler.bad = mode == 'bad-signature'
            try:
                result = run(tool, config, origin, executable, version, filename, mode,
                             env=env, capture_output=True, text=True, timeout=180)
            except subprocess.CalledProcessError as error:
                (OUT / f'{kind}-{mode}-error.log').write_text(error.stdout + '\n' + error.stderr)
                raise
            report['checks'].append({'kind': kind, 'mode': mode, 'result': result.stdout.strip()})

    try:
        if platform.system() == 'Darwin':
            mount = work / 'dmg'
            mount.mkdir()
            run('hdiutil', 'attach', '-nobrowse', '-mountpoint', mount, next(packages.glob('*.dmg')))
            try:
                app = next(mount.glob('*.app'))
                installed = work / app.name
                shutil.copytree(app, installed, symlinks=True)
            finally:
                run('hdiutil', 'detach', mount)
            binary = installed / 'Contents/MacOS/mklink-ai-probe'
            sidecar = binary.with_name('mklink-sidecar')
            report['before_update'] = asyncio.run(native_gui([str(binary)], sidecar, work, 'mac-before'))
            (installed / 'obsolete-acceptance-marker').write_text('Must disappear during replacement')
            update(binary, next(packages.glob('*.app.tar.gz')).name, 'mac')
            assert not (installed / 'obsolete-acceptance-marker').exists()
            run('codesign', '--verify', '--deep', '--strict', installed)
            report['after_update'] = asyncio.run(native_gui([str(binary)], sidecar, work, 'mac-after'))
        else:
            image = next(packages.glob('*.AppImage'))
            installed = work / image.name
            shutil.copy2(image, installed)
            installed.chmod(0o755)
            run(installed, '--appimage-extract', cwd=work, stdout=subprocess.DEVNULL)
            sidecar = work / 'squashfs-root/usr/bin/mklink-sidecar'
            report['appimage_before'] = asyncio.run(native_gui([str(installed)], sidecar, work, 'appimage-before'))
            update(installed, image.name, 'appimage')
            assert digest(installed) == digest(image) and os.access(installed, os.X_OK)
            report['appimage_after'] = asyncio.run(native_gui([str(installed)], sidecar, work, 'appimage-after'))
            deb = next(packages.glob('*.deb'))
            run('sudo', 'dpkg', '-i', deb)
            binary = Path('/usr/bin/mklink-ai-probe')
            sidecar = Path('/usr/bin/mklink-sidecar')
            report['deb_before'] = asyncio.run(native_gui([str(binary)], sidecar, work, 'deb-before'))
            update(binary, deb.name, 'deb')
            report['deb_after'] = asyncio.run(native_gui([str(binary)], sidecar, work, 'deb-after'))
        assert '/unavailable' in Handler.requests and '/latest.json' in Handler.requests
        report['endpoint_fallback'] = '503 primary -> working secondary'
        report['passed'] = True
    except Exception as error:
        report['error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        server.shutdown()
        report_path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    {'download': download, 'qualify': qualify}[sys.argv[1]]()
