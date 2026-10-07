"""Identify the installed package payload without guessing a checkout commit."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re

BUILD_INFO = Path('resources/build-info.json')


def payload_hash(directory, version):
    """Hash version, relative file names and bytes; omit generated runtime files."""
    directory = Path(directory)
    digest = hashlib.sha256(b'steam-library-payload-v1\0' + version.encode('utf-8') + b'\0')
    files = sorted((path for path in directory.rglob('*') if path.is_file()
                   and '__pycache__' not in path.relative_to(directory).parts
                   and path.suffix not in ('.pyc', '.pyo') and path.relative_to(directory) != BUILD_INFO),
                   key=lambda path: path.relative_to(directory).as_posix())
    for path in files:
        name = path.relative_to(directory).as_posix().encode('utf-8')
        digest.update(len(name).to_bytes(8, 'big'))
        digest.update(name)
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def producer_package_info():
    from steam_library_toolkit.paths import PACKAGE_ROOT, SOURCE_ROOT
    if SOURCE_ROOT is not None:
        import tomllib
        try:
            version = tomllib.loads((SOURCE_ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
        except (OSError, ValueError, KeyError, TypeError):
            version = None
        if not isinstance(version, str) or not version:
            version = None
        return {'package_version': version, 'build_id': None, 'build_status': 'source'}
    try:
        version = importlib.metadata.version('steam-library-toolkit')
    except importlib.metadata.PackageNotFoundError:
        version = None
    result = {'package_version': version, 'build_id': None, 'build_status': 'unavailable'}
    path = PACKAGE_ROOT / BUILD_INFO
    try:
        info = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return result  # Wheels built before this feature remain usable.
    except (OSError, ValueError):
        return {**result, 'build_status': 'invalid'}
    if (not isinstance(info, dict) or set(info) != {'schema_version', 'package_version', 'payload_sha256'}
            or type(info['schema_version']) is not int or info['schema_version'] != 1
            or not isinstance(version, str) or not version or info['package_version'] != version
            or not isinstance(info['payload_sha256'], str)
            or re.fullmatch(r'[0-9a-f]{64}', info['payload_sha256']) is None):
        return {**result, 'build_status': 'invalid'}
    try:
        observed = payload_hash(PACKAGE_ROOT, version)
    except OSError:
        return {**result, 'build_status': 'invalid'}
    if observed != info['payload_sha256']:
        return {**result, 'build_status': 'modified'}
    return {**result, 'build_id': 'sha256:' + observed, 'build_status': 'verified'}
