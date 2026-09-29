import copy
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from classify_games import classify_library, write_csv
from steam_collect import get_owned_games
from steam_sources import SourceResult, reconcile
from steam_runs import publish_run, resolve_artifact


class TimeContractsTests(unittest.TestCase):
    def test_python_api_uses_shared_nullable_time_contract(self):
        cases = json.loads((Path(__file__).parent / 'fixtures/api-time-values.json').read_text())
        for field in cases['fields']:
            for case in cases['valid']:
                row = {'appid': 1, **({field: case['value']} if case['present'] else {})}
                expected = [row, {'appid': 2, 'playtime_forever': 7}]
                with self.subTest(field=field, case=case), patch('steam_collect.get_response', return_value=Mock(
                        status_code=200, json=lambda: {'response': {'game_count': 2, 'games': expected}})):
                    self.assertEqual(get_owned_games('fixture-key', 'fixture-account'), expected)
            for value in cases['invalid']:
                with self.subTest(field=field, value=value), patch('steam_collect.get_response', return_value=Mock(
                        status_code=200, json=lambda: {'response': {'games': [{'appid': 1, field: value}]}})):
                    with self.assertRaises(ValueError):
                        get_owned_games('fixture-key', 'fixture-account')

    def test_historical_last_played_is_independent_from_current_total_and_published(self):
        rows, audit = reconcile([
            SourceResult('client_library', [{'appid': 1, 'name': 'Fixture', 'app_type': 'game'}], completeness={'verified': True}),
            SourceResult('web_api', [{'appid': 1, 'playtime_forever': 5, 'rtime_last_played': None}]),
            SourceResult('license_file', [{'appid': 1, 'rtime_last_played': 1700000000}], fetched_at='2024-01-02T00:00:00Z'),
        ])
        audit.update(run_id='time-contract', producer={'git_commit': 'fixture', 'dirty': False})
        rows[0].update(run_id='time-contract', playtime_minutes=5,
                       playtime={**rows[0]['playtime_evidence']['playtime_forever'], 'minutes': 5},
                       last_played_iso='2023-11-14T22:13:20Z')
        original = copy.deepcopy(rows)
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / 'library.json'
            publish_run(target, rows, audit)
            with resolve_artifact(target, 'classified.csv').open(encoding='utf-8-sig', newline='') as f:
                record = next(csv.DictReader(f))
            self.assertEqual(record['playtime_status'], 'known')
            self.assertEqual(record['last_played_status'], 'historical')
            self.assertEqual(record['last_played_source'], 'license_file')
            self.assertEqual(record['last_played_observed_at'], '2024-01-02T00:00:00Z')
            self.assertEqual(record['last_played_at'], '1700000000')
            self.assertEqual(record['last_played'], '历史 2023-11-14')
            markdown = resolve_artifact(target, 'classified.md').read_text(encoding='utf-8')
            self.assertIn('历史 2023-11-14', markdown)
            self.assertIn('license_file', markdown)
            self.assertIn('2024-01-02T00:00:00Z', markdown)
        self.assertEqual(rows, original)

    def test_last_played_zero_unknown_current_and_legacy_keep_distinct_meanings(self):
        for state, value, expected in [('known_zero', 0, '无时间记录'), ('unknown', None, '未知'),
                                       ('historical', 0, '历史 无时间记录'),
                                       ('known_nonzero', 1700000000, '2023-11-14')]:
            game = {'appid': 1, 'name': 'Fixture', 'playtime_minutes': None, 'last_played_iso': '2000-01-01T00:00:00Z',
                    'playtime_evidence': {'rtime_last_played': {'state': state, 'value': value,
                        'source': 'license_file' if state == 'historical' else 'web_api', 'observed_at': '2024-01-02T00:00:00Z'}}}
            with self.subTest(state=state), tempfile.TemporaryDirectory() as d:
                table = classify_library([game], {})
                write_csv(table, Path(d) / 'table.csv')
                with (Path(d) / 'table.csv').open(encoding='utf-8-sig', newline='') as f:
                    record = next(csv.DictReader(f))
                self.assertEqual(record['last_played'], expected)
                self.assertEqual(record['last_played_status'], state)
                self.assertNotIn('1970', record['last_played'])
        legacy = classify_library([{'appid': 1, 'last_played_iso': '2023-11-14T22:13:20Z'}], {})[0]
        self.assertEqual(legacy['last_played_status'], 'unverified')
        self.assertIsNone(legacy['last_played_source'])
