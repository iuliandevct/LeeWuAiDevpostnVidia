#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloudflare Preflight Validation Suite — Without Tunnel Activation
Project: LeeWu AI — Maritime Cargo Survey Intelligence

Validates:
1. Pages: Static files, entry points, relative API routing, zero build dependencies.
2. API: Allowed domains, Bearer authentication, strict CORS (wildcard .pages.dev rejection), and all 11 endpoints.
3. Tunnel: Configuration structure and ingress route validation (`cloudflare/config.yml`).
4. Headers & Secrets: `_headers` rules, live HTTP security headers, `.env.example` hygiene, zero frontend secrets.
5. Zero external side effects: No DNS changes, no public port exposure (loopback 127.0.0.1 only), no active `cloudflared` tunnel, original SQLite DB untouched.
"""

import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestCloudflarePreflight(unittest.TestCase):
    """Comprehensive Cloudflare Pages, API, CORS, Headers, and Tunnel Preflight Suite."""

    @classmethod
    def setUpClass(cls):
        cls.original_db = PROJECT_ROOT / "data" / "leewu_mvp.db"
        cls.orig_sha256 = hashlib.sha256(cls.original_db.read_bytes()).hexdigest()

        cls.temp_dir = Path(tempfile.mkdtemp(prefix="leewu_cf_preflight_"))
        cls.iso_data_dir = cls.temp_dir / "data"
        (cls.iso_data_dir / "uploads").mkdir(parents=True, exist_ok=True)
        cls.iso_db = cls.iso_data_dir / "leewu_mvp_preflight.db"
        shutil.copy2(cls.original_db, cls.iso_db)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            cls.port = s.getsockname()[1]

        cls.admin_key = "preflight-admin-token-constant-time-check"
        env = os.environ.copy()
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
        for _ in range(30):
            try:
                with urllib.request.urlopen(f"{cls.base_url}/api/health", timeout=2) as r:
                    if r.status == 200:
                        ready = True
                        break
            except Exception:
                time.sleep(0.15)
        assert ready, "Preflight test server failed to start"

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try:
            cls.proc.wait(timeout=5)
        except Exception:
            cls.proc.kill()
        if cls.proc.stdout:
            cls.proc.stdout.close()
        if cls.proc.stderr:
            cls.proc.stderr.close()
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

        after_sha = hashlib.sha256(cls.original_db.read_bytes()).hexdigest()
        assert after_sha == cls.orig_sha256, "Original DB modified during Cloudflare Preflight!"

    def _raw_request(self, path: str, method: str = "GET", headers: dict = None):
        req = urllib.request.Request(f"{self.base_url}{path}", headers=headers or {}, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, r.read().decode("utf-8", errors="replace"), dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", errors="replace"), dict(e.headers)

    def test_01_pages_static_files_and_configuration(self):
        """1. Pages: Verify static HTML/CSS/JS assets, entry points, and relative API routes."""
        required_static = [
            "index.html",
            "landing.html",
            "login.html",
            "prices.html",
            "demo.html",
            "survey-console.html",
            "survey.html",
            "ai-ops.html",
            "ai_ops.js",
            "ai_ops.css",
            "_headers",
        ]
        for rel in required_static:
            fpath = PROJECT_ROOT / rel
            self.assertTrue(fpath.exists(), f"Missing static asset: {rel}")
            self.assertGreater(fpath.stat().st_size, 100, f"Empty static asset: {rel}")

        # Verify HTTP serving of static pages
        for page in ["/index.html", "/landing.html", "/login.html", "/prices.html", "/demo.html", "/ai-ops.html"]:
            code, body, _ = self._raw_request(page)
            self.assertEqual(code, 200, f"Static page {page} did not return 200")
            self.assertIn("<!doctype html>", body[:200].lower())

        # Verify ai_ops.js uses relative API paths (/api/ai-ops/...)
        js_code = (PROJECT_ROOT / "ai_ops.js").read_text(encoding="utf-8")
        self.assertIn("/api/ai-ops/overview", js_code)
        self.assertIn("/api/ai-ops/usage", js_code)
        self.assertIn("/api/ai-ops/models", js_code)

    def test_02_api_domains_auth_cors_and_endpoints(self):
        """2. API: Validate allowed CORS domains, wildcard rejection, Bearer auth, and all 11 endpoints."""
        # A. Official production domains and Pages subdomains allowed
        for allowed_origin in [
            "https://leewuai.ro",
            "https://www.leewuai.ro",
            "https://console.leewuai.ro",
            "https://leewuai.pages.dev",
            "https://leewu-ai.pages.dev",
        ]:
            code, _, hdrs = self._raw_request("/api/health", method="OPTIONS", headers={"Origin": allowed_origin})
            self.assertEqual(code, 204, f"OPTIONS failed for allowed origin {allowed_origin}")
            self.assertEqual(hdrs.get("Access-Control-Allow-Origin"), allowed_origin)

        # B. Unauthorized wildcard .pages.dev and third-party origins strictly rejected
        for untrusted_origin in [
            "https://malicious-tenant.pages.dev",
            "https://spoof-leewuai.pages.dev",
            "https://evil.example.com",
        ]:
            code_opt, _, hdrs_opt = self._raw_request("/api/health", method="OPTIONS", headers={"Origin": untrusted_origin})
            self.assertEqual(code_opt, 403, f"Untrusted origin {untrusted_origin} was not rejected on OPTIONS!")
            self.assertIsNone(hdrs_opt.get("Access-Control-Allow-Origin"))

            code_get, _, hdrs_get = self._raw_request("/api/health", method="GET", headers={"Origin": untrusted_origin})
            self.assertEqual(code_get, 200)
            self.assertIsNone(hdrs_get.get("Access-Control-Allow-Origin"))

        # C. All 11 API GET endpoints return HTTP 200 with valid auth
        auth_hdr = {"Authorization": f"Bearer {self.admin_key}"}
        endpoints = [
            "/api/health",
            "/api/surveys",
            "/api/surveys/LW-DEMO-001",
            "/api/surveys/LW-DEMO-001/export",
            "/api/ai-ops/overview",
            "/api/ai-ops/health",
            "/api/ai-ops/models",
            "/api/ai-ops/usage",
            "/api/ai-ops/costs",
            "/api/ai-ops/alerts",
            "/api/ai-ops/requests",
        ]
        for ep in endpoints:
            code, _, _ = self._raw_request(ep, headers=auth_hdr)
            self.assertEqual(code, 200, f"Endpoint {ep} failed with HTTP {code}")

    def test_03_tunnel_configuration_and_routes(self):
        """3. Tunnel: Validate reconciled `cloudflare/config.yml` (API-only ingress, Node-RED/n8n excluded, 404 catch-all)."""
        cfg_path = PROJECT_ROOT / "cloudflare" / "config.yml"
        self.assertTrue(cfg_path.exists())
        cfg_text = cfg_path.read_text(encoding="utf-8")

        self.assertIn("tunnel: leewu-tunnel", cfg_text)
        self.assertIn("credentials-file: /etc/cloudflared/leewu-tunnel.json", cfg_text)
        self.assertIn("hostname: api.leewuai.ro", cfg_text)
        self.assertIn("path: ^/api/.*", cfg_text)
        self.assertIn("http://127.0.0.1:8080", cfg_text)

        # Verify active (uncommented) lines do NOT expose Node-RED (:1880) or n8n (:5678)
        non_comment_lines = [
            line.strip() for line in cfg_text.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        active_block = "\n".join(non_comment_lines)
        self.assertNotIn("1880", active_block, "Node-RED port 1880 must not be exposed in active Tunnel ingress!")
        self.assertNotIn("5678", active_block, "n8n port 5678 must not be exposed in active Tunnel ingress!")
        self.assertEqual(non_comment_lines[-1], "- service: http_status:404")

    def test_04_security_headers_and_secrets_hygiene(self):
        """4. Verify `_headers`, HTTP response security headers, and zero secrets in static/config files."""
        # A. Check _headers file
        headers_file = (PROJECT_ROOT / "_headers").read_text(encoding="utf-8")
        self.assertIn("X-Content-Type-Options: nosniff", headers_file)
        self.assertIn("X-Frame-Options: SAMEORIGIN", headers_file)
        self.assertIn("Referrer-Policy: strict-origin-when-cross-origin", headers_file)
        self.assertIn("Permissions-Policy: camera=(), microphone=(), geolocation=()", headers_file)

        # B. Check live HTTP response headers from leewu_mvp_server.py
        code, body, hdrs = self._raw_request("/api/health")
        self.assertEqual(code, 200)
        self.assertEqual(hdrs.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(hdrs.get("X-Frame-Options"), "SAMEORIGIN")
        self.assertEqual(hdrs.get("Referrer-Policy"), "strict-origin-when-cross-origin")
        self.assertEqual(hdrs.get("Permissions-Policy"), "camera=(), microphone=(), geolocation=()")
        self.assertNotIn("leewu_mvp.db", body, "Health endpoint must not leak filesystem DB path")

        # C. Check .env.example and frontend HTML/JS files for secrets
        secret_regex = re.compile(r"(v1\.Cm[A-Za-z0-9_\-\.]{20,}|\b\d{8,11}:[A-Za-z0-9_-]{30,45}\b)")
        files_to_scan = [
            PROJECT_ROOT / ".env.example",
            PROJECT_ROOT / "cloudflare" / "config.yml",
            PROJECT_ROOT / "index.html",
            PROJECT_ROOT / "landing.html",
            PROJECT_ROOT / "login.html",
            PROJECT_ROOT / "prices.html",
            PROJECT_ROOT / "demo.html",
            PROJECT_ROOT / "survey-console.html",
            PROJECT_ROOT / "survey.html",
            PROJECT_ROOT / "ai-ops.html",
            PROJECT_ROOT / "ai_ops.js",
        ]
        for f in files_to_scan:
            content = f.read_text(encoding="utf-8", errors="ignore")
            matches = secret_regex.findall(content)
            self.assertEqual(matches, [], f"Secret pattern found in {f.name}: {matches}")

    def test_05_no_active_tunnel_or_public_port_exposure(self):
        """5. Confirm `cloudflared` tunnel is NOT running and server default bind is loopback `127.0.0.1`."""
        # Check server source default bind
        srv_code = (PROJECT_ROOT / "leewu_mvp_server.py").read_text(encoding="utf-8")
        self.assertIn('HOST = os.getenv("HOST", "127.0.0.1")', srv_code)

        # Confirm cloudflared is not active (cross-platform Windows + Linux)
        if os.name == "nt":
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-Process cloudflared -ErrorAction SilentlyContinue"],
                capture_output=True, text=True
            )
        else:
            res = subprocess.run(
                ["pgrep", "-x", "cloudflared"],
                capture_output=True, text=True
            )
        self.assertEqual(res.stdout.strip(), "", "cloudflared process should not be active during preflight!")


if __name__ == "__main__":
    unittest.main(verbosity=2)
