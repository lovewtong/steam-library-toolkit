import base64
import json
import time
import types
import unittest
from unittest.mock import Mock, patch

import steam_auth
from steam_sources import AccountMismatchError

ACCOUNT = "76561198000000001"


def token(payload):
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return "header." + body + ".signature"


class AuthenticationTests(unittest.TestCase):
    def test_expired_malformed_and_wrong_account_tokens_rejected(self):
        good = token({"sub": ACCOUNT, "exp": time.time() + 600})
        self.assertEqual(steam_auth.validate_token(good, ACCOUNT), ACCOUNT)
        with self.assertRaises(AccountMismatchError):
            steam_auth.validate_token(good, "76561198000000002")
        for bad in (None, "secret", token([]), token({"sub": ACCOUNT, "exp": 0}),
                    token({"sub": ACCOUNT, "exp": "later"})):
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
