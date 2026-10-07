"""Shared synthetic account and verified-run fixtures; contains no test cases."""
from pathlib import Path
from steam_sources import SourceResult, reconcile


ROOT = Path(__file__).resolve().parents[1]
ACCOUNT = '76561198000000001'


def run_bundle(run, ids=(1, 2)):
    rows, audit = reconcile([SourceResult('client_library',
        [{'appid': i, 'name': 'Fixture', 'app_type': 'game'} for i in ids],
        steam_id=ACCOUNT, completeness={'verified': True})])
    audit.update(run_id=run, producer={'git_commit': 'fixture', 'dirty': False})
    for row in rows:
        row.update(run_id=run, playtime_minutes=None)
    return rows, audit
