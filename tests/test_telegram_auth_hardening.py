import os
import sys
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from telegram_bot_daemon import (
    parse_allowed_entities,
    is_authorized,
    safe_mask,
    mask_numeric_id,
    query_nemotron_with_history
)


class TestTelegramAuthHardening(unittest.TestCase):
    """
    Comprehensive test suite verifying P0 Telegram Authorization Hardening:
    - Removal of bypasses
    - Numeric-only ID enforcement
    - Rejection of usernames as credentials
    - Prevention of username spoofing
    - Handling of changed usernames
    - Fail-closed behavior on missing, empty, or malformed configuration
    - Redaction integrity (no credential fragments)
    """

    def setUp(self):
        # Clean environment before each test
        for var in ["TELEGRAM_CHAT_ID", "TELEGRAM_ALLOWED_USERS", "TELEGRAM_ALLOW_ALL", "NEBIUS_API_KEY"]:
            if var in os.environ:
                del os.environ[var]

    def test_01_empty_configuration_fails_closed(self):
        """Missing or empty configuration must deny access to all requests."""
        # Neither env var set
        allowed, is_valid, reason = parse_allowed_entities(chat_id_env="", allowed_users_env="")
        self.assertFalse(is_valid)
        self.assertEqual(len(allowed), 0)
        self.assertIn("Missing allowlist configuration", reason)

        # is_authorized must fail closed
        auth, auth_reason = is_authorized(123456789, {"id": 123456789}, chat_id_env="", allowed_users_env="")
        self.assertFalse(auth)
        self.assertIn("Access denied", auth_reason)

    def test_02_valid_numeric_configuration(self):
        """Valid comma-separated numeric IDs must parse correctly."""
        allowed, is_valid, reason = parse_allowed_entities(
            chat_id_env="987654321, -1001234567890",
            allowed_users_env="111222333, 444555666"
        )
        self.assertTrue(is_valid)
        self.assertEqual(allowed, {987654321, -1001234567890, 111222333, 444555666})

        # Authorized user by user ID
        auth_u, r_u = is_authorized(999999, {"id": 111222333}, chat_id_env="", allowed_users_env="111222333")
        self.assertTrue(auth_u)
        self.assertEqual(r_u, "Authorized by user ID")

        # Authorized user by chat ID (e.g. approved group)
        auth_c, r_c = is_authorized(-1001234567890, {"id": 999999}, chat_id_env="-1001234567890", allowed_users_env="")
        self.assertTrue(auth_c)
        self.assertEqual(r_c, "Authorized by chat ID")

    def test_03_username_spoofing_prevented(self):
        """
        Attacker claiming an admin's username but having an unauthorized numeric ID
        must be strictly REJECTED.
        """
        # Allowlist has numeric ID 111222333
        allowed_users = "111222333"
        chat_id_env = ""

        # Attacker with ID 999999999 sends username="admin_michael"
        attacker_user = {
            "id": 999999999,
            "username": "admin_michael",
            "first_name": "Michael",
            "is_bot": False
        }
        auth, reason = is_authorized(999999999, attacker_user, chat_id_env=chat_id_env, allowed_users_env=allowed_users)
        self.assertFalse(auth)
        self.assertIn("Unauthorized entity", reason)

    def test_04_changed_username_remains_authorized(self):
        """
        An authorized user who changes their Telegram handle must remain authorized
        because authentication is strictly numeric ID based.
        """
        allowed_users = "111222333"

        # User changed handle from @old_handle to @new_random_handle
        user_new_handle = {
            "id": 111222333,
            "username": "new_random_handle",
            "first_name": "Legitimate User"
        }
        auth, reason = is_authorized(888888, user_new_handle, chat_id_env="", allowed_users_env=allowed_users)
        self.assertTrue(auth)
        self.assertEqual(reason, "Authorized by user ID")

        # User with no handle at all
        user_no_handle = {
            "id": 111222333,
            "first_name": "No Handle User"
        }
        auth2, reason2 = is_authorized(888888, user_no_handle, chat_id_env="", allowed_users_env=allowed_users)
        self.assertTrue(auth2)
        self.assertEqual(reason2, "Authorized by user ID")

    def test_05_missing_ids_in_request_rejected(self):
        """Incoming payloads with missing, null, or empty user/chat IDs must be rejected."""
        allowed_users = "111222333"

        # Missing both chat_id and user_id
        auth1, r1 = is_authorized(None, {}, chat_id_env="", allowed_users_env=allowed_users)
        self.assertFalse(auth1)
        self.assertIn("Missing or invalid numeric ID", r1)

        # Null IDs
        auth2, r2 = is_authorized(None, {"id": None}, chat_id_env="", allowed_users_env=allowed_users)
        self.assertFalse(auth2)
        self.assertIn("Missing or invalid numeric ID", r2)

        # Empty string IDs
        auth3, r3 = is_authorized("", {"id": ""}, chat_id_env="", allowed_users_env=allowed_users)
        self.assertFalse(auth3)
        self.assertIn("Missing or invalid numeric ID", r3)

    def test_06_malformed_configuration_fails_closed(self):
        """
        Allowlist configurations containing usernames, invalid strings, or non-numeric
        tokens must fail closed and deny all access.
        """
        # Contains username with @
        allowed1, valid1, r1 = parse_allowed_entities(chat_id_env="123456", allowed_users_env="@admin_user")
        self.assertFalse(valid1)
        self.assertEqual(len(allowed1), 0)
        self.assertIn("Malformed allowlist configuration", r1)

        auth1, _ = is_authorized(123456, {"id": 123456}, chat_id_env="123456", allowed_users_env="@admin_user")
        self.assertFalse(auth1)

        # Contains alphanumeric junk
        allowed2, valid2, r2 = parse_allowed_entities(chat_id_env="invalid_chat_id", allowed_users_env="")
        self.assertFalse(valid2)
        self.assertEqual(len(allowed2), 0)

        # Trailing garbage
        allowed3, valid3, r3 = parse_allowed_entities(chat_id_env="123456, 789abc", allowed_users_env="")
        self.assertFalse(valid3)

    def test_07_telegram_allow_all_bypass_neutralized(self):
        """TELEGRAM_ALLOW_ALL must have zero effect; unauthorized users remain blocked."""
        os.environ["TELEGRAM_ALLOW_ALL"] = "true"
        allowed_users = "111222333"

        unauthorized_user = {"id": 999999999, "username": "attacker"}
        auth, reason = is_authorized(999999999, unauthorized_user, chat_id_env="", allowed_users_env=allowed_users)
        self.assertFalse(auth)
        self.assertIn("Unauthorized entity", reason)

        # Also test with "1"
        os.environ["TELEGRAM_ALLOW_ALL"] = "1"
        auth2, _ = is_authorized(999999999, unauthorized_user, chat_id_env="", allowed_users_env=allowed_users)
        self.assertFalse(auth2)

    def test_08_safe_mask_and_redaction(self):
        """Credentials must never display prefix, suffix, or raw fragments."""
        dummy_token = "123456789:ABCdefGHIjklMNOpqrSTUvwxYZ_1234567890"
        masked = safe_mask(dummy_token)
        self.assertEqual(masked, "[CONFIGURED]")
        self.assertNotIn("1234", masked)
        self.assertNotIn("7890", masked)

        masked_empty = safe_mask("")
        self.assertEqual(masked_empty, "[NOT SET]")

        # Test mask_numeric_id
        num_mask = mask_numeric_id(123456789)
        self.assertEqual(num_mask, "***6789")
        self.assertNotIn("12345", num_mask)

    def test_09_nebius_inference_safe_failure_without_key(self):
        """Nebius inference must fail safely with localized error when key is missing."""
        # 1. Explicit empty key
        reply = query_nemotron_with_history(12345, "Test prompt", api_key="")
        self.assertIn("NEBIUS_API_KEY lipsește", reply)
        self.assertTrue(reply.startswith("⚠️"))

        # 2. Environment variable empty
        os.environ["NEBIUS_API_KEY"] = ""
        reply2 = query_nemotron_with_history(12345, "Test prompt")
        self.assertIn("NEBIUS_API_KEY lipsește", reply2)
        self.assertTrue(reply2.startswith("⚠️"))



    def test_10_chat_history_isolation(self):
        """Context history must be strictly partitioned by chat ID with zero cross-talk."""
        import telegram_bot_daemon
        chat_a = 11111
        chat_b = 22222

        telegram_bot_daemon.clear_chat_history(chat_a)
        telegram_bot_daemon.clear_chat_history(chat_b)

        telegram_bot_daemon.save_chat_message(chat_a, "user", "Message for Chat A")
        telegram_bot_daemon.save_chat_message(chat_b, "user", "Message for Chat B")

        ctx_a = telegram_bot_daemon.get_recent_context(chat_a)
        ctx_b = telegram_bot_daemon.get_recent_context(chat_b)

        self.assertEqual(len(ctx_a), 1)
        self.assertEqual(ctx_a[0]["content"], "Message for Chat A")
        self.assertEqual(len(ctx_b), 1)
        self.assertEqual(ctx_b[0]["content"], "Message for Chat B")

    def test_11_chat_history_100_limit(self):
        """Enforce strict 100-message retention cap per chat."""
        import telegram_bot_daemon
        chat_id = 33333
        telegram_bot_daemon.clear_chat_history(chat_id)

        for i in range(105):
            telegram_bot_daemon.save_chat_message(chat_id, "user", f"Msg {i}")

        all_hist = telegram_bot_daemon.load_all_history()
        self.assertEqual(len(all_hist[str(chat_id)]), 100)
        self.assertEqual(all_hist[str(chat_id)][-1]["content"], "Msg 104")

    def test_12_clear_chat_history_reports_status(self):
        """clear_chat_history must return boolean status."""
        import telegram_bot_daemon
        chat_id = 44444
        telegram_bot_daemon.save_chat_message(chat_id, "user", "Test before clear")
        success = telegram_bot_daemon.clear_chat_history(chat_id)
        self.assertTrue(success)
        self.assertEqual(len(telegram_bot_daemon.get_recent_context(chat_id)), 0)

if __name__ == "__main__":
    unittest.main()
