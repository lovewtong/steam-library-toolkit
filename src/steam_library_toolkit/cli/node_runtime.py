"""Explicitly prepare the optional Node runtime without authenticating to Steam."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from steam_library_toolkit.paths import SOURCE_ROOT, node_home, node_manifests


def prepare(directory):
    directory = Path(directory).resolve()
    manifest, lock = node_manifests()
    if SOURCE_ROOT is not None and directory == SOURCE_ROOT.resolve():
        return directory  # Preserve the checkout's developer scripts and lockfile.
    marker = directory / '.steam-library-runtime.json'
    if directory.exists() and any(directory.iterdir()):
        if not marker.is_file() or json.loads(marker.read_text(encoding='utf-8')) != {'managed_by': 'steam-library-toolkit', 'version': 1}:
            raise ValueError('Node directory is not managed by steam-library-toolkit; choose an empty directory.')
    directory.mkdir(parents=True, exist_ok=True)
    package = json.loads(manifest.read_text(encoding='utf-8'))
    package.pop('scripts', None)
    (directory / 'package.json').write_text(json.dumps(package, indent=2) + '\n', encoding='utf-8')
    (directory / 'package-lock.json').write_bytes(lock.read_bytes())
    marker.write_text(json.dumps({'managed_by': 'steam-library-toolkit', 'version': 1}) + '\n', encoding='utf-8')
    return directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true', help='Install pinned Node dependencies with npm ci (network access).')
    args = parser.parse_args()
    if not args.install:
        parser.print_help()
        return 0
    executable = shutil.which('npm.cmd') or shutil.which('npm')
    if not executable:
        parser.exit(1, 'npm is unavailable; install Node.js 22 first.\n')
    try:
        directory = prepare(node_home())
        result = subprocess.run([executable, 'ci'], cwd=directory, check=False)
    except (OSError, ValueError) as error:
        parser.exit(1, f'Cannot prepare Node runtime: {error}\n')
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
