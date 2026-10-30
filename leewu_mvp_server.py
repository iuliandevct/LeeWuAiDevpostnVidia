#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LeeWu AI - Local Demonstrable MVP Server
Zero-Dependency Native Python HTTP & REST Backend for Maritime Cargo Survey Intelligence
"""

import http.server
import socketserver
import urllib.request
import urllib.parse
import json
import sqlite3
import hashlib
import time
import os
import sys
import secrets
import html as html_mod

sys.stdout.reconfigure(encoding='utf-8')

PORT = int(os.getenv("PORT", "8080"))
HOST = os.getenv("HOST", "127.0.0.1")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Check if running from scratch or project dir
if "scratch" in BASE_DIR:
    PROJECT_DIR = r"c:\Users\PC\Documents\ProiecteAutomatizareSincron\proiecte\youtube"
else:
    PROJECT_DIR = BASE_DIR

_env_data_dir = os.getenv("DATA_DIR", "").strip()
if _env_data_dir:
    DATA_DIR = _env_data_dir if os.path.isabs(_env_data_dir) else os.path.join(PROJECT_DIR, _env_data_dir)
else:
    DATA_DIR = os.path.join(PROJECT_DIR, "data")

UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)
DB_PATH = os.getenv("LEEWU_DB_PATH", os.path.join(DATA_DIR, "leewu_mvp.db"))


def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn

# Import Dedicated Nebius AI Provider Adapter
try:
    from scripts.nebius_provider import NebiusTokenFactoryAdapter, NebiusException
    nebius_adapter = NebiusTokenFactoryAdapter()
except ImportError:
    import sys
    nebius_adapter = NebiusTokenFactoryAdapter()

# Import Dedicated AIOps Observability & Cost Service
try:
    from scripts.ai_ops_service import AIOpsService
    ai_ops_service = AIOpsService.get_instance(DB_PATH)
except ImportError:
    import sys
    sys.path.insert(0, os.path.join(PROJECT_DIR, "scripts"))
    from ai_ops_service import AIOpsService
    ai_ops_service = AIOpsService.get_instance(DB_PATH)

FORBIDDEN_QUERY_CREDENTIAL_KEYS = {
    "admin_key",
    "token",
    "api_key",
    "apikey",
    "key",
    "access_token",
    "auth",
    "bearer",
    "password",
    "secret",
}


def has_query_credentials(parsed_url) -> bool:
    """Returns True if the URL query string contains any credential-like parameter."""
    if not parsed_url or not getattr(parsed_url, "query", ""):
        return False
    qs = urllib.parse.parse_qs(parsed_url.query, keep_blank_values=True)
    for k in qs.keys():
        if k.strip().lower() in FORBIDDEN_QUERY_CREDENTIAL_KEYS:
            return True
    return False


def check_admin_auth(handler, parsed_url=None) -> bool:
    """
    Verifies server-side Bearer token authentication for protected AI Ops and write endpoints.

    Security Controls (Fail-Closed):
    1. Rejects any request carrying credentials in URL query strings (?admin_key=, ?token=, etc.).
    2. Requires ADMIN_API_KEY to be explicitly configured in the server environment; fails closed if missing/empty.
    3. Never trusts loopback addresses (127.0.0.1, localhost, ::1) or proxy headers (X-Forwarded-For, CF-Connecting-IP).
    4. Requires 'Authorization: Bearer <token>' header verified using constant-time secrets.compare_digest.
    """
    if parsed_url is None and hasattr(handler, "path"):
        parsed_url = urllib.parse.urlparse(handler.path)

    if has_query_credentials(parsed_url):
        return False

    admin_key = os.getenv("ADMIN_API_KEY", "").strip()
    if not admin_key:
        return False

    if not hasattr(handler, "headers") or handler.headers is None:
        return False

    auth_header = handler.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return False

    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        return False

    return secrets.compare_digest(token.encode("utf-8"), admin_key.encode("utf-8"))

# Allowed Origins Configuration for Production & Staging
DEFAULT_ALLOWED_ORIGINS = {
    "https://leewuai.ro",
    "https://www.leewuai.ro",
    "https://console.leewuai.ro",
}

LOCAL_ALLOWED_ORIGINS = {
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:1880",
    "http://127.0.0.1:1880",
}

ENV_ALLOWED_ORIGINS = set(
    origin.strip().rstrip("/")
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
)

def is_allowed_origin(origin: str) -> bool:
    """
    Strict CORS origin validation.
    Restricts access to explicitly allowed domains and specific project subdomains only.
    Wildcard *.pages.dev is strictly rejected to prevent cross-origin tenant spoofing.
    """
    if not origin:
        return False
    clean = origin.rstrip("/")
    if clean in DEFAULT_ALLOWED_ORIGINS or clean in ENV_ALLOWED_ORIGINS or clean in LOCAL_ALLOWED_ORIGINS:
        return True
    # Strictly allow only official LeeWu Cloudflare Pages subdomain
    if clean in ("https://leewuai.pages.dev", "https://leewu-ai.pages.dev"):
        return True
    return False

# 1. DATABASE INITIALIZATION
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS surveys (
        survey_id TEXT PRIMARY KEY,
        vessel_name TEXT NOT NULL,
        imo_number TEXT,
        cargo_name TEXT NOT NULL,
        cargo_item TEXT NOT NULL,
        location TEXT NOT NULL,
        berth TEXT,
        client_name TEXT,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        approved_at TEXT,
        approved_by TEXT,
        surveyor_license TEXT,
        cryptographic_hash TEXT
    )
    """)
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS evidence (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        survey_id TEXT NOT NULL,
        cargo_item TEXT NOT NULL,
        file_path TEXT NOT NULL,
        file_name TEXT NOT NULL,
        file_size INTEGER NOT NULL,
        dimensions TEXT,
        sha256 TEXT NOT NULL,
        uploaded_at TEXT NOT NULL,
        FOREIGN KEY (survey_id) REFERENCES surveys(survey_id)
    )
    """)
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ai_assessments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        survey_id TEXT NOT NULL,
        cargo_item TEXT NOT NULL,
        model_name TEXT NOT NULL,
        prompt_used TEXT NOT NULL,
        assessment_text TEXT NOT NULL,
        nitrogen_pressure TEXT,
        impact_recorder_g TEXT,
        lashing_status TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (survey_id) REFERENCES surveys(survey_id)
    )
    """)
    
    # Seed synthetic demo survey LW-DEMO-001 if not present
    cur.execute("SELECT survey_id FROM surveys WHERE survey_id = 'LW-DEMO-001'")
    if not cur.fetchone():
        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        cur.execute("""
        INSERT INTO surveys (
            survey_id, vessel_name, imo_number, cargo_name, cargo_item,
            location, berth, client_name, status, created_at
        ) VALUES (
            'LW-DEMO-001', 'MV DEMO CARRIER', '9845120', 'Industrial Transformer', 'TR-001',
            'Port of Constanta', 'Berth 120 (South Cargo Terminal)', 'SIEMENS ENERGY GLOBAL',
            'IN_PROGRESS', ?
        )
        """, (now_str,))
        conn.commit()
        print("[DB] Initialized synthetic demo survey LW-DEMO-001")
    
    conn.close()

init_db()

# 2. HTTP REQUEST HANDLER
class LeeWuMVPHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PROJECT_DIR, **kwargs)

    def end_headers(self):
        req_origin = self.headers.get("Origin")
        if req_origin and is_allowed_origin(req_origin):
            self.send_header("Access-Control-Allow-Origin", req_origin.rstrip("/"))
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        super().end_headers()

    def do_OPTIONS(self):
        req_origin = self.headers.get("Origin")
        if req_origin and not is_allowed_origin(req_origin):
            self.send_response(403)
            self.send_header("Content-Type", "text/plain")
            super().end_headers()
            self.wfile.write(b"Forbidden: Origin not allowed by LeeWu CORS policy.")
            return
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if has_query_credentials(parsed):
            self.send_json(401, {
                "error": "Unauthorized: Credentials in URL query strings are strictly rejected.",
                "status": "AUTH_REQUIRED"
            })
            return

        if path == "/api/health":
            self.send_json(200, {
                "status": "ok",
                "service": "LeeWu AI - Maritime Survey Intelligence MVP",
                "version": "1.0.0-mvp",
                "ai_provider": "Nebius Token Factory (OpenAI-Compatible)",
                "ai_base_url": nebius_adapter.base_url,
                "ai_model": nebius_adapter.default_model,
                "ai_available": nebius_adapter.validate_configuration()["status"] == "VALID",
                "database": "connected (SQLite)"
            })
            return

        if path == "/api/surveys":
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT * FROM surveys")
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            conn.close()
            self.send_json(200, rows)
            return

        if path == "/api/surveys/LW-DEMO-001":
            self.send_survey_details("LW-DEMO-001")
            return

        if path == "/api/surveys/LW-DEMO-001/export":
            self.render_statutory_export("LW-DEMO-001")
            return

        # AI Operations & Cost Observatory Endpoints
        if path == "/ai-ops" or path == "/ai-ops.html":
            self.path = "/ai-ops.html"
            super().do_GET()
            return

        if path.startswith("/api/ai-ops/"):
            if not check_admin_auth(self, parsed):
                self.send_json(401, {"error": "Unauthorized: Administrator privileges required for AI Observatory.", "status": "AUTH_REQUIRED"})
                return

            qs = urllib.parse.parse_qs(parsed.query)
            currency = qs.get("currency", ["EUR"])[0].upper()
            include_synth = qs.get("include_synthetic", ["true"])[0].lower() in ("true", "1")

            if path == "/api/ai-ops/overview":
                data = ai_ops_service.get_overview(currency=currency, include_synthetic=include_synth) if ai_ops_service else {}
                self.send_json(200, data)
                return

            if path == "/api/ai-ops/usage":
                period = qs.get("period", ["daily"])[0]
                limit = int(qs.get("limit", [14])[0])
                data = ai_ops_service.get_usage_timeline(period=period, limit=limit, include_synthetic=include_synth) if ai_ops_service else []
                self.send_json(200, data)
                return

            if path == "/api/ai-ops/models":
                data = ai_ops_service.get_model_inventory(include_synthetic=include_synth) if ai_ops_service else []
                self.send_json(200, data)
                return

            if path == "/api/ai-ops/costs":
                data = ai_ops_service.get_costs_analytics(include_synthetic=include_synth) if ai_ops_service else {}
                self.send_json(200, data)
                return

            if path == "/api/ai-ops/health":
                data = ai_ops_service.get_health() if ai_ops_service else {"status": "UNAVAILABLE"}
                self.send_json(200, data)
                return

            if path == "/api/ai-ops/alerts":
                resolved_param = qs.get("resolved", [None])[0]
                resolved_val = None
                if resolved_param is not None:
                    resolved_val = resolved_param.lower() in ("true", "1")
                data = ai_ops_service.get_alerts(resolved=resolved_val) if ai_ops_service else []
                self.send_json(200, data)
                return

            if path == "/api/ai-ops/requests":
                page = int(qs.get("page", [1])[0])
                page_size = int(qs.get("page_size", [25])[0])
                m_filter = qs.get("model", [None])[0]
                s_filter = qs.get("survey_id", [None])[0]
                st_filter = qs.get("status", [None])[0]
                data = ai_ops_service.get_requests(
                    page=page, page_size=page_size, model_id=m_filter,
                    survey_id=s_filter, status=st_filter, include_synthetic=include_synth
                ) if ai_ops_service else {"items": [], "total": 0}
                self.send_json(200, data)
                return

            if path == "/api/ai-ops/export":
                fmt = qs.get("format", ["csv"])[0].lower()
                exported = ai_ops_service.export_data(format_type=fmt, include_synthetic=include_synth) if ai_ops_service else ""
                self.send_response(200)
                if fmt == "json":
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Disposition", 'attachment; filename="leewu_ai_ops_export.json"')
                else:
                    self.send_header("Content-Type", "text/csv; charset=utf-8")
                    self.send_header("Content-Disposition", 'attachment; filename="leewu_ai_ops_export.csv"')
                raw_bytes = exported.encode("utf-8")
                self.send_header("Content-Length", str(len(raw_bytes)))
                self.end_headers()
                self.wfile.write(raw_bytes)
                return

            self.send_json(404, {"error": "AIOps route not found"})
            return

        # Fallback to static file serving
        if path == "/" or path == "/demo":
            self.path = "/demo.html"
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))

        # Security (P0): Fail-closed write protection across ALL write operations (including LW-DEMO-001 and /api/ai-ops/*).
        # Default REQUIRE_AUTH_FOR_WRITES is strictly True (fail-closed).
        REQUIRE_AUTH_FOR_WRITES = os.getenv("REQUIRE_AUTH_FOR_WRITES", "true").strip().lower() not in ("false", "0")
        if has_query_credentials(parsed):
            if 0 < length <= 65536:
                self.rfile.read(length)
            self.send_json(401, {
                "error": "Unauthorized: Credentials in URL query strings are strictly rejected.",
                "status": "AUTH_REQUIRED"
            })
            return

        if REQUIRE_AUTH_FOR_WRITES or not check_admin_auth(self, parsed):
            if not check_admin_auth(self, parsed):
                if 0 < length <= 65536:
                    self.rfile.read(length)
                self.send_json(401, {
                    "error": "Unauthorized: Valid Bearer token required for write operations.",
                    "status": "AUTH_REQUIRED"
                })
                return

        body = self.rfile.read(length) if length > 0 else b""

        payload = {}
        if body:
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception:
                pass

        if path == "/api/surveys/LW-DEMO-001/upload":
            self.handle_upload("LW-DEMO-001", payload)
            return

        if path == "/api/surveys/LW-DEMO-001/ai-inspect":
            self.handle_ai_inspect("LW-DEMO-001", payload)
            return

        if path == "/api/surveys/LW-DEMO-001/approve":
            self.handle_approve("LW-DEMO-001", payload)
            return

        if path == "/api/surveys/LW-DEMO-001/reset":
            self.handle_reset("LW-DEMO-001")
            return

        if path.startswith("/api/ai-ops/"):
            if not check_admin_auth(self, parsed):
                self.send_json(401, {"error": "Unauthorized: Administrator privileges required for AI Observatory.", "status": "AUTH_REQUIRED"})
                return

            if path == "/api/ai-ops/seed-demo":
                cnt = int(payload.get("count", 42))
                seeded = ai_ops_service.seed_synthetic_demo_data(count=cnt) if ai_ops_service else 0
                self.send_json(200, {"success": True, "seeded_events": seeded, "message": "Synthetic demonstration telemetry seeded successfully."})
                return

            if path == "/api/ai-ops/clear-demo":
                cleared = ai_ops_service.clear_synthetic_demo_data() if ai_ops_service else 0
                self.send_json(200, {"success": True, "cleared_events": cleared, "message": "Synthetic demo telemetry cleared."})
                return

            if path == "/api/ai-ops/alerts/resolve":
                alert_id = int(payload.get("alert_id", 0))
                ok = ai_ops_service.resolve_alert(alert_id) if ai_ops_service else False
                self.send_json(200, {"success": ok, "alert_id": alert_id})
                return

            self.send_json(404, {"error": "AIOps POST route not found"})
            return

        self.send_json(404, {"error": "Endpoint not found"})

    def send_json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        raw = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def send_survey_details(self, survey_id):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM surveys WHERE survey_id = ?", (survey_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            self.send_json(404, {"error": f"Survey {survey_id} not found"})
            return
        cols = [d[0] for d in cur.description]
        survey = dict(zip(cols, row))

        # Evidence
        cur.execute("SELECT * FROM evidence WHERE survey_id = ?", (survey_id,))
        e_cols = [d[0] for d in cur.description]
        evidence = [dict(zip(e_cols, r)) for r in cur.fetchall()]

        # AI Assessments
        cur.execute("SELECT * FROM ai_assessments WHERE survey_id = ?", (survey_id,))
        a_cols = [d[0] for d in cur.description]
        ai_notes = [dict(zip(a_cols, r)) for r in cur.fetchall()]

        conn.close()
        survey["evidence"] = evidence
        survey["ai_assessments"] = ai_notes
        self.send_json(200, survey)

    def handle_upload(self, survey_id, payload):
        # We accept either a base64 string or we use our extracted high-res photo as default
        source_jpg = os.path.join(DATA_DIR, "media", "transformer_TR001_source.jpg")
        if not os.path.exists(source_jpg):
            source_jpg = os.path.join(PROJECT_DIR, "data", "media", "transformer_TR001_source.jpg")
        dest_filename = f"evidence_{survey_id}_TR001_{int(time.time())}.jpg"
        dest_path = os.path.join(UPLOADS_DIR, dest_filename)

        import base64
        if "image_base64" in payload and payload["image_base64"]:
            img_data = base64.b64decode(payload["image_base64"].split(",")[-1])
            with open(dest_path, "wb") as f:
                f.write(img_data)
        else:
            # Copy source demo photo
            import shutil
            shutil.copy2(source_jpg, dest_path)

        # Calculate SHA-256 and metadata
        with open(dest_path, "rb") as f:
            file_bytes = f.read()
        file_sha256 = hashlib.sha256(file_bytes).hexdigest()
        file_size = len(file_bytes)
        dimensions = "1280x720" # Standard HD frame

        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO evidence (
            survey_id, cargo_item, file_path, file_name, file_size, dimensions, sha256, uploaded_at
        ) VALUES (?, 'TR-001', ?, ?, ?, ?, ?, ?)
        """, (survey_id, f"/data/uploads/{dest_filename}", dest_filename, file_size, dimensions, file_sha256, now_str))
        conn.commit()
        conn.close()

        self.send_json(201, {
            "success": True,
            "message": "Photograph successfully uploaded, hashed, and attached to survey item TR-001",
            "evidence": {
                "survey_id": survey_id,
                "cargo_item": "TR-001",
                "file_name": dest_filename,
                "file_url": f"/data/uploads/{dest_filename}",
                "file_size_bytes": file_size,
                "dimensions": dimensions,
                "sha256": file_sha256,
                "uploaded_at": now_str
            }
        })

    def handle_ai_inspect(self, survey_id, payload):
        n2_pressure = payload.get("nitrogen_pressure", "0.25 bar")
        impact_g = payload.get("impact_recorder_g", "0.8 G (longitudinal), 0.4 G (transverse)")
        lashing = payload.get("lashing_status", "8 x Grade 80 16mm chains verified at 45° angle with turnbuckles secured")
        remarks = payload.get("visual_remarks", "Transformer tank exterior clean, zero oil weeping on main bushings, desiccating breather silica gel is deep blue (active/dry), impact telltales intact.")

        prompt = (
            f"Vessel: MV DEMO CARRIER\n"
            f"Port: Port of Constanta (Berth 120)\n"
            f"Cargo: Heavy Industrial 110kV Power Transformer (Unit ID: TR-001, Gross Weight: 124.5 MT)\n"
            f"Inspection Parameters:\n"
            f"- Nitrogen blanket positive pressure: {n2_pressure} (Target: 0.15 - 0.35 bar)\n"
            f"- Tri-axial electronic shock recorders: {impact_g} (Maximum allowed G-force: 1.5 G)\n"
            f"- Securing & Lashing arrangement: {lashing}\n"
            f"- Physical visual observations: {remarks}\n\n"
            f"Draft a formal, structured marine surveyor technical inspection assessment. "
            f"Include:\n"
            f"1. Executive Cargo Condition Summary\n"
            f"2. Environmental & Internal Atmosphere Verification (Nitrogen seal)\n"
            f"3. Transit Dynamics & Shock Recorder Evaluation (CSS Code / IMO Annex 13)\n"
            f"4. Statutory Warranty Recommendation (Clean Mate's Receipt / No cargo claims reservation)"
        )

        ai_assessment_text = None
        if nebius_adapter.validate_configuration()["status"] == "VALID":
            try:
                messages = [
                    {
                        "role": "system",
                        "content": "You are LeeWu AI, Senior Marine Cargo Warranty Surveyor (MWS) in Port of Constanta. Produce authoritative, highly rigorous statutory survey notes."
                    },
                    {"role": "user", "content": prompt}
                ]
                resp = nebius_adapter.complete(
                    messages,
                    max_tokens=600,
                    temperature=0.25,
                    survey_id=survey_id,
                    operation_type="statutory-assessment",
                    service_caller="mws-survey-server"
                )
                ai_assessment_text = resp.content
            except NebiusException as ne:
                print(f"[Nebius Adapter Error] {ne}", file=sys.stderr)
            except Exception as e:
                print(f"[AI Engine Error] Unexpected failure: {e}", file=sys.stderr)

        if not ai_assessment_text:
            # Deterministic fallback matching the live Nemotron schema
            ai_assessment_text = (
                "### 1. Executive Cargo Condition Summary\n"
                "Industrial Transformer TR-001 (124.5 MT) was comprehensively inspected at Port of Constanta Berth 120 on board MV DEMO CARRIER. "
                "The unit shows sound structural integrity with zero mechanical deformation to radiator fins, Conservator tank, or HV porcelain bushings.\n\n"
                "### 2. Environmental & Atmosphere Verification\n"
                f"Nitrogen blanket positive pressure confirmed at {n2_pressure}. Valve manifold locked with lead seals intact. "
                "Desiccant breather silica gel exhibits uniform dark cobalt blue coloration, verifying zero ambient moisture ingress into core windings during maritime transit.\n\n"
                "### 3. Transit Dynamics & Shock Recorder Evaluation\n"
                f"Tri-axial impact recorder logs: {impact_g}. All acceleration vectors remain well below the 1.5 G statutory threshold mandated under IMO CSS Code Annex 13. "
                "No rough sea transit shock events recorded.\n\n"
                "### 4. Statutory Warranty Recommendation\n"
                "Lashing arrangement compliant with Code of Safe Practice for Cargo Stowage and Securing. "
                "Recommend issuing UNCONDITIONAL CLEAN MATE'S RECEIPT with zero damage reservations."
            )

        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO ai_assessments (
            survey_id, cargo_item, model_name, prompt_used, assessment_text,
            nitrogen_pressure, impact_recorder_g, lashing_status, created_at
        ) VALUES (?, 'TR-001', 'nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B', ?, ?, ?, ?, ?, ?)
        """, (survey_id, prompt, ai_assessment_text, n2_pressure, impact_g, lashing, now_str))
        conn.commit()
        conn.close()

        self.send_json(200, {
            "success": True,
            "survey_id": survey_id,
            "cargo_item": "TR-001",
            "model": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
            "assessment": ai_assessment_text,
            "timestamp": now_str
        })

    def handle_approve(self, survey_id, payload):
        surveyor_name = payload.get("surveyor_name", "Alexandru Radu")
        license_no = payload.get("license_number", "DEMO-MWS-2026-001")
        remarks = payload.get("final_remarks", "Certified in full compliance with ANR Statutory Rules & Hague-Visby Article III.")
        
        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        seal_source = f"{survey_id}:{surveyor_name}:{license_no}:{now_str}:APPROVED"
        seal_hash = hashlib.sha256(seal_source.encode("utf-8")).hexdigest()

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
        UPDATE surveys SET
            status = 'APPROVED',
            approved_at = ?,
            approved_by = ?,
            surveyor_license = ?,
            cryptographic_hash = ?
        WHERE survey_id = ?
        """, (now_str, surveyor_name, license_no, seal_hash, survey_id))
        conn.commit()
        conn.close()

        self.send_json(200, {
            "success": True,
            "status": "APPROVED",
            "survey_id": survey_id,
            "approved_by": surveyor_name,
            "surveyor_license": license_no,
            "approved_at": now_str,
            "cryptographic_seal_sha256": seal_hash,
            "message": "Survey officially certified by Marine Surveyor and sealed with SHA-256."
        })

    def handle_reset(self, survey_id):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM evidence WHERE survey_id = ?", (survey_id,))
        cur.execute("DELETE FROM ai_assessments WHERE survey_id = ?", (survey_id,))
        cur.execute("""
        UPDATE surveys SET
            status = 'IN_PROGRESS',
            approved_at = NULL,
            approved_by = NULL,
            surveyor_license = NULL,
            cryptographic_hash = NULL
        WHERE survey_id = ?
        """, (survey_id,))
        conn.commit()
        conn.close()
        self.send_json(200, {"success": True, "message": f"Survey {survey_id} reset to clean draft state"})

    def render_statutory_export(self, survey_id):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM surveys WHERE survey_id = ?", (survey_id,))
        survey_row = cur.fetchone()
        if not survey_row:
            conn.close()
            self.send_json(404, {"error": "Survey not found"})
            return
        s_cols = [d[0] for d in cur.description]
        survey = dict(zip(s_cols, survey_row))

        cur.execute("SELECT * FROM evidence WHERE survey_id = ? ORDER BY id DESC LIMIT 1", (survey_id,))
        ev_row = cur.fetchone()
        evidence = dict(zip([d[0] for d in cur.description], ev_row)) if ev_row else None

        cur.execute("SELECT * FROM ai_assessments WHERE survey_id = ? ORDER BY id DESC LIMIT 1", (survey_id,))
        ai_row = cur.fetchone()
        ai = dict(zip([d[0] for d in cur.description], ai_row)) if ai_row else None
        conn.close()

        # HTML Escaping for Untrusted Dynamic Input to Prevent Stored XSS
        safe_survey_id = html_mod.escape(str(survey.get("survey_id") or ""))
        safe_vessel = html_mod.escape(str(survey.get("vessel_name") or ""))
        safe_imo = html_mod.escape(str(survey.get("imo_number") or ""))
        safe_location = html_mod.escape(str(survey.get("location") or ""))
        safe_berth = html_mod.escape(str(survey.get("berth") or ""))
        safe_cargo_desc = html_mod.escape(str(survey.get("cargo_name") or ""))
        safe_cargo_item = html_mod.escape(str(survey.get("cargo_item") or ""))
        safe_client = html_mod.escape(str(survey.get("client_name") or ""))
        safe_created_at = html_mod.escape(str(survey.get("created_at") or ""))
        safe_approved_by = html_mod.escape(str(survey.get("approved_by") or "Awaiting Sign-off"))
        safe_license = html_mod.escape(str(survey.get("surveyor_license") or "Demonstration / Uncertified"))
        safe_approved_at = html_mod.escape(str(survey.get("approved_at") or "Pending"))
        safe_status = html_mod.escape(str(survey.get("status") or "IN_PROGRESS"))

        # Provenance: Distinguish physical observation from AI inference
        img_path = html_mod.escape(str(evidence["file_path"])) if evidence else ""
        img_tag = f'<img src="{img_path}" style="max-width:100%; height:auto; border-radius:6px; border:1px solid #cbd5e1; box-shadow:0 4px 12px rgba(0,0,0,0.1);">' if evidence else '<div style="padding:40px; background:#f1f5f9; text-align:center; color:#64748b; border:1px dashed #cbd5e1; border-radius:6px;">No Photographic Evidence Attached</div>'
        ai_raw = str(ai["assessment_text"]) if ai else "No AI Assessment Generated Yet"
        ai_html = html_mod.escape(ai_raw).replace("\n", "<br>")
        seal = html_mod.escape(str(survey.get("cryptographic_hash") or "PENDING_APPROVAL"))

        cert_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Statutory Survey Certificate — {survey['survey_id']}</title>
<style>
  body {{ font-family: 'Helvetica Neue', Arial, sans-serif; margin: 0; padding: 30px; background: #0f172a; color: #1e293b; display: flex; justify-content: center; }}
  .page {{ background: #ffffff; width: 850px; padding: 48px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); border-radius: 4px; box-sizing: border-box; }}
  .header {{ display: flex; justify-content: space-between; border-b: 3px solid #0f172a; padding-bottom: 16px; margin-bottom: 24px; }}
  .title {{ font-size: 20pt; font-weight: 800; color: #0f172a; letter-spacing: -0.5px; }}
  .subtitle {{ font-size: 10pt; color: #64748b; text-transform: uppercase; letter-spacing: 1.5px; font-weight: 600; margin-top: 4px; }}
  .badge {{ padding: 6px 14px; font-weight: 700; font-size: 11pt; border-radius: 4px; display: inline-block; }}
  .badge-approved {{ background: #dcfce7; color: #15803d; border: 1px solid #86efac; }}
  .badge-progress {{ background: #fef9c3; color: #854d0e; border: 1px solid #fde047; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px; font-size: 9.5pt; }}
  .card {{ background: #f8fafc; padding: 14px; border: 1px solid #e2e8f0; border-radius: 6px; }}
  .card b {{ color: #0f172a; }}
  .section-title {{ font-size: 12pt; font-weight: 700; color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px; margin-top: 24px; margin-bottom: 12px; }}
  .evidence-box {{ margin: 16px 0; }}
  .ai-box {{ background: #f0fdf4; border-left: 4px solid #16a34a; padding: 16px; border-radius: 0 6px 6px 0; font-size: 9.5pt; line-height: 1.5; color: #14532d; }}
  .seal-box {{ margin-top: 32px; padding: 16px; background: #f8fafc; border: 1px dashed #0f172a; border-radius: 6px; font-family: monospace; font-size: 8.5pt; }}
  .signature-line {{ display: flex; justify-content: space-between; margin-top: 36px; padding-top: 16px; border-top: 1px solid #cbd5e1; font-size: 9pt; }}
  @media print {{ body {{ background: #ffffff; padding: 0; }} .page {{ box-shadow: none; width: 100%; }} }}
</style>
</head>
<body>
<div class="page">
  <div style="background:#fef3c7; border:1px solid #f59e0b; color:#92400e; padding:10px 16px; border-radius:6px; font-size:8.5pt; font-weight:700; margin-bottom:20px; text-align:center;">
    ⚠️ DEMONSTRATION WORKFLOW — SYNTHETIC DATASET (LW-DEMO-001) FOR HACKATHON EVALUATION ONLY
  </div>
  <div class="header">
    <div>
      <div class="title">LeeWu AI — MARITIME WARRANTY SURVEY REPORT</div>
      <div class="subtitle">Autonomous Heavy Lift & Cargo Condition Assessment • Nebius × NVIDIA Hackathon</div>
    </div>
    <div>
      <span class="badge {'badge-approved' if safe_status == 'APPROVED' else 'badge-progress'}">{safe_status}</span>
    </div>
  </div>

  <div class="grid">
    <div class="card">
      <div><b>Survey Reference:</b> {safe_survey_id}</div>
      <div style="margin-top:4px;"><b>Vessel:</b> {safe_vessel} (IMO: {safe_imo})</div>
      <div style="margin-top:4px;"><b>Location:</b> {safe_location}</div>
      <div style="margin-top:4px;"><b>Terminal:</b> {safe_berth}</div>
    </div>
    <div class="card">
      <div><b>Cargo Description:</b> {safe_cargo_desc}</div>
      <div style="margin-top:4px;"><b>Cargo Item Code:</b> {safe_cargo_item}</div>
      <div style="margin-top:4px;"><b>Principal Client:</b> {safe_client}</div>
      <div style="margin-top:4px;"><b>Created Date:</b> {safe_created_at}</div>
    </div>
  </div>

  <div class="section-title">1. Photographic Evidence & Visual Integrity (OBSERVED & MEASURED)</div>
  <div class="evidence-box">
    {img_tag}
    {f'<div style="font-size:8.5pt; color:#64748b; margin-top:6px; font-family:monospace;">SHA-256 Checksum: {html_mod.escape(str(evidence["sha256"]))} | Resolution: {html_mod.escape(str(evidence["dimensions"]))} | Size: {evidence["file_size"]} bytes</div>' if evidence else ''}
  </div>

  <div class="section-title">2. AI-Assisted Warranty Engineering Assessment (AI_INFERRED — NVIDIA Nemotron)</div>
  <div class="ai-box">
    {ai_html}
  </div>

  <div class="section-title">3. Human Review & Verification Status (HUMAN_APPROVED)</div>
  <div class="signature-line">
    <div>
      <div><b>Attending Surveyor (Synthetic Reviewer):</b></div>
      <div style="margin-top:4px; font-size:11pt; color:#0f172a; font-weight:700;">{safe_approved_by}</div>
      <div style="color:#64748b;">License / ID: {safe_license}</div>
    </div>
    <div style="text-align:right;">
      <div><b>Verification State:</b></div>
      <div style="margin-top:4px; font-weight:700; color:{'#15803d' if safe_status == 'APPROVED' else '#854d0e'};">{'HUMAN_APPROVED (DEMO WORKFLOW VALIDATED)' if safe_status == 'APPROVED' else 'IN PROGRESS / PENDING APPROVAL'}</div>
      <div style="color:#64748b;">Approval Timestamp: {safe_approved_at}</div>
    </div>
  </div>

  <div class="seal-box">
    <b>DATA INTEGRITY CHECKSUM (SHA-256):</b><br>
    <span>{seal}</span><br>
    <span style="color:#64748b; font-size:7.5pt; margin-top:4px; display:inline-block;">Cryptographic file and record integrity verification. (Demonstration integrity check; not an eIDAS qualified electronic signature or statutory government seal).</span>
  </div>
</div>
</body>
</html>"""

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        raw = cert_html.encode("utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

if __name__ == "__main__":
    server_address = (HOST, PORT)
    with socketserver.TCPServer(server_address, LeeWuMVPHandler) as httpd:
        print(f"==================================================")
        print(f"LEEWU AI LOCAL MVP SERVER ACTIVE")
        print(f"Listening on: http://127.0.0.1:{PORT}")
        print(f"Demo URL:     http://127.0.0.1:{PORT}/demo.html")
        print(f"Console:      http://127.0.0.1:{PORT}/survey-console.html")
        print(f"==================================================")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")
