from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import time
import unittest

from steam_http import get_response
from steam_metadata import RequestGate


class HTTPStatusRetryTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.status = 503
        self.exhaust = False
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                fixture.requests.append(time.monotonic())
                status = fixture.status if fixture.exhaust or len(fixture.requests) == 1 else 200
                self.send_response(status)
                self.send_header('Retry-After', '1' if status == 429 else '0')
                self.end_headers()
                self.wfile.write(b'{"ok": true}')

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def fetch(self):
        stats = {}
        response = get_response(f'http://127.0.0.1:{self.server.server_port}',
                                params={}, timeout=3, total_timeout=15, stats=stats,
                                gate=RequestGate(0) if self.status == 429 else None)
        # Close before reading: this is also how the retry loop disposes responses.
        response.close()
        self.assertEqual(stats['attempts'], len(self.requests))
        return response

    def test_real_worker_503_then_200(self):
        response = self.fetch()
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'ok': True})

    def test_real_worker_429_then_200_obeys_short_cooldown(self):
        self.status = 429
        response = self.fetch()
        self.assertEqual(len(self.requests), 2)
        self.assertGreaterEqual(self.requests[1] - self.requests[0], 1)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'ok': True})

    def test_real_worker_retry_exhaustion_returns_http_status(self):
        self.exhaust = True
        for status in (503, 429):
            with self.subTest(status=status):
                self.status = status
                self.requests.clear()
                response = self.fetch()
                self.assertEqual(len(self.requests), 3)
                self.assertEqual(response.status_code, status)
