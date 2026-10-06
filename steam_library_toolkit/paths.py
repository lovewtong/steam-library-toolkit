"""Source-checkout paths; moving services must not move users' data."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / 'config_local.json'
OUTPUT_FILE = ROOT / 'steam_library.json'
CACHE_DIR = ROOT / '.steam_cache'
RULES_FILE = ROOT / 'docs/guides/CLASSIFICATION_RULES.md'


def library_target(path):
    path = Path(path).resolve()
    if path.name.endswith('.current.json'):
        path = path.with_name(path.name[:-len('.current.json')] + '.json')
    return path
