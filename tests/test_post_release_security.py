#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Post-Release Security Remediation Test Suite
Project: LeeWu AI — Maritime Cargo Survey Intelligence
Repository: LeeWuAiDevpostnVidia

Verifies all P0 and P1 security requirements using an isolated SQLite database
and a mocked Nebius Token Factory endpoint (zero paid API credits consumed):
1. Missing Bearer token -> 401 for every write endpoint (including LW-DEMO-001).
2. Invalid Bearer token -> 401 for every write and protected endpoint; constant-time comparison via secrets.compare_digest.
3. Valid Bearer token -> permitted operation (200/201).
4. Query-string credentials (?admin_key=, ?token=, ?api_key=, etc.) -> strictly rejected (401).
5. Missing ADMIN_API_KEY -> all protected endpoints fail closed (401).
6. Loopback requests (127.0.0.1, localhost, ::1) without credentials -> rejected (401) for protected operations.
7. Proxied cloudflared-to-local-backend requests (X-Forwarded-For, CF-Connecting-IP, etc.) cannot bypass authentication.
8. Public demo is strictly read-only: cannot trigger Nebius inference or mutate survey data.
9. Login (web/login.html & login.html) rejects arbitrary passwords and keeps client-side preview unauthenticated & read-only.
10. Original SQLite database (data/leewu_mvp.db) remains 100% unmodified.
"""

import hashlib
import http.server
import inspect
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
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class _MockNebiusHandler(http.server.BaseHTTPRequestHandler):
    """Local mock OpenAI-compatible Nebius server to ensure zero paid API credits are consumed."""
    call_log = []

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path.endswith("/models"):
            payload = {
                "object": "list",
                "data": [{"id": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B", "object": "model"}]
            }
            raw = json.dumps(payload).encode("utf-8")
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
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        _MockNebiusHandler.call_log.append({
            "path": self.path,
            "auth": self.headers.get("Authorization", ""),
            "body": body,
        })
        payload = {
            "id": f"chatcmpl-mock-sec-{len(_MockNebiusHandler.call_log)}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": (
                        "### 1. Executive Cargo Condition Summary\n"
                        "Mocked Nebius Nemotron assessment for TR-001 (124.5 MT). Structural integrity verified.\n\n"
                        "### 2. Environmental & Internal Atmosphere Verification\n"
                        "Nitrogen blanket pressure verified at 0.25 bar.\n\n"
                        "### 3. Transit Dynamics & Shock Recorder Evaluation\n"
                        "Tri-axial impact recorder within 1.5 G IMO CSS Code Annex 13 limits.\n\n"
                        "### 4. Statutory Warranty Recommendation\n"
                        "Issue UNCONDITIONAL CLEAN MATE'S RECEIPT."
                    )
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 280,
                "completion_tokens": 120,
                "total_tokens": 400
            }
        }
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestPostReleaseSecurityRemediation(unittest.TestCase):
    """Comprehensive automated security test suite for P0 & P1 post-release remediations."""

    @classmethod
    def setUpClass(cls):
        cls.original_db = PROJECT_ROOT / "data" / "leewu_mvp.db"
        assert cls.original_db.exists(), f"Original DB missing: {cls.original_db}"
        cls.orig_sha256 = hashlib.sha256(cls.original_db.read_bytes()).hexdigest()
        cls.orig_size = cls.original_db.stat().st_size
        cls.orig_mtime_ns = cls.original_db.stat().st_mtime_ns

        # 1. Start local mock Nebius server (0 paid API credits)
        cls.mock_nebius_port = _find_free_port()
        _MockNebiusHandler.call_log.clear()
        cls.mock_nebius_server = http.server.HTTPServer(("127.0.0.1", cls.mock_nebius_port), _MockNebiusHandler)
        cls.mock_nebius_thread = threading.Thread(target=cls.mock_nebius_server.serve_forever, daemon=True)
        cls.mock_nebius_thread.start()

        # 2. Create isolated temporary directory & SQLite copy
        cls.temp_dir = Path(tempfile.mkdtemp(prefix="leewu_post_release_sec_"))
        cls.iso_data_dir = cls.temp_dir / "data"
        cls.iso_uploads_dir = cls.iso_data_dir / "uploads"
        cls.iso_uploads_dir.mkdir(parents=True, exist_ok=True)
        cls.iso_db = cls.iso_data_dir / "leewu_mvp_sec_isolated.db"
        shutil.copy2(cls.original_db, cls.iso_db)

        # 3. Start main isolated server WITH ADMIN_API_KEY configured
        cls.port = _find_free_port()
        cls.admin_key = "sec-remediation-bearer-key-2026-9f8e7d6c5b4a"
        env = os.environ.copy()
        env["PORT"] = str(cls.port)
        env["HOST"] = "127.0.0.1"
        env["DATA_DIR"] = str(cls.iso_data_dir)
        env["LEEWU_DB_PATH"] = str(cls.iso_db)
        env["ADMIN_API_KEY"] = cls.admin_key
        env["NEBIUS_API_KEY"] = "v1.MOCK_NEBIUS_KEY_FOR_SECURITY_TESTS_ONLY_000000"
        env["NEBIUS_BASE_URL"] = f"http://127.0.0.1:{cls.mock_nebius_port}/v1"
        env.pop("REQUIRE_AUTH_FOR_WRITES", None)  # Rely on default (must fail closed)

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
        assert ready, "Security test server failed to start"

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try:
            cls.proc.wait(timeout=5)
        except Exception:
            cls.proc.kill()

        cls.mock_nebius_server.shutdown()
        cls.mock_nebius_server.server_close()
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

        # Verify original DB untouched
        assert hashlib.sha256(cls.original_db.read_bytes()).hexdigest() == cls.orig_sha256
        assert cls.original_db.stat().st_size == cls.orig_size
        assert cls.original_db.stat().st_mtime_ns == cls.orig_mtime_ns

    def _request(self, path: str, method: str = "GET", payload: dict = None, headers: dict = None, base_url: str = None):
        target_base = base_url or self.base_url
        req_headers = dict(headers or {})
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            req_headers.setdefault("Content-Type", "application/json")
        req = urllib.request.Request(f"{target_base}{path}", data=data, headers=req_headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                body = r.read().decode("utf-8")
                ct = r.headers.get("Content-Type", "")
                return r.status, (json.loads(body) if "application/json" in ct else body), dict(r.headers)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            try:
                return e.code, json.loads(body), dict(e.headers)
            except Exception:
                return e.code, body, dict(e.headers)

    def _get_survey_db_state(self, survey_id: str = "LW-DEMO-001") -> dict:
        conn = sqlite3.connect(str(self.iso_db), timeout=10.0)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM surveys WHERE survey_id = ?", (survey_id,))
        survey = dict(cur.fetchone())
        cur.execute("SELECT COUNT(*) FROM evidence WHERE survey_id = ?", (survey_id,))
        ev_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM ai_assessments WHERE survey_id = ?", (survey_id,))
        ai_count = cur.fetchone()[0]
        conn.close()
        return {"survey": survey, "evidence_count": ev_count, "ai_count": ai_count}

    def test_01_missing_bearer_token_returns_401_for_every_write_endpoint(self):
        """Missing Bearer token -> 401 for every write endpoint, including LW-DEMO-001."""
        write_endpoints = [
            ("/api/surveys/LW-DEMO-001/upload", {}),
            ("/api/surveys/LW-DEMO-001/ai-inspect", {"nitrogen_pressure": "0.25 bar"}),
            ("/api/surveys/LW-DEMO-001/approve", {"surveyor_name": "Unauthorized User"}),
            ("/api/surveys/LW-DEMO-001/reset", {}),
            ("/api/surveys/LW-PROD-999/upload", {}),
            ("/api/ai-ops/seed-demo", {"count": 5}),
            ("/api/ai-ops/clear-demo", {}),
            ("/api/ai-ops/alerts/resolve", {"alert_id": 1}),
        ]
        for endpoint, body in write_endpoints:
            with self.subTest(endpoint=endpoint):
                status, resp, _ = self._request(endpoint, method="POST", payload=body)
                self.assertEqual(status, 401, f"Expected 401 on {endpoint} without Bearer token, got {status}")
                self.assertEqual(resp.get("status"), "AUTH_REQUIRED")

    def test_02_invalid_bearer_token_returns_401_and_uses_compare_digest(self):
        """Invalid Bearer token -> 401 across all write and protected AI Ops endpoints; verifies secrets.compare_digest."""
        os.environ["LEEWU_DB_PATH"] = str(self.iso_db)
        import leewu_mvp_server
        src = inspect.getsource(leewu_mvp_server.check_admin_auth)
        self.assertIn("secrets.compare_digest", src, "check_admin_auth must use secrets.compare_digest")

        invalid_headers_list = [
            {"Authorization": "Bearer wrong-token-12345"},
            {"Authorization": "Bearer demo-admin-local"},
            {"Authorization": "Bearer local-demo-jwt"},
            {"Authorization": f"Bearer {self.admin_key[:-1]}X"},
            {"Authorization": "Bearer "},
            {"Authorization": f"Basic {self.admin_key}"},
            {"Authorization": self.admin_key},
        ]
        protected_targets = [
            ("POST", "/api/surveys/LW-DEMO-001/upload", {}),
            ("POST", "/api/surveys/LW-DEMO-001/ai-inspect", {}),
            ("POST", "/api/surveys/LW-DEMO-001/approve", {}),
            ("POST", "/api/surveys/LW-DEMO-001/reset", {}),
            ("POST", "/api/ai-ops/seed-demo", {}),
            ("POST", "/api/ai-ops/clear-demo", {}),
            ("GET", "/api/ai-ops/overview", None),
            ("GET", "/api/ai-ops/requests", None),
            ("GET", "/api/ai-ops/costs", None),
        ]
        for hdrs in invalid_headers_list:
            for method, path, payload in protected_targets:
                with self.subTest(auth=hdrs["Authorization"], method=method, path=path):
                    status, resp, _ = self._request(path, method=method, payload=payload, headers=hdrs)
                    self.assertEqual(status, 401, f"Expected 401 for {method} {path} with {hdrs}")

    def test_03_query_string_credentials_rejected(self):
        """Query-string credentials -> rejected with 401 on GET and POST, even if valid Bearer header is also present."""
        valid_hdr = {"Authorization": f"Bearer {self.admin_key}"}
        query_params = [
            f"admin_key={self.admin_key}",
            f"token={self.admin_key}",
            f"api_key={self.admin_key}",
            f"apikey={self.admin_key}",
            f"access_token={self.admin_key}",
            f"auth={self.admin_key}",
            f"bearer={self.admin_key}",
            f"secret={self.admin_key}",
        ]
        for qp in query_params:
            with self.subTest(query_param=qp):
                # Without header
                s1, _, _ = self._request(f"/api/ai-ops/overview?{qp}", method="GET")
                self.assertEqual(s1, 401)
                s2, _, _ = self._request(f"/api/surveys/LW-DEMO-001/upload?{qp}", method="POST", payload={})
                self.assertEqual(s2, 401)
                # Even WITH valid Bearer header, query credentials must be rejected
                s3, _, _ = self._request(f"/api/ai-ops/overview?{qp}", method="GET", headers=valid_hdr)
                self.assertEqual(s3, 401)
                s4, _, _ = self._request(f"/api/surveys/LW-DEMO-001/reset?{qp}", method="POST", payload={}, headers=valid_hdr)
                self.assertEqual(s4, 401)

    def test_04_missing_admin_api_key_fails_closed(self):
        """Missing ADMIN_API_KEY -> protected endpoints fail closed (401), never falling back to loopback or demo tokens."""
        no_key_port = _find_free_port()
        iso_db_nokey = self.iso_data_dir / "leewu_mvp_nokey.db"
        shutil.copy2(self.original_db, iso_db_nokey)

        env = os.environ.copy()
        env["PORT"] = str(no_key_port)
        env["HOST"] = "127.0.0.1"
        env["DATA_DIR"] = str(self.iso_data_dir)
        env["LEEWU_DB_PATH"] = str(iso_db_nokey)
        env["ADMIN_API_KEY"] = ""  # Explicitly missing/empty
        env["NEBIUS_API_KEY"] = ""

        proc_nokey = subprocess.Popen(
            [sys.executable, str(PROJECT_ROOT / "leewu_mvp_server.py")],
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        nokey_url = f"http://127.0.0.1:{no_key_port}"
        try:
            ready = False
            for _ in range(30):
                try:
                    with urllib.request.urlopen(f"{nokey_url}/api/health", timeout=1) as r:
                        if r.status == 200:
                            ready = True
                            break
                except Exception:
                    time.sleep(0.15)
            self.assertTrue(ready, "No-key server failed to start")

            for method, path, payload in [
                ("GET", "/api/ai-ops/overview", None),
                ("POST", "/api/ai-ops/seed-demo", {}),
                ("POST", "/api/surveys/LW-DEMO-001/upload", {}),
                ("POST", "/api/surveys/LW-DEMO-001/ai-inspect", {}),
                ("POST", "/api/surveys/LW-DEMO-001/approve", {}),
                ("POST", "/api/surveys/LW-DEMO-001/reset", {}),
            ]:
                # 1. Without Authorization header from 127.0.0.1
                st1, _, _ = self._request(path, method=method, payload=payload, base_url=nokey_url)
                self.assertEqual(st1, 401, f"Expected 401 when ADMIN_API_KEY is missing on {method} {path}")
                # 2. With legacy 'Bearer demo-admin-local' header
                st2, _, _ = self._request(
                    path, method=method, payload=payload,
                    headers={"Authorization": "Bearer demo-admin-local"},
                    base_url=nokey_url
                )
                self.assertEqual(st2, 401, f"Expected 401 for legacy demo-admin-local token on {method} {path}")
        finally:
            proc_nokey.terminate()
            try:
                proc_nokey.wait(timeout=5)
            except Exception:
                proc_nokey.kill()

    def test_05_loopback_requests_without_credentials_rejected(self):
        """Loopback requests (127.0.0.1, localhost, ::1) without credentials -> rejected for protected operations."""
        os.environ["LEEWU_DB_PATH"] = str(self.iso_db)
        from leewu_mvp_server import check_admin_auth

        class DummyHandler:
            def __init__(self, headers, client_ip, path="/api/ai-ops/overview"):
                self.headers = headers
                self.client_address = (client_ip, 54321)
                self.path = path

        old_key = os.environ.get("ADMIN_API_KEY")
        try:
            os.environ["ADMIN_API_KEY"] = self.admin_key
            for loopback_ip in ("127.0.0.1", "localhost", "::1"):
                h_no_cred = DummyHandler({}, loopback_ip)
                self.assertFalse(
                    check_admin_auth(h_no_cred, urllib.parse.urlparse("/api/ai-ops/overview")),
                    f"Loopback {loopback_ip} without credentials must be rejected!"
                )
            # Also verify with ADMIN_API_KEY unset
            os.environ["ADMIN_API_KEY"] = ""
            for loopback_ip in ("127.0.0.1", "localhost", "::1"):
                h_no_key = DummyHandler({}, loopback_ip)
                self.assertFalse(
                    check_admin_auth(h_no_key, urllib.parse.urlparse("/api/ai-ops/overview")),
                    f"Loopback {loopback_ip} with unset ADMIN_API_KEY must be rejected!"
                )
        finally:
            if old_key is None:
                os.environ.pop("ADMIN_API_KEY", None)
            else:
                os.environ["ADMIN_API_KEY"] = old_key

    def test_06_proxied_cloudflared_requests_cannot_bypass_authentication(self):
        """Test actual cloudflared-to-local-backend request path (127.0.0.1 origin socket + Cloudflare/proxy headers)."""
        spoofed_proxy_headers = {
            "Host": "api.leewuai.ro",
            "CF-Connecting-IP": "127.0.0.1",
            "X-Forwarded-For": "127.0.0.1, ::1, localhost",
            "X-Real-IP": "127.0.0.1",
            "X-Forwarded-Host": "localhost:8080",
            "X-Forwarded-Proto": "https",
            "CF-Ray": "8da1234567890abc-OTP",
            "CF-Visitor": '{"scheme":"https"}',
        }
        # 1. Unauthenticated proxied requests to protected GET and POST endpoints must all be rejected (401)
        for method, path, body in [
            ("GET", "/api/ai-ops/overview", None),
            ("GET", "/api/ai-ops/costs", None),
            ("POST", "/api/ai-ops/seed-demo", {"count": 5}),
            ("POST", "/api/surveys/LW-DEMO-001/upload", {}),
            ("POST", "/api/surveys/LW-DEMO-001/ai-inspect", {}),
            ("POST", "/api/surveys/LW-DEMO-001/approve", {}),
            ("POST", "/api/surveys/LW-DEMO-001/reset", {}),
        ]:
            with self.subTest(method=method, path=path):
                status, resp, _ = self._request(path, method=method, payload=body, headers=spoofed_proxy_headers)
                self.assertEqual(status, 401, f"Proxied request bypassed auth on {method} {path}")

        # 2. Authenticated proxied request (with valid Bearer token) succeeds through the same tunnel path
        authed_proxy_headers = dict(spoofed_proxy_headers)
        authed_proxy_headers["Authorization"] = f"Bearer {self.admin_key}"
        status_ok, ov_data, _ = self._request("/api/ai-ops/overview", method="GET", headers=authed_proxy_headers)
        self.assertEqual(status_ok, 200)
        self.assertIn("total_requests", ov_data)

    def test_07_public_demo_read_only_no_nebius_cost_no_data_mutation(self):
        """Public demo cannot trigger Nebius inference or mutate survey data; read-only GET endpoints remain accessible."""
        _MockNebiusHandler.call_log.clear()
        before_state = self._get_survey_db_state("LW-DEMO-001")

        # 1. Public read-only endpoints succeed without credentials
        st_health, _, _ = self._request("/api/health")
        self.assertEqual(st_health, 200)
        st_list, _, _ = self._request("/api/surveys")
        self.assertEqual(st_list, 200)
        st_det, det_body, _ = self._request("/api/surveys/LW-DEMO-001")
        self.assertEqual(st_det, 200)
        self.assertEqual(det_body["survey_id"], "LW-DEMO-001")
        st_exp, exp_html, _ = self._request("/api/surveys/LW-DEMO-001/export")
        self.assertEqual(st_exp, 200)
        self.assertIn("LW-DEMO-001", exp_html)

        # 2. Public write/inference attempts are blocked with 401
        self.assertEqual(self._request("/api/surveys/LW-DEMO-001/upload", method="POST", payload={})[0], 401)
        self.assertEqual(self._request("/api/surveys/LW-DEMO-001/ai-inspect", method="POST", payload={"nitrogen_pressure": "9.99 bar"})[0], 401)
        self.assertEqual(self._request("/api/surveys/LW-DEMO-001/approve", method="POST", payload={"surveyor_name": "Attacker"})[0], 401)
        self.assertEqual(self._request("/api/surveys/LW-DEMO-001/reset", method="POST", payload={})[0], 401)

        # 3. Confirm ZERO calls reached the mocked Nebius API and ZERO rows mutated in SQLite
        self.assertEqual(len(_MockNebiusHandler.call_log), 0, "Public unauthenticated request triggered Nebius inference!")
        after_state = self._get_survey_db_state("LW-DEMO-001")
        self.assertEqual(before_state, after_state, "Public unauthenticated requests mutated SQLite survey state!")

        # 4. Confirm frontend demo.html does not embed ADMIN_API_KEY
        demo_html = (PROJECT_ROOT / "demo.html").read_text(encoding="utf-8")
        self.assertNotIn(self.admin_key, demo_html)
        self.assertIn("getOperatorHeaders", demo_html)

    def test_08_valid_bearer_token_permits_write_operations_with_mocked_nebius(self):
        """Valid Bearer token -> permitted write operations (reset, upload, mocked ai-inspect, approve)."""
        auth_headers = {"Authorization": f"Bearer {self.admin_key}"}
        _MockNebiusHandler.call_log.clear()

        # 1. Reset
        st_rst, res_rst, _ = self._request("/api/surveys/LW-DEMO-001/reset", method="POST", payload={}, headers=auth_headers)
        self.assertEqual(st_rst, 200)
        self.assertTrue(res_rst["success"])

        # 2. Upload
        st_up, res_up, _ = self._request("/api/surveys/LW-DEMO-001/upload", method="POST", payload={}, headers=auth_headers)
        self.assertEqual(st_up, 201)
        self.assertTrue(res_up["success"])

        # 3. AI Inspect (calls local mocked Nebius server -> 0 paid credits)
        st_ai, res_ai, _ = self._request(
            "/api/surveys/LW-DEMO-001/ai-inspect",
            method="POST",
            payload={"nitrogen_pressure": "0.25 bar", "impact_recorder_g": "0.6 G"},
            headers=auth_headers
        )
        self.assertEqual(st_ai, 200)
        self.assertTrue(res_ai["success"])
        self.assertIn("Mocked Nebius Nemotron assessment", res_ai["assessment"])
        self.assertEqual(len(_MockNebiusHandler.call_log), 1)

        # 4. Approve
        st_app, res_app, _ = self._request(
            "/api/surveys/LW-DEMO-001/approve",
            method="POST",
            payload={"surveyor_name": "Ing. Alexandru Radu", "license_number": "DEMO-MWS-2026-001"},
            headers=auth_headers
        )
        self.assertEqual(st_app, 200)
        self.assertEqual(res_app["status"], "APPROVED")

    def test_09_login_rejects_arbitrary_passwords_and_enforces_read_only_preview(self):
        """Verify web/login.html and login.html remove >=6 char password fallback and keep demo preview read-only."""
        login_files = [PROJECT_ROOT / "login.html"]
        if (PROJECT_ROOT / "web" / "login.html").exists():
            login_files.append(PROJECT_ROOT / "web" / "login.html")
        if (PROJECT_ROOT / "dist" / "login.html").exists():
            login_files.append(PROJECT_ROOT / "dist" / "login.html")

        for lf in login_files:
            with self.subTest(login_file=str(lf)):
                content = lf.read_text(encoding="utf-8")
                # 1. Arbitrary 6+ char password fallback must be gone
                self.assertNotIn("password.length >= 6", content)
                self.assertNotIn("local-demo-jwt", content)
                # 2. Backend login failure must reject sign-in rather than falling back to DEMO_ACCOUNTS
                self.assertIn("Authentication rejected: Invalid credentials or authentication server unreachable", content)
                self.assertIn("Arbitrary client-side passwords are not accepted", content)
                # 3. Client-side preview must explicitly set authenticated: false, read_only: true, and remove leewu_auth_token
                self.assertIn("READ_ONLY_PREVIEW", content)
                self.assertIn("authenticated: false", content)
                self.assertIn("read_only: true", content)
                self.assertIn('localStorage.removeItem("leewu_auth_token")', content)

    def test_10_original_sqlite_database_unchanged(self):
        """Confirm original SQLite database (data/leewu_mvp.db) is 100% unmodified."""
        current_sha = hashlib.sha256(self.original_db.read_bytes()).hexdigest()
        current_stat = self.original_db.stat()
        self.assertEqual(current_sha, self.orig_sha256)
        self.assertEqual(current_stat.st_size, self.orig_size)
        self.assertEqual(current_stat.st_mtime_ns, self.orig_mtime_ns)


if __name__ == "__main__":
    unittest.main(verbosity=2)
