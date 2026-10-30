"""
tests/test_ai_ops.py
Comprehensive automated test suite for LeeWu AI Operations & Cost Observatory.

Covers:
1. Successful AI request telemetry recording
2. Failed AI request telemetry recording
3. Real token usage extraction (prompt, completion, total, cached)
4. Cost calculation mathematical accuracy (input/output/cached formula)
5. Missing model pricing handling ("Pricing unavailable" / -1.0 flag)
6. Duplicate request ID idempotence & conflict safety
7. Budget threshold alerts generation (50%, 75%, 90%, 100%)
8. Administrator authorization validation (Bearer token, loopback dev mode)
9. Non-blocking resilience: Telemetry storage failure never breaks AI inference
"""

import os
import sys
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone

# Add project root to sys.path
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from scripts.ai_ops_service import AIOpsService
from scripts.nebius_provider import NebiusResponse, NebiusException


class TestAIOpsObservability(unittest.TestCase):

    def setUp(self):
        """Creates an isolated temporary SQLite database for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_db = os.path.join(self.temp_dir.name, "test_leewu_ai_ops.db")
        self.service = AIOpsService(db_path=self.test_db)

    def tearDown(self):
        """Cleans up temporary resources."""
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_01_successful_telemetry(self):
        """Tests recording of a successful AI inference event."""
        req_id = self.service.record_inference_event(
            provider="nebius",
            model_id="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
            latency_ms=2150.5,
            http_status=200,
            status="SUCCESS",
            prompt_tokens=320,
            completion_tokens=580,
            total_tokens=900,
            cached_tokens=0,
            survey_id="LW-DEMO-001",
            operation_type="statutory-assessment",
            is_synthetic=False
        )
        self.assertIsNotNone(req_id)

        # Verify persisted row
        requests = self.service.get_requests(page=1, page_size=10, include_synthetic=False)
        self.assertEqual(requests["total"], 1)
        item = requests["items"][0]
        self.assertEqual(item["request_id"], req_id)
        self.assertEqual(item["status"], "SUCCESS")
        self.assertEqual(item["prompt_tokens"], 320)
        self.assertEqual(item["completion_tokens"], 580)
        self.assertEqual(item["total_tokens"], 900)
        self.assertAlmostEqual(item["latency_ms"], 2150.5, places=1)
        self.assertGreater(item["estimated_cost"], 0.0)

    def test_02_failed_telemetry(self):
        """Tests recording of a failed inference event with error logging."""
        req_id = self.service.record_inference_event(
            provider="nebius",
            model_id="nvidia/Nemotron-3.5-Super-VL",
            latency_ms=450.0,
            http_status=429,
            status="FAILURE",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            survey_id="LW-DEMO-001",
            error_message="Nebius Rate Limit Exceeded (HTTP 429)"
        )
        self.assertIsNotNone(req_id)

        requests = self.service.get_requests(status="FAILURE")
        self.assertEqual(requests["total"], 1)
        item = requests["items"][0]
        self.assertEqual(item["status"], "FAILURE")
        self.assertEqual(item["http_status"], 429)

        # An alert should have been raised for the failure
        alerts = self.service.get_alerts()
        self.assertTrue(any("failure" in a["alert_type"] for a in alerts))

    def test_03_token_usage_extraction(self):
        """Tests real token usage extraction from NebiusResponse object."""
        sample_raw = {
            "id": "chatcmpl-test-uuid-99",
            "model": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
            "choices": [{"message": {"content": "Test analysis"}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": 412,
                "completion_tokens": 588,
                "total_tokens": 1000,
                "prompt_tokens_details": {"cached_tokens": 128}
            }
        }
        resp = NebiusResponse(
            content="Test analysis",
            model="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
            finish_reason="stop",
            usage=sample_raw["usage"],
            latency_seconds=1.85,
            raw_response=sample_raw
        )

        self.assertEqual(resp.prompt_tokens, 412)
        self.assertEqual(resp.completion_tokens, 588)
        self.assertEqual(resp.total_tokens, 1000)

        # Ingest directly
        req_id = self.service.record_inference_event(
            provider="nebius",
            model_id=resp.model,
            latency_ms=resp.latency_seconds * 1000,
            prompt_tokens=resp.prompt_tokens,
            completion_tokens=resp.completion_tokens,
            total_tokens=resp.total_tokens,
            cached_tokens=128,
            request_id=sample_raw["id"]
        )
        self.assertEqual(req_id, "chatcmpl-test-uuid-99")

    def test_04_cost_calculation_accuracy(self):
        """Tests mathematical accuracy of cost formulas based on verified rates."""
        # Rate for Nemotron-3-Nano: Input 0.15 / 1M, Output 0.30 / 1M, Cached 0.075 / 1M
        # Prompt: 1,000,000 tokens -> 0.15 EUR
        # Output: 1,000,000 tokens -> 0.30 EUR
        cost, curr, has_p = self.service.calculate_cost(
            model_id="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
            cached_tokens=0
        )
        self.assertTrue(has_p)
        self.assertEqual(curr, "EUR")
        self.assertAlmostEqual(cost, 0.45, places=5)

        # Test small cargo survey call: 500 prompt, 500 completion
        # Input: 500 * 0.15 / 1M = 0.000075
        # Output: 500 * 0.30 / 1M = 0.000150
        # Total: 0.000225 EUR
        cost_survey, _, _ = self.service.calculate_cost(
            model_id="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
            prompt_tokens=500,
            completion_tokens=500
        )
        self.assertAlmostEqual(cost_survey, 0.000225, places=6)

    def test_05_missing_pricing_handling(self):
        """Tests that uncatalogued models explicitly report missing pricing rather than $0."""
        cost, curr, has_pricing = self.service.calculate_cost(
            model_id="unknown-experimental-model-99",
            prompt_tokens=1000,
            completion_tokens=1000
        )
        self.assertFalse(has_pricing)
        self.assertEqual(cost, 0.0)

        # Ingestion records -1.0 estimated cost to signal missing pricing
        self.service.record_inference_event(
            provider="unknown",
            model_id="unknown-experimental-model-99",
            latency_ms=800,
            prompt_tokens=1000,
            completion_tokens=1000
        )
        reqs = self.service.get_requests(model_id="unknown-experimental-model-99")
        self.assertEqual(reqs["items"][0]["estimated_cost"], -1.0)

        # Unknown pricing alert raised
        alerts = self.service.get_alerts()
        self.assertTrue(any(a["alert_type"] == "unknown_pricing" for a in alerts))

    def test_06_duplicate_request_id_safety(self):
        """Verifies duplicate request IDs are handled idempotently without throwing SQL errors."""
        fixed_id = "req_duplicate_test_001"
        res1 = self.service.record_inference_event(
            provider="nebius",
            model_id="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
            latency_ms=1200,
            request_id=fixed_id,
            prompt_tokens=100,
            completion_tokens=200
        )
        self.assertEqual(res1, fixed_id)

        # Duplicate attempt with same ID
        res2 = self.service.record_inference_event(
            provider="nebius",
            model_id="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
            latency_ms=1300,
            request_id=fixed_id,
            prompt_tokens=100,
            completion_tokens=200
        )
        self.assertEqual(res2, fixed_id)

        # Only 1 row in table
        reqs = self.service.get_requests()
        self.assertEqual(reqs["total"], 1)

    def test_07_budget_threshold_alerts(self):
        """Tests threshold alerts when spending nears or breaches daily budget."""
        # Set daily budget to €0.10 for testing
        self.service.budget_settings["daily_budget_eur"] = 0.10
        with self.service._get_connection() as conn:
            conn.execute("UPDATE ai_budget_limits SET budget_amount = 0.10 WHERE period = 'daily'")
            conn.commit()

        # Ingest event with substantial token usage (Hermes 405B at €5.00/1M)
        # 30,000 tokens ~ €0.12 (120% of €0.10 budget)
        self.service.record_inference_event(
            provider="nebius",
            model_id="NousResearch/Hermes-4-405B",
            latency_ms=3500,
            prompt_tokens=15000,
            completion_tokens=15000,
            is_synthetic=False
        )

        overview = self.service.get_overview(include_synthetic=False)
        self.assertGreater(overview["budget"]["daily_pct_consumed"], 50.0)

        alerts = self.service.get_alerts()
        self.assertTrue(any(a["alert_type"] == "budget_warning" for a in alerts))

    def test_08_admin_authorization(self):
        """Tests admin token validation helper."""
        os.environ['LEEWU_DB_PATH'] = self.test_db
        from leewu_mvp_server import check_admin_auth
        import urllib.parse

        class MockHandler:
            def __init__(self, headers, client_ip):
                self.headers = headers
                self.client_address = (client_ip, 50000)

        # Case 1: Localhost without ADMIN_API_KEY env set -> Must fail closed (P0 loopback bypass removed)
        os.environ.pop("ADMIN_API_KEY", None)
        h_local = MockHandler({}, "127.0.0.1")
        url_local = urllib.parse.urlparse("/api/ai-ops/overview")
        self.assertFalse(check_admin_auth(h_local, url_local))

        # Case 2: External or loopback client without token when ADMIN_API_KEY configured -> Rejected
        os.environ["ADMIN_API_KEY"] = "super-secret-admin-token-2026"
        self.assertFalse(check_admin_auth(h_local, url_local))
        h_ext = MockHandler({}, "198.51.100.25")
        self.assertFalse(check_admin_auth(h_ext, url_local))

        # Case 3: External client with valid Bearer token
        h_auth = MockHandler({"Authorization": "Bearer super-secret-admin-token-2026"}, "198.51.100.25")
        self.assertTrue(check_admin_auth(h_auth, url_local))

        # Case 4: Query parameter ?admin_key=...
        url_query = urllib.parse.urlparse("/api/ai-ops/overview?admin_key=super-secret-admin-token-2026")
        self.assertFalse(check_admin_auth(h_ext, url_query))  # Query-string tokens rejected per P0-SEC-07

        del os.environ["ADMIN_API_KEY"]

    def test_09_telemetry_failure_does_not_break_inference(self):
        """Verifies that database lock/failure during telemetry recording does not raise exceptions."""
        from unittest.mock import patch
        with patch.object(self.service, "_get_connection", side_effect=sqlite3.OperationalError("database is locked")):
            # Record should return None safely without raising an exception back to caller
            res = self.service.record_inference_event(
                provider="nebius",
                model_id="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
                latency_ms=1500
            )
            self.assertIsNone(res)

    def test_10_synthetic_demo_seeding_and_clearing(self):
        """Tests seeding isolated synthetic demo data and clearing it without touching real events."""
        # 1. Ingest 1 real event
        self.service.record_inference_event(
            provider="nebius",
            model_id="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
            latency_ms=2000,
            is_synthetic=False
        )

        # 2. Seed 15 synthetic events
        seeded = self.service.seed_synthetic_demo_data(count=15)
        self.assertEqual(seeded, 15)

        total_reqs = self.service.get_requests(include_synthetic=True)
        self.assertEqual(total_reqs["total"], 16)

        real_only = self.service.get_requests(include_synthetic=False)
        self.assertEqual(real_only["total"], 1)

        # 3. Clear synthetic events
        cleared = self.service.clear_synthetic_demo_data()
        self.assertEqual(cleared, 15)

        remaining = self.service.get_requests(include_synthetic=True)
        self.assertEqual(remaining["total"], 1)


if __name__ == "__main__":
    unittest.main()
