import base64
import io
import json
import queue
import time
import sys
import types
import unittest
from unittest.mock import Mock, patch
from contextlib import ExitStack, redirect_stderr

import steam_auth
import steam_collect
from steam_sources import AccountMismatchError

ACCOUNT = "76561198000000001"


def token(payload):
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return "header." + body + ".signature"


class AuthenticationTests(unittest.TestCase):
    def bridge(self, received, clock=None):
        stack = ExitStack()
        self.addCleanup(stack.close)
        process = Mock(stdin=io.StringIO(), stdout=io.StringIO(), returncode=0)
        process.poll.return_value = None
        stack.enter_context(patch("steam_auth.local_credentials", return_value=(ACCOUNT, "private-token")))
        stack.enter_context(patch("steam_auth.shutil.which", return_value="node"))
        stack.enter_context(patch("steam_auth.subprocess.Popen", return_value=process))
        stack.enter_context(patch("steam_auth.threading.Thread"))
        events = stack.enter_context(patch("steam_auth.queue.Queue")).return_value
        events.get.side_effect = received
        stack.enter_context(patch("steam_auth.urllib.request.proxy_bypass", return_value=False))
        stack.enter_context(patch("steam_auth.urllib.request.getproxies", return_value={"https": "http://secret@localhost:7890"}))
        if clock:
            stack.enter_context(patch("steam_auth.time.monotonic", side_effect=clock))
        return process

    def test_bridge_reports_waiting_and_preserves_connection_timeout_without_secrets(self):
        now = [0]
        calls = [0]
        def received(**kwargs):
            calls[0] += 1
            if calls[0] == 1:
                return json.dumps({"event": "progress", "stage": "connecting_cm"})
            if calls[0] == 2:
                now[0] = 11
                raise queue.Empty()
            return json.dumps({"event": "error", "code": "CM_CONNECT_TIMEOUT", "message": "private-token"})
        process = self.bridge(received, clock=lambda: now[0])
        progress = []
        with self.assertRaises(steam_auth.AuthError) as result:
            steam_auth.collect_client(local_session=True, on_progress=progress.append)
        self.assertEqual(result.exception.code, "CM_CONNECT_TIMEOUT")
        output = "\n".join(progress) + str(result.exception)
        self.assertIn("11 秒", output)
        self.assertIn("CM", output)
        self.assertNotIn("private-token", output)
        self.assertNotIn("secret@", output)
        process.kill.assert_called_once()
        self.assertTrue(process.stdout.closed)

    def test_bridge_cleans_up_child_when_interrupted(self):
        process = self.bridge(KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt):
            steam_auth.collect_client(local_session=True, on_progress=lambda _: None)
        process.kill.assert_called_once()
        process.wait.assert_called_once()
        self.assertTrue(process.stdout.closed)

    def test_cli_interrupt_exits_cleanly_without_publishing(self):
        stderr = io.StringIO()
        with patch.object(sys, "argv", ["steam_collect.py", "--local-session", "--no-store"]), \
                patch("steam_collect.collect", side_effect=KeyboardInterrupt()), \
                patch("steam_runs.publish_run") as publish, redirect_stderr(stderr), \
                self.assertRaises(SystemExit) as result:
            steam_collect.main()
        self.assertEqual(result.exception.code, 130)
        self.assertIn("中断", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())
        publish.assert_not_called()

    @unittest.skipUnless(sys.platform == "win32", "Windows local-session dependency check")
    def test_missing_vdf_reports_dependency_not_steam_login_failure(self):
        with patch.dict("sys.modules", {"vdf": None}), self.assertRaises(steam_auth.AuthError) as result:
            steam_auth.local_credentials()
        self.assertEqual(result.exception.code, "PYTHON_DEPENDENCY_MISSING")
        self.assertIn("vdf", str(result.exception))

    @patch("steam_collect.load_config", return_value={"steam_id": ACCOUNT, "api_key": ""})
    @patch("steam_collect.collect_client", side_effect=steam_auth.AuthError("PYTHON_DEPENDENCY_MISSING", "缺少 vdf"))
    def test_collect_keeps_actionable_dependency_error(self, client, config):
        with self.assertRaisesRegex(RuntimeError, "PYTHON_DEPENDENCY_MISSING") as result:
            steam_collect.collect(fetch_store=False, use_api=False, use_client=True, local_session=True)
        self.assertIn("缺少 vdf", str(result.exception))

    def test_expired_malformed_and_wrong_account_tokens_rejected(self):
        good = token({"sub": ACCOUNT, "exp": time.time() + 600})
        self.assertEqual(steam_auth.validate_token(good, ACCOUNT), ACCOUNT)
        with self.assertRaises(AccountMismatchError):
            steam_auth.validate_token(good, "76561198000000002")
        for bad in (None, "secret", token([]), token({"sub": ACCOUNT, "exp": 0}),
                    token({"sub": ACCOUNT, "exp": "later"}),
                    *(token({"sub": ACCOUNT, "exp": value}) for value in (float('nan'), float('inf'), -float('inf'))),
                    token({"sub": '７' * 17, "exp": time.time() + 600})):
            with self.subTest(bad=type(bad).__name__), self.assertRaises(ValueError):
                steam_auth.validate_token(bad)

    def test_plaintext_keyring_backend_is_rejected(self):
        backend_type = type("PlaintextKeyring", (), {"priority": 1, "__module__": "keyrings.alt.file"})
        module = types.SimpleNamespace(get_keyring=lambda: backend_type())
        with patch.dict("sys.modules", {"keyring": module}), self.assertRaises(RuntimeError):
            steam_auth.secret_store()

    @patch("steam_auth.secret_store")
    def test_saved_credentials_bound_to_selected_account(self, secret_store):
        store = Mock()
        secret_store.return_value = store
        store.get_password.side_effect = lambda service, name: token({"sub": ACCOUNT, "exp": time.time() + 600})
        with self.assertRaises(AccountMismatchError):
            steam_auth.saved_credentials("76561198000000002")
        self.assertEqual(store.get_password.call_args.args[1], "76561198000000002")


if __name__ == "__main__":
    unittest.main()
