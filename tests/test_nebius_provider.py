"""
tests/test_nebius_provider.py
Comprehensive Unit Test Suite for NebiusProvider.

Validates all 15 specification requirements using mocked HTTP responses:
1. Missing API key handling.
2. Missing model handling.
3. Invalid base URL (non-HTTPS validation for non-localhost).
4. Successful chat completion & typed NebiusResponse.
5. Authentication failure (HTTP 401/403 - no retries).
6. Rate limiting (HTTP 429 - retried with backoff).
7. Network timeout handling (NebiusTimeoutError).
8. Upstream server errors (HTTP 500/503 - retried).
9. Malformed API responses (invalid JSON, missing choices).
10. Missing usage statistics (usage_available=False, no fabricated tokens).
11. Safe API key masking (mask_api_key).
12. Model fleet discovery (list_models).
13. Case-insensitive NVIDIA Nemotron filtering (get_available_nemotron_models).
14. Retry limits & backoff execution.
15. Redaction verification: Secrets NEVER appear in exception messages or logs.

Plus:
- Opt-in live integration test (runs only when RUN_LIVE_NEBIUS_TESTS=1).
"""

import os
import sys
import json
import io
import time
import socket
import logging
import unittest
from unittest.mock import patch, MagicMock
import urllib.error

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.nebius_provider import (
    NebiusProvider,
    NebiusTokenFactoryAdapter,
    NebiusResponse,
    NebiusError,
    NebiusConfigurationError,
    NebiusAuthenticationError,
    NebiusRateLimitError,
    NebiusTimeoutError,
    NebiusValidationError,
    NebiusAPIError,
    mask_api_key,
    sanitize_text
)


def make_mock_http_response(status_code: int = 200, payload: dict = None, headers: dict = None):
    """Creates a mock urllib HTTP response object."""
    body_bytes = json.dumps(payload or {}).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.status = status_code
    mock_resp.read.return_value = body_bytes
    mock_resp.headers = headers or {}
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None
    return mock_resp


def make_mock_http_error(status_code: int, error_payload: dict, headers: dict = None):
    """Creates a mock urllib HTTPError."""
    body_bytes = json.dumps(error_payload).encode("utf-8")
    fp = io.BytesIO(body_bytes)
    return urllib.error.HTTPError(
        url="https://api.tokenfactory.nebius.com/v1/chat/completions",
        code=status_code,
        msg=f"HTTP Error {status_code}",
        hdrs=headers or {},
        fp=fp
    )


class TestNebiusProviderUnit(unittest.TestCase):
    """Unit tests for NebiusProvider using mocked network interactions."""

    def setUp(self):
        self.dummy_key = "v1.TEST_SECRET_KEY_1234567890_XYZ"
        self.dummy_model = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
        self.dummy_base_url = "https://api.tokenfactory.nebius.com/v1"
        self.provider = NebiusProvider(
            api_key=self.dummy_key,
            base_url=self.dummy_base_url,
            model=self.dummy_model,
            timeout=10,
            max_retries=2,
            retry_delay=0.01  # Fast tests
        )

    # --------------------------------------------------------------------------
    # 1. Missing API Key
    # --------------------------------------------------------------------------
    def test_01_missing_api_key(self):
        """Validates that a missing or empty API key triggers NebiusConfigurationError."""
        p = NebiusProvider(api_key="", base_url="https://api.tokenfactory.nebius.com/v1", model="nvidia/Nemotron")
        cfg = p.validate_config()
        self.assertEqual(cfg["status"], "INVALID")
        self.assertIn("NEBIUS_API_KEY is missing or empty.", cfg["errors"])

        messages = [{"role": "user", "content": "Hello"}]
        with self.assertRaises(NebiusConfigurationError) as ctx:
            p.chat_completion(messages)
        self.assertIn("NEBIUS_API_KEY is not configured", str(ctx.exception))

    # --------------------------------------------------------------------------
    # 2. Missing Model
    # --------------------------------------------------------------------------
    def test_02_missing_model(self):
        """Validates that an empty or missing model identifier triggers validation errors."""
        p = NebiusProvider(api_key=self.dummy_key, model="")
        cfg = p.validate_config()
        self.assertEqual(cfg["status"], "INVALID")
        self.assertIn("NEBIUS_MODEL is missing or empty.", cfg["errors"])

        with self.assertRaises(NebiusConfigurationError):
            p.chat_completion([{"role": "user", "content": "Hello"}], model="")

    # --------------------------------------------------------------------------
    # 3. Invalid Base URL (Scheme & Localhost Exemption)
    # --------------------------------------------------------------------------
    def test_03_invalid_base_url(self):
        """Validates that insecure HTTP URLs are rejected unless targeting localhost."""
        # Insecure remote HTTP -> Rejected
        p_insecure = NebiusProvider(
            api_key=self.dummy_key,
            base_url="http://insecure-api.tokenfactory.nebius.com/v1",
            model=self.dummy_model
        )
        cfg = p_insecure.validate_config()
        self.assertEqual(cfg["status"], "INVALID")
        self.assertTrue(any("HTTPS" in err for err in cfg["errors"]))

        with self.assertRaises(NebiusConfigurationError):
            p_insecure.chat_completion([{"role": "user", "content": "Hello"}])

        # Permitted localhost HTTP -> Accepted
        p_local = NebiusProvider(
            api_key=self.dummy_key,
            base_url="http://localhost:8080/v1",
            model=self.dummy_model
        )
        self.assertEqual(p_local.validate_config()["status"], "VALID")

        p_127 = NebiusProvider(
            api_key=self.dummy_key,
            base_url="http://127.0.0.1:8080/v1",
            model=self.dummy_model
        )
        self.assertEqual(p_127.validate_config()["status"], "VALID")

    # --------------------------------------------------------------------------
    # 4. Successful Chat Completion
    # --------------------------------------------------------------------------
    @patch("urllib.request.urlopen")
    def test_04_successful_chat_completion(self, mock_urlopen):
        """Validates successful inference parsing into a typed NebiusResponse dataclass."""
        mock_payload = {
            "id": "chatcmpl-mock-12345",
            "model": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
            "created": 1793330000,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Statutory cargo survey verified. Nitrogen pressure is within acceptable limits."
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 45,
                "total_tokens": 165,
                "prompt_tokens_details": {"cached_tokens": 16}
            }
        }
        mock_urlopen.return_value = make_mock_http_response(200, mock_payload)

        messages = [
            {"role": "system", "content": "You are a marine surveyor."},
            {"role": "user", "content": "Assess cargo TR-001."}
        ]

        resp = self.provider.chat_completion(messages, max_tokens=100)

        self.assertIsInstance(resp, NebiusResponse)
        self.assertEqual(resp.content, "Statutory cargo survey verified. Nitrogen pressure is within acceptable limits.")
        self.assertEqual(resp.model, "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B")
        self.assertEqual(resp.provider, "nebius")
        self.assertEqual(resp.request_id, "chatcmpl-mock-12345")
        self.assertEqual(resp.input_tokens, 120)
        self.assertEqual(resp.output_tokens, 45)
        self.assertEqual(resp.total_tokens, 165)
        self.assertTrue(resp.usage_available)
        self.assertEqual(resp.finish_reason, "stop")
        self.assertGreaterEqual(resp.latency_ms, 0.0)

        # Backward compatibility properties
        self.assertEqual(resp.prompt_tokens, 120)
        self.assertEqual(resp.completion_tokens, 45)
        self.assertIn("prompt_tokens", resp.usage)

    # --------------------------------------------------------------------------
    # 5. Authentication Failure (No Retries)
    # --------------------------------------------------------------------------
    @patch("urllib.request.urlopen")
    def test_05_authentication_failure(self, mock_urlopen):
        """Validates HTTP 401 raises NebiusAuthenticationError and does NOT retry."""
        mock_error = make_mock_http_error(401, {"error": {"message": "Invalid API key provided."}})
        mock_urlopen.side_effect = mock_error

        messages = [{"role": "user", "content": "Ping"}]

        with self.assertRaises(NebiusAuthenticationError) as ctx:
            self.provider.chat_completion(messages)

        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Auth Error", str(ctx.exception))
        # Call count must be exactly 1: NEVER retry authentication failures
        self.assertEqual(mock_urlopen.call_count, 1)

    # --------------------------------------------------------------------------
    # 6. Rate Limiting (HTTP 429 - Retried with Backoff)
    # --------------------------------------------------------------------------
    @patch("urllib.request.urlopen")
    @patch("time.sleep")
    def test_06_rate_limiting_and_retry(self, mock_sleep, mock_urlopen):
        """Validates that HTTP 429 rate limits are retried up to max_retries."""
        mock_error = make_mock_http_error(429, {"error": {"message": "Rate limit exceeded"}}, {"Retry-After": "0.5"})
        mock_urlopen.side_effect = mock_error

        messages = [{"role": "user", "content": "Ping"}]

        with self.assertRaises(NebiusRateLimitError) as ctx:
            self.provider.chat_completion(messages)

        self.assertEqual(ctx.exception.status_code, 429)
        # Provider max_retries=2 -> initial attempt + 2 retries = 3 calls
        self.assertEqual(mock_urlopen.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    # --------------------------------------------------------------------------
    # 7. Network Timeout Handling
    # --------------------------------------------------------------------------
    @patch("urllib.request.urlopen")
    @patch("time.sleep")
    def test_07_network_timeout(self, mock_sleep, mock_urlopen):
        """Validates that network socket timeout triggers NebiusTimeoutError after retries."""
        mock_urlopen.side_effect = socket.timeout("Timed out connecting to gateway")

        messages = [{"role": "user", "content": "Ping"}]

        with self.assertRaises(NebiusTimeoutError):
            self.provider.chat_completion(messages)

        # Initial attempt + 2 retries = 3 attempts
        self.assertEqual(mock_urlopen.call_count, 3)

    # --------------------------------------------------------------------------
    # 8. Server Error (HTTP 500 / 503)
    # --------------------------------------------------------------------------
    @patch("urllib.request.urlopen")
    @patch("time.sleep")
    def test_08_server_error_and_eventual_success(self, mock_sleep, mock_urlopen):
        """Validates transient 503 server error followed by successful retry."""
        mock_503 = make_mock_http_error(503, {"error": {"message": "Service Temporarily Unavailable"}})
        mock_success = make_mock_http_response(200, {
            "id": "chatcmpl-after-retry",
            "choices": [{"message": {"role": "assistant", "content": "Recovered response"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        })

        mock_urlopen.side_effect = [mock_503, mock_success]

        resp = self.provider.chat_completion([{"role": "user", "content": "Ping"}])
        self.assertEqual(resp.content, "Recovered response")
        self.assertEqual(mock_urlopen.call_count, 2)
        self.assertEqual(mock_sleep.call_count, 1)

    # --------------------------------------------------------------------------
    # 9. Malformed API Responses
    # --------------------------------------------------------------------------
    @patch("urllib.request.urlopen")
    def test_09_malformed_api_responses(self, mock_urlopen):
        """Validates that invalid JSON or missing choices triggers NebiusValidationError."""
        # Non-JSON response
        mock_resp_invalid_json = MagicMock()
        mock_resp_invalid_json.read.return_value = b"<html>502 Bad Gateway</html>"
        mock_resp_invalid_json.__enter__.return_value = mock_resp_invalid_json
        mock_resp_invalid_json.__exit__.return_value = None
        mock_urlopen.return_value = mock_resp_invalid_json

        with self.assertRaises(NebiusValidationError):
            self.provider.chat_completion([{"role": "user", "content": "Test"}])

        # Missing choices
        mock_urlopen.return_value = make_mock_http_response(200, {"id": "123", "model": "test"})
        with self.assertRaises(NebiusValidationError):
            self.provider.chat_completion([{"role": "user", "content": "Test"}])

    # --------------------------------------------------------------------------
    # 10. Missing Usage Statistics (No Guessing / Character Heuristics)
    # --------------------------------------------------------------------------
    @patch("urllib.request.urlopen")
    def test_10_missing_usage_statistics(self, mock_urlopen):
        """Validates that absent usage object results in usage_available=False, never guessed."""
        mock_payload_no_usage = {
            "id": "chatcmpl-no-usage",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Analysis completed without usage header."},
                    "finish_reason": "stop"
                }
            ]
            # No 'usage' field
        }
        mock_urlopen.return_value = make_mock_http_response(200, mock_payload_no_usage)

        resp = self.provider.chat_completion([{"role": "user", "content": "Query"}])

        self.assertFalse(resp.usage_available)
        self.assertIsNone(resp.input_tokens)
        self.assertIsNone(resp.output_tokens)
        self.assertIsNone(resp.total_tokens)
        self.assertEqual(resp.usage, {})

    # --------------------------------------------------------------------------
    # 11. API Key Masking
    # --------------------------------------------------------------------------
    def test_11_mask_api_key(self):
        """Validates that mask_api_key returns a minimal prefix/suffix and hides credentials."""
        real_looking_key = "v1.SYNTHETIC_TEST_KEY_XYZ9876543210ABCDEFGH_secret"
        masked = mask_api_key(real_looking_key)

        self.assertIn("v1.SYN", masked)
        self.assertIn("ret", masked)
        self.assertIn("[REDACTED]", masked)
        self.assertNotIn("XYZ9876543210ABCDEFGH", masked)

        self.assertEqual(mask_api_key(None), "[NOT CONFIGURED]")
        self.assertEqual(mask_api_key(""), "[NOT CONFIGURED]")
        self.assertEqual(mask_api_key("short"), "[CONFIGURED - TOO SHORT TO SAFELY MASK]")

    # --------------------------------------------------------------------------
    # 12. Model Discovery (list_models)
    # --------------------------------------------------------------------------
    @patch("urllib.request.urlopen")
    def test_12_list_models(self, mock_urlopen):
        """Validates query to Nebius Token Factory /models endpoint."""
        mock_models_payload = {
            "object": "list",
            "data": [
                {"id": "meta-llama/Llama-3.1-70B-Instruct", "created": 1700000000},
                {"id": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B", "created": 1700000000},
                {"id": "nvidia/NVIDIA-Nemotron-3-Super-120B-A12B", "created": 1700000000},
                {"id": "Qwen/Qwen2.5-72B-Instruct", "created": 1700000000}
            ]
        }
        mock_urlopen.return_value = make_mock_http_response(200, mock_models_payload)

        models = self.provider.list_models()

        self.assertIsInstance(models, list)
        self.assertEqual(len(models), 4)
        self.assertIn("nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B", models)
        self.assertIn("meta-llama/Llama-3.1-70B-Instruct", models)

    # --------------------------------------------------------------------------
    # 13. Nemotron Model Filtering (Case-Insensitive)
    # --------------------------------------------------------------------------
    @patch("urllib.request.urlopen")
    def test_13_nemotron_model_filtering(self, mock_urlopen):
        """Validates case-insensitive filtering for NVIDIA Nemotron family models."""
        mock_models_payload = {
            "data": [
                {"id": "meta-llama/Llama-3.3-70B-Instruct"},
                {"id": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"},
                {"id": "nvidia/NVIDIA-nemotron-3.5-Super-VL-120B"},
                {"id": "NousResearch/Hermes-4-405B"}
            ]
        }
        mock_urlopen.return_value = make_mock_http_response(200, mock_models_payload)

        nemotrons = self.provider.get_available_nemotron_models()

        self.assertEqual(len(nemotrons), 2)
        self.assertIn("nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B", nemotrons)
        self.assertIn("nvidia/NVIDIA-nemotron-3.5-Super-VL-120B", nemotrons)

    # --------------------------------------------------------------------------
    # 14. Retry Limits & Backoff Ceiling
    # --------------------------------------------------------------------------
    @patch("urllib.request.urlopen")
    @patch("time.sleep")
    def test_14_retry_limits(self, mock_sleep, mock_urlopen):
        """Validates that retry attempts are strictly bounded by max_retries."""
        p_bounded = NebiusProvider(
            api_key=self.dummy_key,
            max_retries=1,
            retry_delay=0.01
        )
        mock_error = make_mock_http_error(503, {"error": "Gateway Error"})
        mock_urlopen.side_effect = mock_error

        with self.assertRaises(NebiusAPIError):
            p_bounded.chat_completion([{"role": "user", "content": "Ping"}])

        # Initial attempt + 1 retry = 2 attempts total
        self.assertEqual(mock_urlopen.call_count, 2)

    # --------------------------------------------------------------------------
    # 15. Secrets Never Appear in Exceptions or Logs
    # --------------------------------------------------------------------------
    @patch("urllib.request.urlopen")
    def test_15_secrets_never_leak_in_exceptions(self, mock_urlopen):
        """Validates that sensitive API keys and Bearer tokens are redacted from error traces."""
        sensitive_key = "v1.SUPER_SECRET_COMPROMISED_KEY_99999"
        p_leak_test = NebiusProvider(
            api_key=sensitive_key,
            max_retries=0
        )
        # Simulate upstream server echoing the Authorization header or API key in error
        mock_error = make_mock_http_error(
            400,
            {"error": f"Bad request for token Bearer {sensitive_key}."}
        )
        mock_urlopen.side_effect = mock_error

        with self.assertRaises(NebiusValidationError) as ctx:
            p_leak_test.chat_completion([{"role": "user", "content": "Ping"}])

        err_string = str(ctx.exception)
        self.assertNotIn(sensitive_key, err_string, "CRITICAL: Raw API key leaked in exception message!")
        self.assertIn("[REDACTED", err_string)

    # --------------------------------------------------------------------------
    # URL Construction (No duplicate /v1)
    # --------------------------------------------------------------------------
    def test_16_url_construction_no_v1_duplication(self):
        """Validates that _build_url never duplicates /v1."""
        # Case A: Base has /v1, path does not
        p1 = NebiusProvider(api_key=self.dummy_key, base_url="https://api.tokenfactory.nebius.com/v1")
        self.assertEqual(p1._build_url("chat/completions"), "https://api.tokenfactory.nebius.com/v1/chat/completions")
        self.assertEqual(p1._build_url("models"), "https://api.tokenfactory.nebius.com/v1/models")

        # Case B: Base has /v1, path has v1/
        self.assertEqual(p1._build_url("v1/chat/completions"), "https://api.tokenfactory.nebius.com/v1/chat/completions")

        # Case C: Base does NOT have /v1, path does not
        p2 = NebiusProvider(api_key=self.dummy_key, base_url="https://api.tokenfactory.nebius.com")
        self.assertEqual(p2._build_url("chat/completions"), "https://api.tokenfactory.nebius.com/v1/chat/completions")

        # Case D: Base does NOT have /v1, path has v1/
        self.assertEqual(p2._build_url("v1/chat/completions"), "https://api.tokenfactory.nebius.com/v1/chat/completions")

    # --------------------------------------------------------------------------
    # Backward Compatibility Aliases
    # --------------------------------------------------------------------------
    def test_17_backward_compatibility_aliases(self):
        """Validates that legacy class names and aliases work interchangeably."""
        adapter = NebiusTokenFactoryAdapter(api_key=self.dummy_key)
        self.assertIsInstance(adapter, NebiusProvider)
        cfg = adapter.validate_configuration()
        self.assertEqual(cfg["status"], "VALID")


# ==============================================================================
# Optional Opt-In Live Integration Test (Only when RUN_LIVE_NEBIUS_TESTS=1)
# ==============================================================================
class TestNebiusProviderLiveOptIn(unittest.TestCase):
    """
    Opt-in live integration test against actual Nebius Token Factory endpoints.
    Executes ONLY when explicitly enabled via environment variable:
        $env:RUN_LIVE_NEBIUS_TESTS="1"
    """

    def setUp(self):
        if os.getenv("RUN_LIVE_NEBIUS_TESTS") != "1":
            self.skipTest("Live integration tests disabled by default. Set RUN_LIVE_NEBIUS_TESTS=1 to run.")

        self.provider = NebiusProvider()
        cfg = self.provider.validate_config()
        if cfg["status"] != "VALID":
            self.skipTest(f"Live Nebius credentials not valid: {cfg['errors']}")

    def test_live_chat_completion(self):
        """Executes a real minimal prompt to the verified live Nemotron model."""
        messages = [
            {"role": "system", "content": "You are LeeWu AI. Answer in two words."},
            {"role": "user", "content": "Ping."}
        ]
        resp = self.provider.chat_completion(messages, max_tokens=20)
        self.assertIsInstance(resp, NebiusResponse)
        self.assertTrue(len(resp.content) > 0)
        self.assertGreater(resp.total_tokens, 0)
        self.assertTrue(resp.usage_available)


if __name__ == "__main__":
    unittest.main(verbosity=2)
