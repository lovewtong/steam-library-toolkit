import contextlib
import copy
import csv
import http.client
import io
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

import classify_games
from classify_steam_games import classify_one
import steam_collect
from steam_http import get_response
from steam_lock import collection_lock
from steam_picker_server import PickerLibrary, create_server
from steam_runs import publish_run, manifest_path, load_library, save_failed_run
from steam_sources import SourceResult, reconcile

ROOT = Path(__file__).resolve().parents[1]
ACCOUNT = '76561198000000001'


def client_payload():
    # Synthetic IDs/names with the same cardinality relationships as the live observation.
    types = ['game'] * 377 + ['application'] * 5 + ['demo'] * 2 + ['beta'] * 4
    apps = [{'appid': i, 'name': f'Fixture App {i}', 'app_type': kind} for i, kind in enumerate(types, 1)]
    missing = set(range(1, 28)) | {378, 383, 384}
    return {'steam_id': ACCOUNT, 'client': {'state': 'complete', 'completeness': {'verified': True, 'semantic_completeness_proven': False}, 'records': apps},
            'api': {'state': 'complete', 'records': [{**r, 'playtime_forever': 0} for r in apps if r['appid'] not in missing]},
            'licenses': [{'appid': i, 'app_type': 'tool'} for i in range(1, 2420)], 'license_status': 'ok',
            'playtimes': [{'appid': i, 'playtime_forever': i} for i in list(range(28, 229)) + [1, 2, 3]], 'playtime_status': 'ok'}


def small_run(run_id, ids=(1, 2)):
    rows, audit = reconcile([SourceResult('client_library', [{'appid': i, 'name': f'Game {i}', 'app_type': 'game'} for i in ids],
                                          steam_id=ACCOUNT, completeness={'verified': True})])
    audit.update(run_id=run_id, producer={'git_commit': 'fixture', 'dirty': False})
    for row in rows:
        row.update(run_id=run_id, playtime_minutes=None, playtime_available=False)
    return rows, audit


class ReportContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / 'library.json'

    def test_full_synthetic_integration_counts_schema_and_classification(self):
        with patch('steam_collect.load_config', return_value={}), patch('steam_collect.collect_client', return_value=client_payload()):
            audit = {}
            rows = steam_collect.collect(fetch_store=False, use_client=True, strict=True, audit=audit)
        self.assertEqual(len(rows), 388)
        self.assertEqual(audit['summary']['playtime_known'], 361)
        self.assertEqual(audit['summary']['unknown_playtime_apps'], 27)
        self.assertEqual(audit['difference_summary']['client_not_api']['by_type'], {'game': 27, 'application': 1, 'demo': 2})
        publish_run(self.output, rows, audit)
        picker = PickerLibrary(self.output).read()
        self.assertEqual(len(picker['games']), 377)
        self.assertEqual({int(g['appid']) for g in picker['games']}, {r['appid'] for r in rows if r['app_type'] == 'game'})
        self.assertEqual(len(load_library(self.output)), 388)

    def test_api_failure_defaults_to_client_and_strict_policies_differ(self):
        payload = client_payload()
        payload['api'] = {'state': 'unavailable', 'error_code': 'HTTP_503', 'records': []}
        with patch('steam_collect.load_config', return_value={}), patch('steam_collect.collect_client', return_value=payload):
            for extra in ({}, {'strict_membership': True}):
                audit = {}
                rows = steam_collect.collect(fetch_store=False, use_client=True, audit=audit, **extra)
                self.assertEqual(len(rows), 388)
                self.assertEqual(audit['status'], 'degraded')
            with self.assertRaisesRegex(RuntimeError, 'STRICT_SOURCE_FAILED'):
                steam_collect.collect(fetch_store=False, use_client=True, strict=True)
            with self.assertRaisesRegex(RuntimeError, 'REQUIRED_SOURCE_FAILED'):
                steam_collect.collect(fetch_store=False, use_client=True, require_sources=['web_api'])

    def test_snapshot_precedes_api_and_license_union_is_optin(self):
        sources = [SourceResult('license_file', [{'appid': 1}], steam_id=ACCOUNT),
                   SourceResult('web_api', [{'appid': 2}], steam_id=ACCOUNT),
                   SourceResult('licenses', [{'appid': 3}], steam_id=ACCOUNT)]
        rows, audit = reconcile(sources)
        self.assertEqual([r['appid'] for r in rows], [1])
        self.assertEqual(audit['fallback_source'], 'license_file')
        with self.assertRaisesRegex(RuntimeError, 'NO_MEMBERSHIP_SOURCE'):
            reconcile(sources[-1:])
        rows, _ = reconcile(sources, allow_candidate_membership=True)
        self.assertEqual([r['appid'] for r in rows], [1, 2, 3])

    def test_randomized_membership_invariant(self):
        rng = random.Random(20260912)
        for _ in range(100):
            sets = [set(rng.sample(range(1, 100), rng.randrange(40))) for _ in range(4)]
            sources = [SourceResult(name, [{'appid': i} for i in ids], steam_id=ACCOUNT, completeness={'verified': True})
                       for name, ids in zip(('client_library', 'web_api', 'license_file', 'licenses'), sets)]
            rows, _ = reconcile(sources)
            self.assertEqual({r['appid'] for r in rows}, sets[0])

    def test_schema_rejects_unknown_disguised_as_zero_before_pointer_changes(self):
        publish_run(self.output, *small_run('first'))
        before = manifest_path(self.output).read_bytes()
        rows, audit = small_run('invalid')
        rows[0]['playtime_evidence']['playtime_forever']['value'] = 0
        with self.assertRaisesRegex(ValueError, 'SCHEMA_INVALID'):
            publish_run(self.output, rows, audit)
        self.assertEqual(before, manifest_path(self.output).read_bytes())

    def test_csv_keeps_numeric_column_separate_from_display(self):
        games = [{'appid': i, 'name': 'Game', 'playtime_minutes': minutes,
                  'playtime_available': minutes is not None, 'playtime': {'state': state}}
                 for i, (minutes, state) in enumerate([(None, 'unknown'), (0, 'known_zero'), (3, 'known_nonzero'), (120, 'historical')], 1)]
        rows = classify_games.classify_library(games)
        path = Path(self.temp.name) / 'table.csv'
        classify_games.write_csv(rows, path)
        with path.open(encoding='utf-8-sig', newline='') as stream:
            parsed = list(csv.DictReader(stream))
        self.assertEqual([r['playtime_minutes'] for r in parsed], ['', '0', '3', '120'])
        self.assertEqual([r['playtime_status'] for r in parsed], ['unknown', 'known', 'known', 'historical'])

    def test_store_missing_invalid_and_empty_categories_are_distinct(self):
        response = Mock(status_code=200)
        with patch('steam_http.request_once', return_value=response):
            for data in ({}, {'categories': None}, {'categories': 'bad'}, {'categories': [{}]}):
                response.json.return_value = {'1': {'success': True, 'data': data}}
                details = steam_collect.get_store_details(1)
                self.assertIsNone(details['is_multiplayer'])
                self.assertIsNone(details['is_controller'])
            response.json.return_value = {'1': {'success': True, 'data': {'categories': []}}}
            self.assertFalse(steam_collect.get_store_details(1)['is_controller'])

    def test_rules_and_label_normalization(self):
        self.assertEqual(classify_games.match_main_category({'name': 'Example', 'genres': ['Action']}), '动作/冒险')
        self.assertEqual(classify_games.match_main_category({'name': 'Example', 'genres': ['Indie']}), '独立/其他')
        for name in ('What the Fog', 'Wizard of Legend 2', 'One Gun Guy', 'This Means Warp'):
            labels = classify_one({'appid': 1, 'name': name})['analysis']
            self.assertTrue(all(v == v.strip() for v in labels.values()))

    def test_os_lock_blocks_second_process_and_releases_on_crash(self):
        code = 'from steam_lock import collection_lock; import sys;\nwith collection_lock(sys.argv[1]): print("locked",flush=True); sys.stdin.read()'
        env = {**os.environ, 'PYTHONPATH': str(ROOT), 'PYTHONIOENCODING': 'utf-8'}
        first = subprocess.Popen([sys.executable, '-c', code, str(self.output)], env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
        try:
            self.assertEqual(first.stdout.readline().strip(), 'locked')
            second = subprocess.run([sys.executable, '-c', code, str(self.output)], env=env, input='', capture_output=True, text=True, encoding='utf-8', timeout=10)
            self.assertNotEqual(second.returncode, 0)
            self.assertIn('OUTPUT_BUSY', second.stderr)
        finally:
            first.kill(); first.communicate(timeout=5)
        with collection_lock(self.output):
            pass

    def test_cli_strict_failure_keeps_pointer_and_writes_sanitized_diagnostic(self):
        publish_run(self.output, *small_run('first'))
        before = manifest_path(self.output).read_bytes()
        payload = client_payload()
        payload['api'] = {'state': 'unavailable', 'error_code': 'HTTP_503', 'error': 'canary-private-token'}
        with patch.object(sys, 'argv', ['steam_collect.py', '--local-session', '--no-store', '--strict', '-o', str(self.output)]), \
             patch('steam_collect.load_config', return_value={}), patch('steam_collect.collect_client', return_value=payload), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stopped:
            steam_collect.main()
        self.assertEqual(stopped.exception.code, 1)
        self.assertEqual(before, manifest_path(self.output).read_bytes())
        files = list(Path(self.temp.name).glob('.library.failed-runs/*/diagnostic.json'))
        self.assertEqual(len(files), 1)
        text = files[0].read_text(encoding='utf-8')
        self.assertNotIn('canary-private-token', text)
        self.assertEqual(json.loads(text)['sources']['web_api']['error_code'], 'HTTP_503')

    def test_diagnostics_reject_untrusted_fields_and_values(self):
        audit = {'refresh_token': 'canary-private-token', 'sources': {'web_api': {'state': 'canary-private-token', 'error_code': 'canary-private-token', 'count': 0}}}
        path = save_failed_run(self.output, audit, 'canary-private-token')
        self.assertNotIn('canary-private-token', path.read_text())

    def test_python_http_retry_respects_retry_after_and_does_not_retry_auth(self):
        limited = Mock(status_code=429, headers={'Retry-After': '2'})
        okay = Mock(status_code=200)
        with patch('steam_http.request_once', side_effect=[limited, okay]) as get, patch('steam_http.wait_delay') as sleep:
            stats = {}
            self.assertIs(get_response('https://example.invalid', params={}, timeout=5, stats=stats), okay)
            self.assertEqual(stats['attempts'], 2)
            self.assertEqual(sleep.call_args.args[0], 2)
        with patch('steam_http.request_once', return_value=Mock(status_code=403)) as get:
            get_response('https://example.invalid', params={}, timeout=5)
            self.assertEqual(get.call_count, 1)


class PickerHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name) / 'library.json'
        publish_run(self.output, *small_run('first'))
        self.server = create_server(PickerLibrary(self.output), port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        self.temp.cleanup()

    def get(self, route, **headers):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            connection.request('GET', route, headers=headers)
            response = connection.getresponse()
            return response.status, response.read(), response.getheader('Cache-Control')
        finally:
            connection.close()

    def test_only_loopback_whitelisted_routes_and_no_store(self):
        self.assertEqual(self.server.server_address[0], '127.0.0.1')
        for path in ('/', '/index.html', '/api/library', '/api/run'):
            status, _, cache = self.get(path)
            self.assertEqual(status, 200)
            self.assertEqual(cache, 'no-store')
        for path in ('/config_local.json', '/.git/config', '/runs/a', '/client.snapshot.json', '/../config_local.json', '/%2e%2e/config_local.json', '/steam_library_classified.json'):
            self.assertEqual(self.get(path)[0], 404)
        self.assertEqual(self.get('/api/library', Host='attacker.invalid')[0], 403)
        self.assertEqual(self.get('/api/library', Origin='https://attacker.invalid')[0], 403)

    def test_pointer_switch_changes_data_and_metadata_together_and_corruption_fails_closed(self):
        first = json.loads(self.get('/api/library')[1])
        self.assertEqual(first['run']['run_id'], 'first')
        publish_run(self.output, *small_run('second', (3,)))
        second = json.loads(self.get('/api/library')[1])
        self.assertEqual(second['run']['run_id'], 'second')
        self.assertEqual([g['appid'] for g in second['games']], ['3'])
        self.assertNotIn(ACCOUNT, json.dumps(second))
        from steam_runs import resolve_artifact
        resolve_artifact(self.output, 'summary.json').write_text('corrupt')
        self.assertEqual(self.get('/api/library')[0], 503)


if __name__ == '__main__':
    unittest.main()
