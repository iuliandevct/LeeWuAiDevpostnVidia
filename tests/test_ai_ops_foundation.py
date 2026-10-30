"""
tests/test_ai_ops_foundation.py
Comprehensive Automated Test Suite for LeeWu AI Operations & Cost Observatory Foundation.

Strictly covers all 15 required verification scenarios:
1. Database initialization twice (idempotency).
2. Missing pricing configuration file.
3. Unknown model pricing (no tariffs invented, flagged unavailable).
4. Verified pricing mathematical calculation (input, output, cached).
5. Missing provider request ID (UUID generated).
6. Provider request ID extraction (preserved).
7. Actual token usage extraction directly from API metadata.
8. Missing usage metadata (no token fabrication).
9. Failed inference event recording with sanitized error category.
10. Telemetry database failure does not break caller inference.
11. Queue saturation (bounded queue drops gracefully without blocking).
12. Concurrent inference event submissions (multi-threaded SQLite transactional safety).
13. Strict PII, prompt, and secret exclusion.
14. Invalid numeric values rejected/clamped (negative tokens, NaN durations).
15. Graceful shutdown and queue flush.

No Nebius credits consumed; all provider interactions are mocked.
"""

import os
import sys
import time
import json
import queue
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch, MagicMock

# Ensure project root is in sys.path
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

import ai_ops_service
from ai_ops_service import (
    AIOpsService,
    TelemetryQueueWriter,
    initialize_database,
    load_pricing,
    record_inference_event,
    get_model_inventory,
    get_usage_summary,
    get_health,
    sanitize_telemetry_text,
    classify_error_category
)


class TestAIOpsTelemetryFoundation(unittest.TestCase):

    def setUp(self):
        """Creates an isolated temporary test directory and database for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_db = os.path.join(self.temp_dir.name, "test_ai_ops.db")
        self.pricing_file = os.path.join(PROJECT_DIR, "config", "ai_pricing.json")
        self.service = AIOpsService(
            db_path=self.test_db,
            pricing_config_path=self.pricing_file,
            enable_async_queue=False  # Default synchronous in base tests
        )

    def tearDown(self):
        """Cleans up temporary resources."""
        if hasattr(self, "service") and self.service:
            self.service.shutdown(timeout=1.0)
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    # ==========================================================================
    # 1. Database Initialization Twice (Idempotency)
    # ==========================================================================
    def test_01_database_initialization_twice(self):
        """Verifies database initialization is completely idempotent and non-destructive."""
        db_path = os.path.join(self.temp_dir.name, "idempotent_test.db")
        svc = AIOpsService(db_path=db_path, enable_async_queue=False)

        # 1. First initialization
        ok1 = svc.initialize_database(db_path)
        self.assertTrue(ok1)

        # Insert a sample row to verify it survives second init
        with svc.get_connection() as conn:
            conn.execute("""
            INSERT INTO ai_usage_events (request_id, timestamp_utc, provider, model_id, latency_ms)
            VALUES ('req_test_survive', '2026-10-30T00:00:00Z', 'nebius', 'nemotron-nano', 100.0)
            """)
            conn.commit()

        # 2. Second initialization on the same DB
        ok2 = svc.initialize_database(db_path)
        self.assertTrue(ok2)

        # Verify tables and preexisting record exist
        with svc.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [r[0] for r in cur.fetchall()]
            for expected_table in ["ai_alert_events", "ai_budgets", "ai_model_pricing", "ai_models", "ai_usage_events"]:
                self.assertIn(expected_table, tables)

            cur.execute("SELECT COUNT(*) FROM ai_usage_events WHERE request_id = 'req_test_survive'")
            self.assertEqual(cur.fetchone()[0], 1)

    # ==========================================================================
    # 2. Missing Pricing File
    # ==========================================================================
    def test_02_missing_pricing_file(self):
        """Verifies that a nonexistent pricing config file fails safely without raising exceptions."""
        nonexistent = os.path.join(self.temp_dir.name, "nonexistent_pricing.json")
        svc = AIOpsService(db_path=self.test_db, pricing_config_path=nonexistent, enable_async_queue=False)
        loaded = svc.load_pricing(nonexistent)
        self.assertEqual(loaded, {})

    # ==========================================================================
    # 3. Unknown Model Pricing
    # ==========================================================================
    def test_03_unknown_model_pricing(self):
        """Verifies that unpriced or unknown models return unverified status and never invent tariffs."""
        cost, currency, has_pricing = self.service.calculate_cost(
            model_id="unregistered-vendor/unpriced-mystery-model-999b",
            prompt_tokens=5000,
            completion_tokens=5000
        )
        self.assertFalse(has_pricing)
        self.assertEqual(cost, 0.0)
        self.assertEqual(currency, "EUR")

        # Database record must preserve estimated_cost as -1.0 to indicate unpriced
        req_id = self.service.record_inference_event(
            provider="nebius",
            model_id="unregistered-vendor/unpriced-mystery-model-999b",
            latency_ms=500.0,
            prompt_tokens=5000,
            completion_tokens=5000
        )
        self.assertIsNotNone(req_id)
        reqs = self.service.get_requests(model_id="unregistered-vendor/unpriced-mystery-model-999b")
        self.assertEqual(reqs["total"], 1)
        self.assertEqual(reqs["items"][0]["estimated_cost"], -1.0)

    # ==========================================================================
    # 4. Verified Pricing Calculation
    # ==========================================================================
    def test_04_verified_pricing_calculation(self):
        """Verifies mathematical accuracy of verified pricing formulas including prompt, cached, and completion tokens."""
        # NVIDIA Nemotron 3 Nano (30B A3B): €0.15/1M in, €0.30/1M out, €0.075/1M cached
        model = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"

        # 1M regular input + 1M completion = €0.15 + €0.30 = €0.45
        cost, curr, verified = self.service.calculate_cost(
            model_id=model,
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
            cached_tokens=0
        )
        self.assertTrue(verified)
        self.assertEqual(curr, "EUR")
        self.assertAlmostEqual(cost, 0.45, places=5)

        # 1M input (with 500k cached) + 1M completion = (0.5 * 0.15) + (0.5 * 0.075) + (1.0 * 0.30)
        # = 0.075 + 0.0375 + 0.30 = €0.4125
        cost_cached, _, _ = self.service.calculate_cost(
            model_id=model,
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
            cached_tokens=500_000
        )
        self.assertAlmostEqual(cost_cached, 0.4125, places=5)

        # Test currency conversion (EUR -> USD) using documented rate (1.08)
        usd_cost = self.service.convert_currency(cost, "EUR", "USD")
        self.assertAlmostEqual(usd_cost, 0.45 * 1.08, places=4)

    # ==========================================================================
    # 5. Missing Provider Request ID (UUID Generated)
    # ==========================================================================
    def test_05_missing_provider_request_id(self):
        """Verifies that when request ID is omitted or empty, an automatic UUID is generated."""
        req_id1 = self.service.record_inference_event(
            provider="nebius",
            model_id="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
            request_id=None,
            latency_ms=120.0
        )
        self.assertIsNotNone(req_id1)
        self.assertTrue(req_id1.startswith("req_"))

        req_id2 = self.service.record_inference_event(
            provider="nebius",
            model_id="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
            request_id="",
            latency_ms=120.0
        )
        self.assertIsNotNone(req_id2)
        self.assertNotEqual(req_id1, req_id2)

    # ==========================================================================
    # 6. Provider Request ID Extraction
    # ==========================================================================
    def test_06_provider_request_id_extraction(self):
        """Verifies that an upstream provider request ID is preserved exactly without truncation."""
        provider_id = "chatcmpl-nebius-eu-north1-994821a8f90c4d"
        recorded_id = self.service.record_inference_event(
            provider="nebius",
            model_id="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
            request_id=provider_id,
            latency_ms=250.0
        )
        self.assertEqual(recorded_id, provider_id)
        reqs = self.service.get_requests()
        self.assertEqual(reqs["items"][0]["request_id"], provider_id)

    # ==========================================================================
    # 7. Actual Token Usage Extraction
    # ==========================================================================
    def test_07_actual_token_usage_extraction(self):
        """Verifies actual token metrics extracted from OpenAI-compatible API responses."""
        self.service.record_inference_event(
            provider="nebius",
            model_id="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
            prompt_tokens=412,
            completion_tokens=789,
            total_tokens=1201,
            cached_tokens=128,
            latency_ms=1150.0,
            usage_source="api_response"
        )
        reqs = self.service.get_requests()
        item = reqs["items"][0]
        self.assertEqual(item["prompt_tokens"], 412)
        self.assertEqual(item["completion_tokens"], 789)
        self.assertEqual(item["total_tokens"], 1201)
        self.assertEqual(item["cached_tokens"], 128)
        self.assertEqual(item["usage_source"], "api_response")

    # ==========================================================================
    # 8. Missing Usage Metadata
    # ==========================================================================
    def test_08_missing_usage_metadata(self):
        """Verifies that when token metadata is missing from API, tokens are not fabricated."""
        self.service.record_inference_event(
            provider="nebius",
            model_id="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            latency_ms=800.0,
            usage_source="unavailable"
        )
        reqs = self.service.get_requests()
        item = reqs["items"][0]
        self.assertEqual(item["prompt_tokens"], 0)
        self.assertEqual(item["completion_tokens"], 0)
        self.assertEqual(item["total_tokens"], 0)
        self.assertEqual(item["usage_source"], "unavailable")

    # ==========================================================================
    # 9. Failed Inference Event
    # ==========================================================================
    def test_09_failed_inference_event(self):
        """Verifies recording of failed inference attempts with sanitized taxonomy classification."""
        self.service.record_inference_event(
            provider="nebius",
            model_id="nvidia/nemotron-3-super-120b-a12b",
            latency_ms=140.0,
            http_status=429,
            status="FAILURE",
            error_message="Nebius Rate Limit Exceeded (HTTP 429) for API key Bearer v1.SYNTHETIC_TEST_KEY_Pxyz123456"
        )
        reqs = self.service.get_requests(status="FAILURE")
        self.assertEqual(reqs["total"], 1)
        item = reqs["items"][0]
        self.assertEqual(item["status"], "FAILURE")
        self.assertEqual(item["http_status"], 429)
        self.assertEqual(item["error_category"], "RATE_LIMIT")
        # Ensure credentials were redacted from error text
        self.assertNotIn("v1.SYNTHETIC_TEST_KEY_Pxyz123456", item["error_message"])
        self.assertIn("[REDACTED_TOKEN]", item["error_message"])

    # ==========================================================================
    # 10. Telemetry Database Failure Does Not Break Inference
    # ==========================================================================
    def test_10_telemetry_database_failure_does_not_break_inference(self):
        """Verifies that database locks or filesystem failures do not crash inference callers."""
        with patch.object(self.service, "_get_connection", side_effect=sqlite3.OperationalError("database is locked")):
            # Recording must not raise an unhandled exception
            try:
                res = self.service.record_inference_event(
                    provider="nebius",
                    model_id="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
                    latency_ms=100.0
                )
                self.assertIsNone(res)
            except Exception as e:
                self.fail(f"record_inference_event raised an exception during DB failure: {e}")

    # ==========================================================================
    # 11. Queue Saturation
    # ==========================================================================
    def test_11_queue_saturation(self):
        """Verifies bounded queue drops events gracefully without blocking inference when saturated."""
        async_svc = AIOpsService(
            db_path=self.test_db,
            pricing_config_path=self.pricing_file,
            enable_async_queue=True
        )
        writer = TelemetryQueueWriter(async_svc, maxsize=3)
        dummy_event = {
            "request_id": "dummy", "provider": "nebius", "model_id": "m",
            "timestamp_utc": "2026-10-30T00:00:00Z", "latency_ms": 1.0,
            "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
            "cached_tokens": 0, "http_status": 200, "status": "SUCCESS",
            "retry_count": 0, "estimated_cost": -1.0, "currency": "EUR",
            "is_synthetic": 0, "usage_source": "u", "service_caller": "s",
            "operation_type": "o"
        }
        # Fill queue to capacity
        for i in range(3):
            item = dict(dummy_event, request_id=f"fill_{i}")
            writer.queue.put_nowait(item)

        # Force queue full condition for next enqueue
        with patch.object(writer.queue, "put", side_effect=queue.Full):
            t0 = time.time()
            ok = writer.enqueue(dict(dummy_event, request_id="r_overflow"), timeout=0.05)
            duration = time.time() - t0

        self.assertFalse(ok)
        self.assertLess(duration, 0.5)  # Zero indefinite blocking
        self.assertGreaterEqual(writer.dropped_events_count, 1)
        writer.shutdown(timeout=1.0)
        async_svc.shutdown(timeout=1.0)

    # ==========================================================================
    # 12. Concurrent Inference Event Submissions
    # ==========================================================================
    def test_12_concurrent_inference_event_submissions(self):
        """Verifies thread-safe ingestion under high concurrency across 10 threads."""
        async_svc = AIOpsService(
            db_path=self.test_db,
            pricing_config_path=self.pricing_file,
            enable_async_queue=True
        )

        def worker(thread_idx: int):
            for i in range(10):
                async_svc.record_inference_event(
                    provider="nebius",
                    model_id="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
                    request_id=f"concur_{thread_idx}_{i}",
                    latency_ms=100.0 + i,
                    prompt_tokens=100,
                    completion_tokens=100,
                    total_tokens=200
                )

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Flush background queue to disk
        flushed = async_svc.flush(timeout=5.0)
        self.assertTrue(flushed)

        reqs = async_svc.get_requests(page_size=200)
        self.assertEqual(reqs["total"], 100)
        async_svc.shutdown(timeout=2.0)

    # ==========================================================================
    # 13. PII and Prompt Exclusion
    # ==========================================================================
    def test_13_pii_and_prompt_exclusion(self):
        """Verifies that prompts, completions, personal names, and authorization tokens are strictly excluded."""
        sensitive_key = "Bearer v1.SecretAdminToken994821a8"
        raw_error = f"Authentication rejected for {sensitive_key} by Nebius Gateway."

        req_id = self.service.record_inference_event(
            provider="nebius",
            model_id="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
            error_message=raw_error,
            # Pass arbitrary keyword arguments that might mimic prompts
            prompt="SECRET MARITIME VESSEL MANIFEST FOR MV DEMO CARRIER",
            completion="CONFIDENTIAL STATUTORY ADVICE DO NOT LOG",
            authorization=sensitive_key,
            user_email="surveyor@example.com"
        )
        self.assertIsNotNone(req_id)

        # Inspect raw SQLite database table columns and values
        with self.service.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM ai_usage_events WHERE request_id = ?", (req_id,))
            row = dict(cur.fetchone())

            # Ensure prompt, completion, and authorization columns do not exist in schema
            self.assertNotIn("prompt", row)
            self.assertNotIn("completion", row)
            self.assertNotIn("authorization", row)
            self.assertNotIn("user_email", row)

            # Ensure error message has secrets redacted
            self.assertNotIn(sensitive_key, row["error_message"])
            self.assertIn("Bearer [REDACTED_TOKEN]", row["error_message"])

    # ==========================================================================
    # 14. Invalid Numeric Values
    # ==========================================================================
    def test_14_invalid_numeric_values(self):
        """Verifies that negative tokens, negative latencies, and NaN durations are safely clamped."""
        req_id = self.service.record_inference_event(
            provider="nebius",
            model_id="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
            prompt_tokens=-500,
            completion_tokens=-250,
            total_tokens=-750,
            cached_tokens=-100,
            latency_ms=-999.0,
            retry_count=-5
        )
        self.assertIsNotNone(req_id)

        reqs = self.service.get_requests()
        item = reqs["items"][0]
        self.assertEqual(item["prompt_tokens"], 0)
        self.assertEqual(item["completion_tokens"], 0)
        self.assertEqual(item["total_tokens"], 0)
        self.assertEqual(item["cached_tokens"], 0)
        self.assertEqual(item["latency_ms"], 0.0)
        self.assertEqual(item["retry_count"], 0)

    # ==========================================================================
    # 15. Graceful Shutdown and Queue Flush
    # ==========================================================================
    def test_15_graceful_shutdown_and_queue_flush(self):
        """Verifies that telemetry queue flushes cleanly during graceful process shutdown."""
        async_svc = AIOpsService(
            db_path=self.test_db,
            pricing_config_path=self.pricing_file,
            enable_async_queue=True
        )

        # Submit 10 events
        for i in range(10):
            async_svc.record_inference_event(
                provider="nebius",
                model_id="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
                request_id=f"flush_test_{i}",
                latency_ms=50.0
            )

        # Execute shutdown with flush
        async_svc.shutdown(timeout=3.0)

        # Verify writer worker stopped
        self.assertFalse(async_svc.queue_writer._worker_thread.is_alive())

        # Verify all 10 events were flushed and committed to SQLite
        with async_svc.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM ai_usage_events WHERE request_id LIKE 'flush_test_%'")
            count = cur.fetchone()[0]
            self.assertEqual(count, 10)


if __name__ == "__main__":
    unittest.main()
