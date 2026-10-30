"""
tests/test_nebius_integration.py
End-to-End Integration Test Suite for Nebius Token Factory Adapter.

By default, uses a deterministic local OpenAI-compatible mock server so security and CI test
runs do not consume paid Nebius API credits unnecessarily. Set RUN_LIVE_NEBIUS_TESTS=1 to hit
the live Nebius Token Factory API.
"""

import http.server
import json
import os
import socket
import sys
import threading
import time
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.nebius_provider import (
    NebiusTokenFactoryAdapter,
    NebiusResponse,
    NebiusException,
    NebiusConfigurationError,
    NebiusAuthenticationError,
    NebiusAPIError,
    NebiusValidationError
)


class _AdapterMockServerHandler(http.server.BaseHTTPRequestHandler):
    """Mock Nebius OpenAI-compatible server for zero-cost integration testing."""
    expected_key = "v1.MOCK_ADAPTER_KEY_1234567890ABCDEF"

    def log_message(self, format, *args):
        pass

    def _send_json(self, code: int, payload: dict):
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _check_auth(self) -> bool:
        auth = self.headers.get("Authorization", "")
        if auth != f"Bearer {self.expected_key}":
            self._send_json(401, {"error": {"message": "Invalid authentication credentials", "type": "invalid_request_error"}})
            return False
        return True

    def do_GET(self):
        if not self._check_auth():
            return
        if self.path.endswith("/models"):
            self._send_json(200, {
                "object": "list",
                "data": [
                    {"id": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B", "object": "model"},
                    {"id": "nvidia/Llama-3_3-Nemotron-Super-49B-v1_5", "object": "model"}
                ]
            })
            return
        self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        if not self._check_auth():
            return
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}
        model = body.get("model", "")
        if "non-existent" in model:
            self._send_json(404, {"error": {"message": f"Model '{model}' does not exist", "type": "invalid_request_error"}})
            return

        content = (
            "### 1. Executive Cargo Condition Summary\n"
            "Heavy Industrial Transformer (115 MT) on board MV DEMO PACIFIC verified in sound statutory condition. "
            "Nitrogen blanket pressure (0.38 bar) and tri-axial shock logs (0.22 G longitudinal / 0.15 G transverse) "
            "comply with IMO CSS Code Annex 13 requirements. Recommend UNCONDITIONAL CLEAN MATE'S RECEIPT."
        )
        self._send_json(200, {
            "id": "chatcmpl-mock-adapter-001",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model or "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop"
            }],
            "usage": {"prompt_tokens": 120, "completion_tokens": 85, "total_tokens": 205}
        })


class TestNebiusTokenFactoryIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mock_server = None
        if os.environ.get("RUN_LIVE_NEBIUS_TESTS") == "1":
            cls.adapter = NebiusTokenFactoryAdapter()
            cls.mock_base_url = cls.adapter.base_url
        else:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", 0))
                port = s.getsockname()[1]
            cls.mock_server = http.server.HTTPServer(("127.0.0.1", port), _AdapterMockServerHandler)
            threading.Thread(target=cls.mock_server.serve_forever, daemon=True).start()
            cls.mock_base_url = f"http://127.0.0.1:{port}/v1"
            cls.adapter = NebiusTokenFactoryAdapter(
                api_key=_AdapterMockServerHandler.expected_key,
                base_url=cls.mock_base_url
            )
        cls.raw_key = cls.adapter.api_key

    @classmethod
    def tearDownClass(cls):
        if cls.mock_server is not None:
            cls.mock_server.shutdown()
            cls.mock_server.server_close()

    def test_01_configuration_audit_safe(self):
        """Verifies configuration audit succeeds without exposing raw secrets."""
        cfg = self.adapter.validate_configuration()
        self.assertEqual(cfg["status"], "VALID", f"Configuration audit failed: {cfg.get('errors')}")
        self.assertTrue(cfg["key_present"], "API key was not detected.")
        self.assertIn("REDACTED", cfg["key_masked"], "API key was not properly masked.")
        cfg_str = str(cfg)
        if self.raw_key and len(self.raw_key) > 10:
            self.assertNotIn(self.raw_key, cfg_str, "CRITICAL: Full raw API key leaked in configuration audit!")

    def test_02_model_discovery(self):
        """Verifies query to Nebius Token Factory /models endpoint."""
        models = self.adapter.list_models()
        self.assertIsInstance(models, list)
        self.assertGreater(len(models), 0, "No models returned from Nebius Token Factory.")

        nemotron_models = self.adapter.get_available_nemotron_models()
        self.assertIsInstance(nemotron_models, list)
        self.assertGreater(len(nemotron_models), 0, "No NVIDIA Nemotron models found in Nebius catalog.")
        self.assertIn(self.adapter.default_model, models)

    def test_03_real_chat_completion(self):
        """Executes a chat completion and validates the response object."""
        test_prompt = [
            {"role": "system", "content": "You are LeeWu AI. Answer directly in one short sentence."},
            {"role": "user", "content": "Confirm operational readiness for maritime survey operations."}
        ]
        t0 = time.time()
        resp = self.adapter.complete(test_prompt, max_tokens=250, temperature=0.1)
        latency = time.time() - t0

        self.assertIsInstance(resp, NebiusResponse)
        self.assertTrue(len(resp.content) > 0)
        self.assertIn(resp.finish_reason, ["stop", "length"])
        self.assertGreater(resp.total_tokens, 0)
        self.assertLess(latency, 45.0)

    def test_04_strict_error_handling_invalid_model(self):
        """Verifies that non-existent models raise NebiusAPIError and NEVER fall back silently."""
        invalid_model = "nvidia/non-existent-nemotron-model-999b-xyz"
        messages = [{"role": "user", "content": "Ping test."}]
        with self.assertRaises(NebiusAPIError) as ctx:
            self.adapter.complete(messages, model=invalid_model, max_tokens=50)
        err_msg = str(ctx.exception)
        self.assertTrue(len(err_msg) > 0)
        if self.raw_key and len(self.raw_key) > 10:
            self.assertNotIn(self.raw_key, err_msg)

    def test_05_strict_error_handling_invalid_key(self):
        """Verifies that invalid credentials trigger authentication errors without leaking keys."""
        bogus_adapter = NebiusTokenFactoryAdapter(
            api_key="v1.BOGUS_INVALID_KEY_999999999999999999999",
            base_url=self.mock_base_url
        )
        messages = [{"role": "user", "content": "Auth test."}]
        with self.assertRaises(NebiusException) as ctx:
            bogus_adapter.complete(messages, max_tokens=50)
        err_msg = str(ctx.exception)
        self.assertNotIn("v1.BOGUS_INVALID_KEY_999999999999999999999", err_msg)

    def test_06_domain_survey_assessment(self):
        """Validates high-level statutory survey note generation for LeeWu AI."""
        telemetry = {
            "n2_pressure_bar": 0.38,
            "impact_g": "0.22 G longitudinal / 0.15 G transverse",
            "timestamp": "2026-10-30 07:40:00 UTC"
        }
        resp = self.adapter.generate_survey_assessment(
            vessel_name="MV DEMO PACIFIC",
            cargo_description="Heavy Industrial Transformer 115 MT",
            telemetry=telemetry,
            max_tokens=500
        )
        self.assertIsInstance(resp, NebiusResponse)
        self.assertTrue(len(resp.content) > 100)
        self.assertGreater(resp.completion_tokens, 50)


if __name__ == "__main__":
    unittest.main(verbosity=2)
