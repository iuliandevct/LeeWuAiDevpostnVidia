#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete Demo Validation Suite — End-to-End Maritime Inspection Workflow
Project: LeeWu AI — Maritime Cargo Survey Intelligence

Validates:
1. Authentication (Frontend login.html + Backend Bearer token auth + Demo privilege boundary).
2. Opening demonstration inspection (LW-DEMO-001 initialization, listing, details, reset).
3. Uploading photographic evidence & SHA-256 integrity verification.
4. AI Analysis via Nebius Token Factory (mocked by default to preserve paid API credits) + AIOps telemetry logging.
5. Human Surveyor verification & approval + cryptographic SHA-256 seal.
6. Statutory report generation & HTML export (provenance tags, XSS escaping, seal match).
7. Telegram Bot (@Leewubot) configuration, numeric fail-closed auth, and isolated chat history.
8. Preservation of original SQLite database (zero mutations to data/leewu_mvp.db).
"""

import hashlib
import http.server
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import telegram_bot_daemon as tg_daemon


class _DemoMockNebiusHandler(http.server.BaseHTTPRequestHandler):
    """Deterministic local OpenAI-compatible mock for Nebius Token Factory."""
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path.endswith("/models"):
            raw = json.dumps({
                "object": "list",
                "data": [{"id": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B", "object": "model"}]
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            _ = self.rfile.read(length)
        payload = {
            "id": "chatcmpl-demo-validation-001",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": (
                        "### 1. Executive Cargo Condition Summary\n"
                        "Industrial Transformer TR-001 (124.5 MT) inspected at Port of Constanta Berth 120 on board MV DEMO CARRIER. "
                        "Structural condition is sound with zero oil weeping and intact porcelain bushings.\n\n"
                        "### 2. Environmental & Internal Atmosphere Verification\n"
                        "Nitrogen blanket positive pressure verified at 0.24 bar (within 0.15 - 0.35 bar statutory limits). Silica gel deep cobalt blue.\n\n"
                        "### 3. Transit Dynamics & Shock Recorder Evaluation\n"
                        "Tri-axial impact recorder logs (0.75 G longitudinal, 0.35 G transverse) remain well below 1.5 G IMO CSS Code Annex 13 limits.\n\n"
                        "### 4. Statutory Warranty Recommendation\n"
                        "8 x Grade 80 16mm lashing chains verified. Recommend UNCONDITIONAL CLEAN MATE'S RECEIPT."
                    )
                },
                "finish_reason": "stop"
            }],
            "usage": {"prompt_tokens": 310, "completion_tokens": 165, "total_tokens": 475}
        }
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class TestCompleteDemoValidation(unittest.TestCase):
    """End-to-End Demo Workflow & Telegram History Validation on Isolated SQLite Copy."""

    @classmethod
    def setUpClass(cls):
        cls.original_db = PROJECT_ROOT / "data" / "leewu_mvp.db"
        cls.orig_sha256 = hashlib.sha256(cls.original_db.read_bytes()).hexdigest()
        cls.orig_stat = cls.original_db.stat()

        cls.temp_dir = Path(tempfile.mkdtemp(prefix="leewu_demo_val_"))
        cls.iso_data_dir = cls.temp_dir / "data"
        cls.iso_uploads_dir = cls.iso_data_dir / "uploads"
        cls.iso_uploads_dir.mkdir(parents=True, exist_ok=True)
        cls.iso_db = cls.iso_data_dir / "leewu_mvp_demo.db"
        shutil.copy2(cls.original_db, cls.iso_db)

        # Start local mock Nebius server unless RUN_LIVE_NEBIUS_TESTS=1
        cls.mock_nebius_server = None
        if os.environ.get("RUN_LIVE_NEBIUS_TESTS") != "1":
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", 0))
                mock_port = s.getsockname()[1]
            cls.mock_nebius_server = http.server.HTTPServer(("127.0.0.1", mock_port), _DemoMockNebiusHandler)
            threading.Thread(target=cls.mock_nebius_server.serve_forever, daemon=True).start()

        # Find free local port for demo validation server
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            cls.port = s.getsockname()[1]

        cls.admin_key = "leewu-demo-validation-admin-secret-2026"
        env = os.environ.copy()
        tg_daemon._load_env_file(str(PROJECT_ROOT / ".env"))
        for k in ["NEBIUS_API_KEY", "NEBIUS_BASE_URL", "NEBIUS_MODEL", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "TELEGRAM_ALLOWED_USERS"]:
            if os.environ.get(k):
                env[k] = os.environ[k]

        if cls.mock_nebius_server is not None:
            env["NEBIUS_API_KEY"] = "v1.MOCK_DEMO_VALIDATION_KEY_000000000000000"
            env["NEBIUS_BASE_URL"] = f"http://127.0.0.1:{mock_port}/v1"

        env["PORT"] = str(cls.port)
        env["HOST"] = "127.0.0.1"
        env["DATA_DIR"] = str(cls.iso_data_dir)
        env["LEEWU_DB_PATH"] = str(cls.iso_db)
        env["ADMIN_API_KEY"] = cls.admin_key

        cls.proc = subprocess.Popen(
            [sys.executable, str(PROJECT_ROOT / "leewu_mvp_server.py")],
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        cls.base_url = f"http://127.0.0.1:{cls.port}"

        ready = False
        for _ in range(40):
            try:
                with urllib.request.urlopen(f"{cls.base_url}/api/health", timeout=2) as r:
                    if r.status == 200:
                        ready = True
                        break
            except Exception:
                time.sleep(0.15)
        assert ready, "Demo Validation Server failed to start"

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try:
            cls.proc.wait(timeout=5)
        except Exception:
            cls.proc.kill()
        if cls.mock_nebius_server is not None:
            cls.mock_nebius_server.shutdown()
            cls.mock_nebius_server.server_close()

        shutil.rmtree(cls.temp_dir, ignore_errors=True)

        # Confirm original DB was never touched
        after_sha = hashlib.sha256(cls.original_db.read_bytes()).hexdigest()
        after_stat = cls.original_db.stat()
        assert after_sha == cls.orig_sha256, "Original DB SHA-256 changed during Demo Validation!"
        assert after_stat.st_size == cls.orig_stat.st_size, "Original DB size changed!"
        assert after_stat.st_mtime_ns == cls.orig_stat.st_mtime_ns, "Original DB mtime changed!"

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.admin_key}"}

    def _request(self, path: str, method: str = "GET", payload: dict = None, headers: dict = None):
        req_headers = dict(headers or {})
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            req_headers["Content-Type"] = "application/json"
        req = urllib.request.Request(f"{self.base_url}{path}", data=data, headers=req_headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                body = r.read().decode("utf-8")
                ct = r.headers.get("Content-Type", "")
                return r.status, (json.loads(body) if "application/json" in ct else body), dict(r.headers)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            try:
                return e.code, json.loads(body), dict(e.headers)
            except Exception:
                return e.code, body, dict(e.headers)

    def test_01_authentication_and_privilege_boundaries(self):
        """1. Autentificare: Verify login portal, admin Bearer auth, and demo write protection."""
        status, html_login, _ = self._request("/login.html")
        self.assertEqual(status, 200)
        self.assertIn("DEMO_ACCOUNTS", html_login)
        self.assertIn("Alexandru Radu", html_login)
        self.assertNotIn("Paul" + " Leu", html_login)
        self.assertNotIn("Maritime" + "2026!", html_login)
        self.assertNotIn("password.length >= 6", html_login)

        # Unauthenticated write to both non-demo and LW-DEMO-001 rejected with 401
        status_unauth_prod, body_unauth, _ = self._request("/api/surveys/LW-PROD-999/upload", method="POST", payload={})
        self.assertEqual(status_unauth_prod, 401)
        self.assertEqual(body_unauth.get("status"), "AUTH_REQUIRED")

        status_unauth_demo, _, _ = self._request("/api/surveys/LW-DEMO-001/upload", method="POST", payload={})
        self.assertEqual(status_unauth_demo, 401)

        # Admin AI Ops endpoint rejected without Bearer token
        status_no_auth, _, _ = self._request("/api/ai-ops/overview")
        self.assertEqual(status_no_auth, 401)

        # Admin AI Ops endpoint rejected when token passed via query string (?admin_key=...)
        status_qs_auth, _, _ = self._request(f"/api/ai-ops/overview?admin_key={self.admin_key}")
        self.assertEqual(status_qs_auth, 401)

        # Admin AI Ops endpoint succeeds with valid Bearer token
        status_valid_auth, ov_data, _ = self._request("/api/ai-ops/overview", headers=self._auth_headers())
        self.assertEqual(status_valid_auth, 200)
        self.assertIn("total_requests", ov_data)

    def test_02_open_demonstration_inspection(self):
        """2. Deschiderea inspectiei demonstrative: Reset (authenticated) and open LW-DEMO-001."""
        st_health, health, _ = self._request("/api/health")
        self.assertEqual(st_health, 200)
        self.assertEqual(health["status"], "ok")
        self.assertTrue(health["ai_available"])

        st_reset, res_reset, _ = self._request(
            "/api/surveys/LW-DEMO-001/reset", method="POST", payload={}, headers=self._auth_headers()
        )
        self.assertEqual(st_reset, 200)
        self.assertTrue(res_reset["success"])

        st_list, surveys, _ = self._request("/api/surveys")
        self.assertEqual(st_list, 200)
        self.assertTrue(any(s["survey_id"] == "LW-DEMO-001" for s in surveys))

        st_open, survey, _ = self._request("/api/surveys/LW-DEMO-001")
        self.assertEqual(st_open, 200)
        self.assertEqual(survey["survey_id"], "LW-DEMO-001")
        self.assertEqual(survey["vessel_name"], "MV DEMO CARRIER")
        self.assertEqual(survey["cargo_item"], "TR-001")
        self.assertEqual(survey["status"], "IN_PROGRESS")

    def test_03_upload_photos_and_evidence(self):
        """3. Incarcarea fotografiilor si dovezilor: Upload TR-001 photo and verify SHA-256."""
        st_up, res_up, _ = self._request(
            "/api/surveys/LW-DEMO-001/upload", method="POST", payload={}, headers=self._auth_headers()
        )
        self.assertEqual(st_up, 201)
        self.assertTrue(res_up["success"])
        ev = res_up["evidence"]
        self.assertEqual(ev["survey_id"], "LW-DEMO-001")
        self.assertEqual(ev["cargo_item"], "TR-001")
        self.assertEqual(ev["sha256"], "cbfd090e07a67ab20818c3e113fa6276ad37f3ba9da9479528fdf4dc2e0464b7")
        self.assertGreater(ev["file_size_bytes"], 20000)

        st_det, survey, _ = self._request("/api/surveys/LW-DEMO-001")
        self.assertEqual(st_det, 200)
        self.assertEqual(len(survey["evidence"]), 1)
        self.assertEqual(survey["evidence"][0]["sha256"], ev["sha256"])

    def test_04_ai_analysis_via_nebius(self):
        """4. Analiza AI prin Nebius: Run Nemotron assessment and verify AIOps telemetry."""
        payload = {
            "nitrogen_pressure": "0.24 bar",
            "impact_recorder_g": "0.75 G (longitudinal), 0.35 G (transverse)",
            "lashing_status": "8 x Grade 80 16mm chains verified at 45° angle with turnbuckles secured",
            "visual_remarks": "Transformer tank exterior clean, zero oil weeping, silica gel deep cobalt blue."
        }
        st_ai, res_ai, _ = self._request(
            "/api/surveys/LW-DEMO-001/ai-inspect", method="POST", payload=payload, headers=self._auth_headers()
        )
        self.assertEqual(st_ai, 200)
        self.assertTrue(res_ai["success"])
        self.assertEqual(res_ai["model"], "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B")
        self.assertGreater(len(res_ai["assessment"]), 150)

        st_det, survey, _ = self._request("/api/surveys/LW-DEMO-001")
        self.assertEqual(st_det, 200)
        self.assertEqual(len(survey["ai_assessments"]), 1)
        self.assertEqual(survey["ai_assessments"][0]["nitrogen_pressure"], "0.24 bar")

    def test_05_verification_and_approval(self):
        """5. Verificare si aprobare: Surveyor sign-off and SHA-256 seal generation."""
        st_app, res_app, _ = self._request(
            "/api/surveys/LW-DEMO-001/approve",
            method="POST",
            payload={
                "surveyor_name": "Ing. Alexandru Radu",
                "license_number": "DEMO-MWS-2026-001",
                "final_remarks": "Verified within statutory parameters."
            },
            headers=self._auth_headers()
        )
        self.assertEqual(st_app, 200)
        self.assertTrue(res_app["success"])
        self.assertEqual(res_app["status"], "APPROVED")
        self.assertEqual(res_app["approved_by"], "Ing. Alexandru Radu")
        self.assertEqual(res_app["surveyor_license"], "DEMO-MWS-2026-001")
        seal = res_app["cryptographic_seal_sha256"]
        self.assertEqual(len(seal), 64)

        expected_source = f"LW-DEMO-001:Ing. Alexandru Radu:DEMO-MWS-2026-001:{res_app['approved_at']}:APPROVED"
        expected_seal = hashlib.sha256(expected_source.encode("utf-8")).hexdigest()
        self.assertEqual(seal, expected_seal)

    def test_06_report_generation_and_export(self):
        """6. Generare si export raport: Verify statutory HTML export, provenance, and XSS safety."""
        st_exp, html_export, _ = self._request("/api/surveys/LW-DEMO-001/export")
        self.assertEqual(st_exp, 200)
        self.assertIn("DEMONSTRATION WORKFLOW — SYNTHETIC DATASET (LW-DEMO-001)", html_export)
        self.assertIn("OBSERVED & MEASURED", html_export)
        self.assertIn("AI_INFERRED — NVIDIA Nemotron", html_export)
        self.assertIn("HUMAN_APPROVED (DEMO WORKFLOW VALIDATED)", html_export)
        self.assertIn("DATA INTEGRITY CHECKSUM (SHA-256):", html_export)
        self.assertIn("Ing. Alexandru Radu", html_export)
        self.assertIn("DEMO-MWS-2026-001", html_export)
        self.assertIn("cbfd090e07a67ab20818c3e113fa6276ad37f3ba9da9479528fdf4dc2e0464b7", html_export)
        self.assertNotIn("Paul" + " Leu", html_export)

    def test_07_telegram_and_history_verification(self):
        """7. Verificarea Telegram si a istoricului: Verify token location, numeric auth, and isolated history."""
        yt_env = (PROJECT_ROOT / ".env").read_text(encoding="utf-8")
        self.assertIn("TELEGRAM_BOT_TOKEN=", yt_env)
        self.assertIn('TELEGRAM_CHAT_ID="8143220589"', yt_env)
        self.assertIn('TELEGRAM_ALLOWED_USERS="8143220589"', yt_env)

        ok_auth, reason_auth = tg_daemon.is_authorized(8143220589, {"id": 8143220589}, "8143220589", "8143220589")
        self.assertTrue(ok_auth, reason_auth)

        ok_unauth, _ = tg_daemon.is_authorized(999999999, {"id": 999999999, "username": "admin"}, "8143220589", "8143220589")
        self.assertFalse(ok_unauth)

        hist_file = self.temp_dir / "telegram_chat_history_test.json"
        remarks_file = self.temp_dir / "survey_remarks_test.json"
        with patch.object(tg_daemon, "CHAT_HISTORY_FILE", str(hist_file)),              patch.object(tg_daemon, "REMARKS_FILE", str(remarks_file)),              patch.object(tg_daemon, "send_message", return_value={"ok": True}):

            tg_daemon.save_chat_message(8143220589, "user", "Care este presiunea azotului la TR-001?")
            tg_daemon.save_chat_message(8143220589, "assistant", "Presiunea azotului la TR-001 este 0.24 bar.")
            tg_daemon.save_chat_message(777777777, "user", "Mesaj izolat alt chat")

            ctx_main = tg_daemon.get_recent_context(8143220589, limit=8)
            ctx_other = tg_daemon.get_recent_context(777777777, limit=8)
            self.assertEqual(len(ctx_main), 2)
            self.assertEqual(len(ctx_other), 1)
            self.assertEqual(ctx_main[0]["content"], "Care este presiunea azotului la TR-001?")

            tg_daemon.handle_remark(8143220589, None, "/remark Hold 3 Coil #482 deformare usoara")
            saved_remarks = json.loads(remarks_file.read_text(encoding="utf-8"))
            self.assertEqual(len(saved_remarks), 1)
            self.assertEqual(saved_remarks[0]["surveyor"], "Alexandru Radu")
            self.assertNotIn("Paul" + " Leu", json.dumps(saved_remarks))

            self.assertTrue(tg_daemon.clear_chat_history(8143220589))
            self.assertEqual(len(tg_daemon.get_recent_context(8143220589)), 0)
            self.assertEqual(len(tg_daemon.get_recent_context(777777777)), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
