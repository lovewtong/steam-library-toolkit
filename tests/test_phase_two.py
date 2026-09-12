import errno
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from steam_runs import publish_run, load_library, manifest_path
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


class FailureAndScaleTests(unittest.TestCase):
    def test_interrupted_http_body_retries_without_losing_successful_response(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import socket
        import threading
        from steam_http import get_response
        requests_seen = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                requests_seen.append(1)
                body = b'{"response":{"game_count":0,"games":[]}}'
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                if len(requests_seen) == 1:
                    self.wfile.write(body[:4])
                    self.wfile.flush()
                    self.connection.shutdown(socket.SHUT_RDWR)
                    self.connection.close()
                else:
                    self.wfile.write(body)
        with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                stats = {}
                response = get_response(f'http://127.0.0.1:{server.server_port}', params={}, timeout=1, stats=stats)
                self.assertEqual(response.json()['response']['game_count'], 0)
                self.assertEqual(stats['attempts'], 2)
                response.close()
            finally:
                server.shutdown()
                thread.join(timeout=2)

    def test_fsync_disk_full_or_permission_denied_preserves_previous_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'library.json'
            publish_run(target, *run_bundle('previous'))
            pointer = manifest_path(target).read_bytes()
            for code in (errno.ENOSPC, errno.EACCES):
                with patch('os.fsync', side_effect=OSError(code, 'injected')):
                    with self.assertRaises(OSError):
                        publish_run(target, *run_bundle('failed' + str(code), (3,)))
                self.assertEqual(manifest_path(target).read_bytes(), pointer)
                self.assertEqual([r['appid'] for r in load_library(target)], [1, 2])

    def test_kill_writer_at_commit_boundary_retains_old_pointer_and_releases_lock(self):
        from steam_lock import collection_lock
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'library.json'
            publish_run(target, *run_bundle('previous'))
            pointer = manifest_path(target).read_bytes()
            code = """
import sys
from pathlib import Path
from unittest.mock import patch
from test_phase_two import run_bundle
from steam_lock import collection_lock
from steam_runs import publish_run, manifest_path, atomic_json
target=Path(sys.argv[1])
def gate(path, data):
    if Path(path)==manifest_path(target):
        print('READY_TO_COMMIT',flush=True)
        sys.stdin.read(1)
    atomic_json(path,data)
with collection_lock(target),patch('steam_runs.atomic_json',side_effect=gate):
    publish_run(target,*run_bundle('interrupted',(3,)))
"""
            process = subprocess.Popen([sys.executable, '-c', code, str(target)], cwd=ROOT,
                env={**os.environ, 'PYTHONPATH': os.pathsep.join([str(ROOT), str(ROOT / 'tests')])},
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
            try:
                # A separate reader prevents a broken child from hanging the test indefinitely.
                import queue, threading
                events = queue.Queue()
                reader = threading.Thread(target=lambda: events.put(process.stdout.readline()), daemon=True)
                reader.start()
                self.assertEqual(events.get(timeout=20).strip(), 'READY_TO_COMMIT')
                process.kill()
                process.wait(timeout=5)
                reader.join(timeout=2)
                self.assertEqual(manifest_path(target).read_bytes(), pointer)
                self.assertEqual([r['appid'] for r in load_library(target)], [1, 2])
                with collection_lock(target):
                    publish_run(target, *run_bundle('recovered', (3,)))
                self.assertEqual([r['appid'] for r in load_library(target)], [3])
            finally:
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=5)

    def test_ten_thousand_members_ignore_extra_api_and_stale_license_candidates(self):
        def apps(start, end):
            return [{'appid': i, 'name': 'Fixture', 'app_type': 'game'} for i in range(start, end)]
        rows, audit = reconcile([
            SourceResult('client_library', apps(1, 10001), steam_id=ACCOUNT, completeness={'verified': True}),
            SourceResult('web_api', apps(2001, 11001), steam_id=ACCOUNT),
            SourceResult('licenses', apps(1, 15001), steam_id=ACCOUNT),
            SourceResult('license_file', apps(1, 12001), steam_id=ACCOUNT)])
        self.assertEqual({r['appid'] for r in rows}, set(range(1, 10001)))
        self.assertEqual(len(audit['difference']['client_not_api']), 2000)
        self.assertEqual(len(audit['difference']['api_not_client']), 1000)
        self.assertTrue(all(r['playtime_evidence']['playtime_forever']['state'] == 'unknown' for r in rows))

    def test_online_offline_recovered_sources_keep_historical_members_distinct(self):
        old = SourceResult('license_file', [{'appid': 1}, {'appid': 2}], steam_id=ACCOUNT)
        rows, report = reconcile([old, SourceResult('client_library', status='failed', steam_id=ACCOUNT)])
        self.assertEqual(report['status'], 'degraded')
        self.assertEqual(report['membership_semantics'], 'historical_snapshot')
        self.assertEqual({r['appid'] for r in rows}, {1, 2})
        recovered = SourceResult('client_library', [{'appid': 2}], steam_id=ACCOUNT, completeness={'verified': True})
        rows, report = reconcile([recovered, old])
        self.assertEqual({r['appid'] for r in rows}, {2})
        self.assertEqual(report['membership'], 'client_snapshot')

    def test_offline_summary_counts_historical_time_separately_from_unknown(self):
        from steam_collect import collect
        from steam_sources import utc_now
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'snapshot.json'
            path.write_text(json.dumps({'schema_version': 2, 'steam_id': ACCOUNT,
                'generated_at': utc_now(), 'apps': [{'appid': 1, 'playtime_forever': 0},
                                                  {'appid': 2, 'playtime_forever': 3}, {'appid': 3}]}), encoding='utf-8')
            report = {}
            collect(fetch_store=False, use_api=False, apps_file=path, audit=report)
            self.assertEqual(report['summary']['playtime_historical'], 2)
            self.assertEqual(report['summary']['playtime_known'], 0)
            self.assertEqual(report['summary']['unknown_playtime_apps'], 1)


if __name__ == '__main__':
    unittest.main()
