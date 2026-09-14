import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch
import requests

from steam_http import get_response, RequestCancelled, SourceCoolingDown
from steam_metadata import RequestGate, parse_fields, merge_fields, apply_observation
from steam_collect import cached_store_details
from steam_sources import SourceResult, reconcile
from steam_runs import publish_run, resolve_artifact, manifest_path
from test_phase_two import run_bundle


class HTTPDeadlineTests(unittest.TestCase):
    def setUp(self):
        self.received = threading.Event()
        self.stopped = threading.Event()
        received, stopped = self.received, self.stopped
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                self.send_response(302 if self.path == '/redirect' else 200)
                self.send_header('Location', '/body')
                self.end_headers()
                received.set()
                try:
                    if self.path == '/large':
                        self.wfile.write(b'x' * 8192)
                        self.wfile.flush()
                        return
                    for _ in range(150):
                        if stopped.wait(.04):
                            break
                        self.wfile.write(b'x')
                        self.wfile.flush()
                except (ConnectionError, OSError):
                    pass
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.stopped.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_slow_drip_obeys_total_deadline_and_reaps_worker(self):
        processes = []
        popen = subprocess.Popen
        def launch(*args, **kwargs):
            process = popen(*args, **kwargs)
            processes.append(process)
            return process
        started = time.monotonic()
        with patch('steam_http.subprocess.Popen', side_effect=launch):
            with self.assertRaises(requests.Timeout):
                get_response(self.url, params={}, timeout=1, total_timeout=2)
        self.assertTrue(self.received.is_set())
        self.assertLess(time.monotonic() - started, 3.5)
        self.assertTrue(all(p.poll() is not None for p in processes))

    def test_cancel_terminates_a_receiving_request(self):
        cancel = threading.Event()
        outcome = []
        def run():
            try:
                get_response(self.url, params={}, timeout=1, cancel_event=cancel)
            except RequestCancelled:
                outcome.append('cancelled')
        thread = threading.Thread(target=run)
        thread.start()
        try:
            self.assertTrue(self.received.wait(5))
            started = time.monotonic()
            cancel.set()
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
            self.assertEqual(outcome, ['cancelled'])
            self.assertLess(time.monotonic() - started, 2)
        finally:
            cancel.set()
            thread.join(timeout=3)

    def test_body_cap_and_redirect_do_not_download_unbounded_data(self):
        with self.assertRaisesRegex(requests.RequestException, 'HTTP_RESPONSE_TOO_LARGE'):
            get_response(self.url + '/large', params={}, timeout=1, total_timeout=5, max_bytes=100)
        response = get_response(self.url + '/redirect', params={}, timeout=1, total_timeout=3)
        self.assertEqual(response.status_code, 302)

    def test_enrichment_interrupt_cancels_inflight_request_and_keeps_pointer(self):
        from steam_enrich import enrich
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / 'source.json', Path(directory) / 'output.json'
            publish_run(source, *run_bundle('source'))
            publish_run(output, *run_bundle('previous'))
            pointer = manifest_path(output).read_bytes()
            def fetch(appid, cache_dir, refresh, stats, *, cancel_event, observation):
                if appid == 1:
                    if not self.received.wait(5):
                        raise AssertionError('request did not start')
                    raise KeyboardInterrupt()
                return get_response(self.url, params={}, timeout=1, cancel_event=cancel_event)
            started = time.monotonic()
            with patch('steam_enrich.cached_store_details', side_effect=fetch):
                with self.assertRaises(KeyboardInterrupt):
                    enrich(source, output, workers=2)
            self.assertLess(time.monotonic() - started, 3)
            self.assertEqual(manifest_path(output).read_bytes(), pointer)


class AuditFixTests(unittest.TestCase):
    def test_direct_collection_publishes_missing_versus_empty_evidence(self):
        from steam_collect import collect
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'apps.txt'
            source.write_text('1 Example\n', encoding='utf-8')
            states = []
            for index, data in enumerate(({}, {'genres': []})):
                audit = {}
                with patch('steam_collect.get_store_result', return_value={'status': 'success', 'details': parse_fields(data)}):
                    rows = collect(apps_file=source, use_api=False, use_client=False, audit=audit,
                                   cache_dir=Path(directory) / str(index))
                target = Path(directory) / f'library{index}.json'
                actual, _, _ = publish_run(target, rows, audit)
                saved = json.loads(resolve_artifact(actual, 'steam_library.audit.json').read_text(encoding='utf-8'))
                observation = saved['metadata']['apps']['1']
                states.append(observation['fields']['genres'])
                self.assertIsNotNone(observation['fetched_at'])
                self.assertEqual(observation['source'], 'store_api')
                if index == 0:
                    self.assertNotIn('store_metadata', rows[0]['provenance'])
            self.assertEqual(states, ['missing', 'empty'])

    def test_shared_retry_after_defers_following_apps_without_requests_or_cache(self):
        gate = RequestGate(1.5)
        response = Mock(status_code=429, headers={'Retry-After': '120'})
        with tempfile.TemporaryDirectory() as directory, \
                patch('steam_collect.STORE_GATE', gate), \
                patch('steam_http.request_once', return_value=response) as request:
            cached_store_details(1, directory)
            for appid in (2, 3):
                stats, observation = {}, {}
                self.assertIsNone(cached_store_details(appid, directory, audit_meta=stats, observation=observation))
                self.assertEqual(stats['deferred'], 1)
                self.assertIsNone(observation['fetched_at'])
                self.assertFalse((Path(directory) / f'{appid}.json').exists())
            self.assertEqual(request.call_count, 1)

    def test_mixed_ids_preserve_positive_and_do_not_infer_negative(self):
        mixed = {'categories': [{'id': 28, 'description': 'フルコントローラサポート'}, {'description': '実績'}]}
        fields = parse_fields(mixed)
        self.assertTrue(fields['is_controller'])
        self.assertIsNone(fields['is_multiplayer'])
        row = {'is_controller': True, 'is_multiplayer': True}
        merge_fields(row, fields)
        self.assertTrue(row['is_controller'])
        self.assertTrue(row['is_multiplayer'])
        self.assertIsNone(parse_fields({'categories': [{'id': -1, 'description': '不明'}]})['is_controller'])

    def test_cache_observation_time_and_read_time_remain_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            observation = {}
            result = {'status': 'success', 'details': parse_fields({})}
            with patch('steam_collect.get_store_result', return_value=result), patch('steam_collect.time.time', return_value=100):
                cached_store_details(1, directory)
            with patch('steam_collect.get_store_result', side_effect=AssertionError('cache expected')), \
                    patch('steam_collect.time.time', return_value=200):
                stats = {}
                details = cached_store_details(1, directory, audit_meta=stats, observation=observation)
            self.assertEqual(observation, {'source': 'store_cache', 'fetched_at': 100, 'read_at': 200})
            row, audit = {'appid': 1}, {}
            apply_observation(row, details, stats, observation, audit)
            self.assertNotIn('provenance', row)
            self.assertEqual(audit['apps']['1']['fields']['genres'], 'missing')

    def test_api_unavailable_is_not_a_confirmed_empty_api(self):
        client = SourceResult('client_library', [{'appid': 1, 'name': 'Game', 'app_type': 'game'}], completeness={'verified': True})
        for api in (None, SourceResult('web_api', [], status='error', state='unavailable')):
            rows, audit = reconcile([client] + ([api] if api else []))
            self.assertEqual(audit['difference']['client_not_api'], [])
            self.assertIsNone(audit['difference_summary']['client_not_api']['count'])
            audit.update(run_id='unknown', producer={'git_commit': 'fixture', 'dirty': False})
            rows[0].update(run_id='unknown', playtime_minutes=None)
            with tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / 'library.json'
                publish_run(target, rows, audit)
                output = json.loads(resolve_artifact(target, 'missing_from_web_api.json').read_text(encoding='utf-8'))
                self.assertIsNone(output['apps'][0]['present_in_web_api'])
                self.assertEqual(output['comparison']['state'], 'unavailable')
        _, audit = reconcile([client, SourceResult('web_api', [])])
        self.assertEqual(audit['difference']['client_not_api'], [1])
