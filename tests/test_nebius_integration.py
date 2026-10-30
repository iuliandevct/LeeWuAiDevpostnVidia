"""
tests/test_nebius_integration.py
End-to-End Integration Test Suite for Nebius Token Factory Adapter.

Validates:
1. Safe configuration check with secret redaction.
2. Dynamic NVIDIA Nemotron model discovery.
3. Live inference against Nebius Token Factory with latency & token accounting.
4. Strict error propagation (no silent fallback on invalid models or keys).
5. Statutory marine cargo survey assessment generation.
"""

import os
import sys
import unittest
import time

# Ensure project root is in sys.path
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


class TestNebiusTokenFactoryIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Instantiate adapter (reads from local .env / .env.nebius)
        cls.adapter = NebiusTokenFactoryAdapter()
        cls.raw_key = cls.adapter.api_key

    def test_01_configuration_audit_safe(self):
        """Verifies configuration audit succeeds without exposing raw secrets."""
        cfg = self.adapter.validate_configuration()
        self.assertEqual(cfg["status"], "VALID", f"Configuration audit failed: {cfg.get('errors')}")
        self.assertTrue(cfg["key_present"], "API key was not detected.")
        self.assertIn("REDACTED", cfg["key_masked"], "API key was not properly masked.")
        
        # Ensure the raw full key NEVER appears anywhere in the config dict
        cfg_str = str(cfg)
        if self.raw_key and len(self.raw_key) > 10:
            self.assertNotIn(self.raw_key, cfg_str, "CRITICAL: Full raw API key leaked in configuration audit!")

    def test_02_model_discovery(self):
        """Verifies live query to Nebius Token Factory /models endpoint."""
        models = self.adapter.list_models()
        self.assertIsInstance(models, list)
        self.assertGreater(len(models), 0, "No models returned from Nebius Token Factory.")

        nemotron_models = self.adapter.get_available_nemotron_models()
        self.assertIsInstance(nemotron_models, list)
        self.assertGreater(len(nemotron_models), 0, "No NVIDIA Nemotron models found in Nebius catalog.")
        
        # Default model must be present in available Nemotron models
        self.assertIn(
            self.adapter.default_model,
            models,
            f"Configured default model '{self.adapter.default_model}' not found in active catalog."
        )

    def test_03_real_chat_completion(self):
        """Executes a real API chat completion and validates the response object."""
        test_prompt = [
            {"role": "system", "content": "You are LeeWu AI. Answer directly in one short sentence."},
            {"role": "user", "content": "Confirm operational readiness for maritime survey operations."}
        ]

        t0 = time.time()
        resp = self.adapter.complete(test_prompt, max_tokens=250, temperature=0.1)
        latency = time.time() - t0

        self.assertIsInstance(resp, NebiusResponse)
        self.assertTrue(len(resp.content) > 0, "Model returned an empty content string.")
        self.assertIn(resp.finish_reason, ["stop", "length"], f"Unexpected finish reason: {resp.finish_reason}")
        self.assertGreater(resp.total_tokens, 0, "Total tokens consumed must be greater than zero.")
        self.assertLess(latency, 45.0, f"Inference took too long: {latency:.2f}s")

    def test_04_strict_error_handling_invalid_model(self):
        """Verifies that non-existent models raise NebiusAPIError and NEVER fall back silently."""
        invalid_model = "nvidia/non-existent-nemotron-model-999b-xyz"
        messages = [{"role": "user", "content": "Ping test."}]

        with self.assertRaises(NebiusAPIError) as ctx:
            self.adapter.complete(messages, model=invalid_model, max_tokens=50)

        err_msg = str(ctx.exception)
        self.assertTrue(len(err_msg) > 0)
        # Ensure raw key not in error message
        if self.raw_key and len(self.raw_key) > 10:
            self.assertNotIn(self.raw_key, err_msg, "CRITICAL: API key leaked in exception string!")

    def test_05_strict_error_handling_invalid_key(self):
        """Verifies that invalid credentials trigger authentication errors without leaking keys."""
        bogus_adapter = NebiusTokenFactoryAdapter(api_key="v1.BOGUS_INVALID_KEY_999999999999999999999")
        messages = [{"role": "user", "content": "Auth test."}]

        with self.assertRaises(NebiusException) as ctx:
            bogus_adapter.complete(messages, max_tokens=50)

        err_msg = str(ctx.exception)
        self.assertNotIn("v1.BOGUS_INVALID_KEY_999999999999999999999", err_msg, "Bogus key was not masked in exception!")

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
        self.assertTrue(len(resp.content) > 100, "Survey note too short to be a valid statutory assessment.")
        self.assertGreater(resp.completion_tokens, 50)


if __name__ == "__main__":
    unittest.main(verbosity=2)
