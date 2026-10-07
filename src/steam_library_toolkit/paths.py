"""Separate immutable package resources from checkout or user-selected data."""
import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
RESOURCES = PACKAGE_ROOT / 'resources'
checkout = PACKAGE_ROOT.parents[1]
SOURCE_ROOT = checkout if (PACKAGE_ROOT.parent.name == 'src' and (checkout / 'pyproject.toml').is_file()) else None
ROOT = Path(os.environ['STEAM_LIBRARY_HOME']).expanduser().resolve() if os.environ.get('STEAM_LIBRARY_HOME') else SOURCE_ROOT or Path.cwd()
CONFIG_PATH = ROOT / 'config_local.json'
OUTPUT_FILE = ROOT / 'steam_library.json'
CACHE_DIR = ROOT / '.steam_cache'
BUILTIN_RULES_FILE = RESOURCES / 'rules/classification_overrides.json'
RULES_FILE = SOURCE_ROOT / 'docs/guides/CLASSIFICATION_RULES.md' if SOURCE_ROOT else RESOURCES / 'rules/CLASSIFICATION_RULES.md'


def node_home():
    selected = os.environ.get('STEAM_LIBRARY_NODE_HOME')
    return Path(selected).expanduser().resolve() if selected else SOURCE_ROOT or ROOT / '.steam_node'


def node_modules_dir():
    return node_home() / 'node_modules'


def node_environment():
    environment = dict(os.environ)
    environment['NODE_PATH'] = os.pathsep.join(filter(None, (str(node_modules_dir()), environment.get('NODE_PATH'))))
    return environment


def node_manifests():
    directory = SOURCE_ROOT or RESOURCES / 'node_bridge'
    return directory / 'package.json', directory / 'package-lock.json'


def library_target(path):
    path = Path(path).resolve()
    if path.name.endswith('.current.json'):
        path = path.with_name(path.name[:-len('.current.json')] + '.json')
    return path
