"""
scratch/test_security_remediation.py
Automated Security Remediation Verification Suite for LeeWu AI.

Tests:
1. Telegram authorization: allowed user ID, allowed chat ID, allowed username (case-insensitive, with/without @).
2. Telegram authorization: unauthorized user ID rejected.
3. Telegram authorization: empty allowlist fails closed (rejects all by default).
4. Missing credentials fail safely: TELEGRAM_BOT_TOKEN missing triggers safe failure.
5. Missing credentials fail safely: NEBIUS_API_KEY missing triggers safe warning message without crash.
6. Secret redaction: safe_log_err scrubs bot tokens, Nebius keys, and Bearer tokens.
"""

import os
import sys
import io
import unittest
from unittest.mock import patch

# Point to target repository
REPO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "LeeWuAiDevpostnVidia"))
if REPO_DIR not in sys.path:
    sys.path.insert(0, REPO_DIR)

import telegram_bot_daemon as daemon


class TestSecurityRemediation(unittest.TestCase):

    def setUp(self):
        # Save original environment
        self.orig_env = os.environ.copy()

    def tearDown(self):
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.orig_env)

    def test_01_telegram_authorization_allowed_entities(self):
        """Tests that authorized numeric chat IDs and numeric user IDs pass authorization, while usernames are rejected."""
        # Hardened security: numeric IDs only
        allowed_chat = "123456789,987654321"
        allowed_users = "555666777"

        # Case A: Allowed numeric chat ID
        auth, reason = daemon.is_authorized(123456789, {"id": 111, "username": "stranger"}, chat_id_env=allowed_chat, allowed_users_env=allowed_users)
        self.assertTrue(auth, f"Failed for allowed chat ID: {reason}")

        # Case B: Allowed numeric user ID
        auth, reason = daemon.is_authorized(999999999, {"id": 555666777, "username": "random_name"}, chat_id_env=allowed_chat, allowed_users_env=allowed_users)
        self.assertTrue(auth, f"Failed for allowed user ID: {reason}")

        # Case C: Username alone without matching numeric ID is strictly rejected
        auth, reason = daemon.is_authorized(999999999, {"id": 222, "username": "maritime_surveyor"}, chat_id_env=allowed_chat, allowed_users_env=allowed_users)
        self.assertFalse(auth, "Username alone must never grant authorization")

    def test_02_telegram_authorization_unauthorized_rejected(self):
        """Tests that unauthorized entities are strictly blocked."""
        allowed_chat = "123456789"
        allowed_users = "555666777"

        auth, reason = daemon.is_authorized(999999999, {"id": 888888888, "username": "intruder_user"}, chat_id_env=allowed_chat, allowed_users_env=allowed_users)
        self.assertFalse(auth, "Intruder was incorrectly authorized!")
        self.assertIn("Unauthorized entity", reason)

    def test_03_telegram_authorization_fail_closed_on_empty_allowlist(self):
        """Tests that an empty allowlist fails closed by default."""
        os.environ["TELEGRAM_CHAT_ID"] = ""
        os.environ["TELEGRAM_ALLOWED_USERS"] = ""
        if "TELEGRAM_ALLOW_ALL" in os.environ:
            del os.environ["TELEGRAM_ALLOW_ALL"]

        auth, reason = daemon.is_authorized(123456789, {"id": 111, "username": "any_user"}, chat_id_env="", allowed_users_env="")
        self.assertFalse(auth, "Empty allowlist should fail closed!")
        self.assertIn("Access denied", reason)

    def test_04_missing_telegram_token_fails_safely(self):
        """Tests that missing TELEGRAM_BOT_TOKEN causes send_message to abort safely without crashing."""
        daemon.BOT_TOKEN = ""
        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            res = daemon.send_message(123456789, "Test Message")
            self.assertIsNone(res)
            self.assertIn("TELEGRAM_BOT_TOKEN is not configured", stderr_capture.getvalue())

    def test_05_missing_nebius_key_fails_safely(self):
        """Tests that missing NEBIUS_API_KEY returns safe diagnostic string without crashing."""
        os.environ["NEBIUS_API_KEY"] = ""
        daemon.NEBIUS_KEY = ""
        resp = daemon.query_nemotron_with_history(123456789, "Perform survey assessment", api_key="")
        self.assertIn("NEBIUS_API_KEY lipsește", resp)

    def test_06_secrets_never_appear_in_logs(self):
        """Tests that safe_log_err scrubs bot tokens, Nebius keys, and Bearer tokens."""
        daemon.BOT_TOKEN = "1111111111:AAESyntheticDummyBotTokenForTests_123"
        daemon.NEBIUS_KEY = "v1.synthetic_dummy_nebius_key_for_log_scrubbing_tests_1234567890abcdef"

        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            raw_err = f"Failed calling {daemon.BOT_TOKEN} with Authorization: Bearer {daemon.NEBIUS_KEY}"
            daemon.safe_log_err("TEST_ERROR", raw_err)

        log_output = stderr_capture.getvalue()
        self.assertNotIn(daemon.BOT_TOKEN, log_output, "Raw bot token leaked in error log!")
        self.assertNotIn(daemon.NEBIUS_KEY, log_output, "Raw Nebius key leaked in error log!")
        self.assertIn("[MASKED_BOT_TOKEN]", log_output)
        self.assertIn("[MASKED_NEBIUS_KEY]", log_output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
