"""Build both archives and exercise an installed wheel outside the checkout.

Requires `build` plus the tested Python and Node dependencies. No Steam login or
Steam requests occur during the smoke checks; pip, npm and build isolation may
fetch dependencies. Temporary work stays outside the repository.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ['steam_collect', 'steam_enrich', 'steam_reclassify', 'steam_review_classification',
          'steam_sync_collections', 'steam_picker', 'classify_games', 'classify_steam_games']

SMOKE = r'''
import importlib.metadata
import json, os, sys, threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import urlopen
from unittest.mock import patch
import steam_library_toolkit
from steam_library_toolkit.paths import ROOT, SOURCE_ROOT, RESOURCES, RULES_FILE, node_environment
from steam_library_toolkit.classification.overrides import load_overrides
from steam_library_toolkit.storage.schema import validate_artifacts
from steam_library_toolkit.storage.runs import publish_run, new_run_metadata
from steam_library_toolkit.sources.reconcile import SourceResult, reconcile
from steam_library_toolkit.sources.http import get_response
from steam_library_toolkit.web.server import PickerLibrary, create_server
from steam_library_toolkit.cli.reclassify import reclassify
from steam_library_toolkit.cli.review_classification import build_review
from steam_library_toolkit.cli.collections import build_plan
from steam_library_toolkit.cli.node_runtime import prepare
import subprocess

assert SOURCE_ROOT is None
assert ROOT == Path.cwd()
assert Path(steam_library_toolkit.__file__).is_relative_to(Path(sys.prefix))
assert RULES_FILE.is_file() and len(load_overrides()) >= 1
rows, audit = reconcile([SourceResult('client_library',
    [{'appid': 550, 'name': 'Fixture', 'app_type': 'game'}],
    steam_id='76561198000000001', completeness={'verified': True})])
audit.update(new_run_metadata())
producer = audit['producer']
assert producer['git_commit'] is None and producer['dirty'] is None
assert producer['package_version'] == importlib.metadata.version('steam-library-toolkit')
assert producer['build_status'] == 'verified' and producer['build_id'].startswith('sha256:')
for row in rows:
    row.update(run_id=audit['run_id'], playtime_minutes=None)
validate_artifacts(rows, audit)
source = ROOT / 'library.json'
publish_run(source, rows, audit)
corrected = ROOT / 'corrected.json'
reclassify(source, corrected)
assert len(PickerLibrary(corrected).read()['games']) == 1
assert build_review(corrected)
assert build_plan(corrected, '76561198000000001')
server = create_server(PickerLibrary(corrected), port=0)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    url = f'http://127.0.0.1:{server.server_port}'
    assert b'<html' in urlopen(url).read().lower()
    assert len(json.load(urlopen(url + '/api/library'))['games']) == 1
finally:
    server.shutdown(); server.server_close(); thread.join(timeout=2)

calls = []
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        calls.append(1)
        self.send_response(503 if len(calls) == 1 else 200)
        self.send_header('Retry-After', '0'); self.end_headers()
        self.wfile.write(b'{"ok":true}')
server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
try:
    response = get_response(f'http://127.0.0.1:{server.server_port}', params={}, timeout=3, total_timeout=15)
    response.close()
    assert response.json() == {'ok': True} and len(calls) == 2
finally:
    server.shutdown(); server.server_close(); thread.join(timeout=2)
prepare(ROOT / '.steam_node')
env = node_environment()
subprocess.run(['node', '-e', "for (const n of ['steam-user','steam-session','undici']) require(n);"],
               cwd=RESOURCES / 'node_bridge', env=env, check=True, capture_output=True)
assert not (Path(steam_library_toolkit.__file__).parent / 'config_local.json').exists()
stamp = json.loads((RESOURCES / 'build-info.json').read_bytes())
assert producer['build_id'] == 'sha256:' + stamp['payload_sha256']
resource = RESOURCES / 'rules/CLASSIFICATION_RULES.md'
original = resource.read_bytes()
try:
    resource.write_bytes(original + b'\n')
    modified = new_run_metadata()['producer']
    assert modified['build_status'] == 'modified' and modified['build_id'] is None
finally:
    resource.write_bytes(original)
assert new_run_metadata()['producer'] == producer
print('Installed wheel: schemas, rules, run publication, classification, review, plan, HTML/API, HTTP retry and Node resolution passed.')
'''


def run(command, **kwargs):
    result = subprocess.run([str(part) for part in command], capture_output=True, text=True, encoding='utf-8', **kwargs)
    if result.returncode:
        raise RuntimeError(f'Command failed: {command[0]}\n{result.stdout}\n{result.stderr}')
    return result.stdout


def package_bytes(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        forbidden = ('node_modules/', '.steam_cache/', 'outputs/', 'config_local.json', 'classification_overrides.local.json')
        assert not any(any(part in name for part in forbidden) for name in names), 'Private data in wheel'
        assert all(name.startswith(('steam_library_toolkit/', 'steam_library_toolkit-')) for name in names), names
        return {name: archive.read(name) for name in names if name.startswith('steam_library_toolkit/')}


def main():
    with tempfile.TemporaryDirectory(prefix='steam-package-') as temporary:
        work = Path(temporary)
        artifacts = work / 'archives'
        run([sys.executable, '-m', 'build', '--outdir', artifacts, ROOT])
        wheel = next(artifacts.glob('*.whl'))
        source = next(artifacts.glob('*.tar.gz'))
        # build's default wheel already comes from the sdist. Independently build
        # directly from the checkout and compare the actual installed payload.
        direct = work / 'direct'
        run([sys.executable, '-m', 'build', '--wheel', '--outdir', direct, ROOT])
        payload = package_bytes(wheel)
        assert payload == package_bytes(next(direct.glob('*.whl'))), 'sdist/wheel resource drift'
        required = ['resources/web/steam_picker.html', 'resources/rules/CLASSIFICATION_RULES.md',
                    'resources/rules/classification_overrides.json', 'resources/node_bridge/package.json',
                    'resources/node_bridge/package-lock.json', 'sources/http_worker.py', 'resources/build-info.json']
        assert all('steam_library_toolkit/' + name in payload for name in required)
        with tarfile.open(source) as archive:
            names = archive.getnames()
            assert not any(any(part in name for part in ('node_modules/', '.steam_cache/', '/outputs/', '/config_local.json', '/classification_overrides.local.json')) for name in names)
            assert all(any(name.endswith('/' + old + '.py') for name in names) for old in LEGACY)
            for public in ('docs/ARCHITECTURE.md', 'tests/test_picker_evidence.cjs', 'examples/config_local.example.json', 'legacy/classify_steam.js'):
                assert any(name.endswith('/' + public) for name in names), public
        environment = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'STEAM_LIBRARY_HOME', 'STEAM_LIBRARY_NODE_HOME')}
        environment.update(PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
        target = work / 'venv'
        venv.EnvBuilder(with_pip=True).create(target)
        python = target / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        user = work / 'user'
        user.mkdir()
        run([python, '-m', 'pip', 'install', '-r', ROOT / 'requirements-tested.txt'], cwd=user, env=environment)
        run([python, '-m', 'pip', 'install', '--no-deps', wheel], cwd=user, env=environment)
        run([python, '-m', 'steam_library_toolkit', 'node', '--install'], cwd=user, env=environment)
        print(run([python, '-c', SMOKE], cwd=user, env=environment).strip())
        for command in ['collect', 'enrich', 'reclassify', 'review', 'plan', 'picker', 'classify', 'classify-five', 'node']:
            run([python, '-m', 'steam_library_toolkit', command, '--help'], cwd=user, env=environment)
        binary = target / ('Scripts/steam-library.exe' if os.name == 'nt' else 'bin/steam-library')
        run([binary, 'collect', '--help'], cwd=user, env=environment)
        selected = work / 'selected'
        selected.mkdir()
        explicit = {**environment, 'STEAM_LIBRARY_HOME': str(selected)}
        # Windows runners use 8.3 temp names; macOS /var may resolve to /private/var.
        # Compare actual directory identity rather than two spelling variants.
        run([python, '-c', 'from steam_library_toolkit.paths import ROOT; import os; assert ROOT.samefile(os.environ["STEAM_LIBRARY_HOME"])'], cwd=user, env=explicit)
        # -S removes editable-package discovery. Only third-party modules are
        # restored explicitly; the compatibility entry must bootstrap src itself.
        dependency_paths = json.loads(run([sys.executable, '-c', 'import json,site; print(json.dumps(site.getsitepackages()))']))
        source_env = {**environment, 'PYTHONPATH': os.pathsep.join(dependency_paths)}
        for command in LEGACY:
            run([sys.executable, '-S', ROOT / (command + '.py'), '--help'], cwd=user, env=source_env)
        print(f'Distribution passed: {len(payload)} package files, sdist parity, installed commands and {len(LEGACY)} source compatibility entries.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
