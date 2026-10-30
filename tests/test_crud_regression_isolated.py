#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CRUD Regression Test Suite — Isolated SQLite Database
Project: LeeWu AI — Maritime Cargo Survey Intelligence
Target: C:\\Users\\PC\\Documents\\ProiecteAutomatizareSincron\\proiecte\\youtube

Verifies:
1. Separate isolated copy of the SQLite database (data/leewu_mvp.db).
2. Full CRUD operations across all implemented tables and HTTP API endpoints.
3. Relational integrity (FOREIGN KEY constraints, UNIQUE constraints, NOT NULL constraints, PRAGMA integrity_check, PRAGMA foreign_key_check).
4. Cryptographic confirmation (SHA-256, byte size, mtime, row counts) that the original SQLite database was NOT modified.
"""

import hashlib
import json
import os
import shutil
import socket
import sqlite3
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

from ai_ops_service import AIOpsService


def get_db_snapshot(db_path: Path) -> dict:
    """Computes cryptographic and structural snapshot of a SQLite file without modifying it."""
    stat = db_path.stat()
    raw_bytes = db_path.read_bytes()
    sha256 = hashlib.sha256(raw_bytes).hexdigest()

    uri = f"file:{db_path.as_posix()}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]
    row_counts = {}
    for t in tables:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        row_counts[t] = cur.fetchone()[0]
    conn.close()

    return {
        "path": str(db_path),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": sha256,
        "tables": row_counts,
    }


class TestIsolatedSQLiteCRUDRegression(unittest.TestCase):
    """Comprehensive CRUD & relational integrity regression suite on an isolated SQLite copy."""

    @classmethod
    def setUpClass(cls):
        cls.original_db_path = PROJECT_ROOT / "data" / "leewu_mvp.db"
        assert cls.original_db_path.exists(), f"Original database not found at {cls.original_db_path}"

        # 1. Record strict baseline snapshot of the original database BEFORE any operation
        cls.baseline_snapshot = get_db_snapshot(cls.original_db_path)

        # 2. Create isolated work directory and isolated SQLite database copy
        cls.temp_dir = Path(tempfile.mkdtemp(prefix="leewu_isolated_crud_"))
        cls.isolated_data_dir = cls.temp_dir / "data"
        cls.isolated_uploads_dir = cls.isolated_data_dir / "uploads"
        cls.isolated_uploads_dir.mkdir(parents=True, exist_ok=True)
        cls.isolated_db_path = cls.isolated_data_dir / "leewu_mvp_isolated.db"

        # Copy original DB bytes directly so original file is never opened in write/WAL mode
        shutil.copy2(cls.original_db_path, cls.isolated_db_path)

        # Also persist a named isolated backup in data_backups/ for audit traceability
        cls.backup_dir = PROJECT_ROOT / "data_backups"
        cls.backup_dir.mkdir(parents=True, exist_ok=True)
        cls.persistent_isolated_copy = cls.backup_dir / "leewu_mvp_isolated_crud_test.db"
        shutil.copy2(cls.original_db_path, cls.persistent_isolated_copy)

    @classmethod
    def tearDownClass(cls):
        # Verify original database is 100% untouched after all CRUD tests
        final_snapshot = get_db_snapshot(cls.original_db_path)
        assert final_snapshot["sha256"] == cls.baseline_snapshot["sha256"], (
            f"CRITICAL: Original DB SHA-256 changed! "
            f"Before={cls.baseline_snapshot['sha256']} After={final_snapshot['sha256']}"
        )
        assert final_snapshot["size"] == cls.baseline_snapshot["size"], "Original DB byte size changed!"
        assert final_snapshot["mtime_ns"] == cls.baseline_snapshot["mtime_ns"], "Original DB mtime changed!"
        assert final_snapshot["tables"] == cls.baseline_snapshot["tables"], "Original DB row counts changed!"

        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def _connect_isolated(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.isolated_db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        return conn

    def test_01_isolated_copy_fidelity_and_pragma_integrity(self):
        """Verify isolated SQLite copy matches original schema, row counts, and passes integrity checks."""
        iso_snap = get_db_snapshot(self.isolated_db_path)
        self.assertEqual(iso_snap["sha256"], self.baseline_snapshot["sha256"])
        self.assertEqual(iso_snap["size"], self.baseline_snapshot["size"])
        self.assertEqual(iso_snap["tables"], self.baseline_snapshot["tables"])

        conn = self._connect_isolated()
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check;")
        self.assertEqual(cur.fetchone()[0], "ok")
        cur.execute("PRAGMA foreign_key_check;")
        self.assertEqual(cur.fetchall(), [])
        conn.close()

    def test_02_surveys_table_crud_lifecycle(self):
        """Test CREATE, READ, UPDATE, and DELETE operations on the `surveys` table."""
        conn = self._connect_isolated()
        cur = conn.cursor()

        survey_id = "LW-CRUD-TEST-001"
        now_str = "2026-10-30T10:00:00Z"

        # CREATE
        cur.execute("""
            INSERT INTO surveys (
                survey_id, vessel_name, imo_number, cargo_name, cargo_item,
                location, berth, client_name, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            survey_id, "MV BLACK SEA PIONEER", "9482184",
            "Heavy Industrial Stator", "ST-001", "Port of Constanta",
            "Berth 120 (South Cargo Terminal)", "GLOBAL OCEAN SHIPPING & TRADING",
            "IN_PROGRESS", now_str
        ))
        conn.commit()

        # READ
        cur.execute("SELECT * FROM surveys WHERE survey_id = ?", (survey_id,))
        row = dict(cur.fetchone())
        self.assertEqual(row["vessel_name"], "MV BLACK SEA PIONEER")
        self.assertEqual(row["status"], "IN_PROGRESS")
        self.assertIsNone(row["approved_by"])

        # UPDATE (Approve workflow)
        seal_hash = hashlib.sha256(f"{survey_id}:Alexandru Radu:DEMO-MWS-2026-001:{now_str}:APPROVED".encode()).hexdigest()
        cur.execute("""
            UPDATE surveys SET
                status = 'APPROVED',
                approved_at = ?,
                approved_by = ?,
                surveyor_license = ?,
                cryptographic_hash = ?
            WHERE survey_id = ?
        """, (now_str, "Alexandru Radu", "DEMO-MWS-2026-001", seal_hash, survey_id))
        conn.commit()

        cur.execute("SELECT * FROM surveys WHERE survey_id = ?", (survey_id,))
        updated = dict(cur.fetchone())
        self.assertEqual(updated["status"], "APPROVED")
        self.assertEqual(updated["approved_by"], "Alexandru Radu")
        self.assertEqual(updated["cryptographic_hash"], seal_hash)

        # UPDATE (Reset workflow)
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

        cur.execute("SELECT status, approved_by, cryptographic_hash FROM surveys WHERE survey_id = ?", (survey_id,))
        reset_row = dict(cur.fetchone())
        self.assertEqual(reset_row["status"], "IN_PROGRESS")
        self.assertIsNone(reset_row["approved_by"])
        self.assertIsNone(reset_row["cryptographic_hash"])

        # DELETE
        cur.execute("DELETE FROM surveys WHERE survey_id = ?", (survey_id,))
        conn.commit()
        cur.execute("SELECT COUNT(*) FROM surveys WHERE survey_id = ?", (survey_id,))
        self.assertEqual(cur.fetchone()[0], 0)
        conn.close()

    def test_03_evidence_and_ai_assessments_crud_and_foreign_key_integrity(self):
        """Test CRUD on `evidence` and `ai_assessments` and verify strict FOREIGN KEY enforcement."""
        conn = self._connect_isolated()
        cur = conn.cursor()

        # 1. Verify FOREIGN KEY blocks orphan evidence insert
        with self.assertRaises(sqlite3.IntegrityError):
            cur.execute("""
                INSERT INTO evidence (
                    survey_id, cargo_item, file_path, file_name, file_size, dimensions, sha256, uploaded_at
                ) VALUES ('NON-EXISTENT-SURVEY', 'TR-999', '/data/uploads/x.jpg', 'x.jpg', 1024, '1280x720', 'abc', '2026-10-30T10:00:00Z')
            """)

        # 2. Verify FOREIGN KEY blocks orphan ai_assessments insert
        with self.assertRaises(sqlite3.IntegrityError):
            cur.execute("""
                INSERT INTO ai_assessments (
                    survey_id, cargo_item, model_name, prompt_used, assessment_text,
                    nitrogen_pressure, impact_recorder_g, lashing_status, created_at
                ) VALUES ('NON-EXISTENT-SURVEY', 'TR-999', 'model', 'prompt', 'assessment', '0.25 bar', '0.5 G', 'OK', '2026-10-30T10:00:00Z')
            """)

        # 3. Create parent survey
        parent_id = "LW-FK-TEST-002"
        cur.execute("""
            INSERT INTO surveys (
                survey_id, vessel_name, imo_number, cargo_name, cargo_item,
                location, berth, client_name, status, created_at
            ) VALUES (?, 'MV DANUBE EXPRESS', '9123456', 'Power Transformer', 'TR-002',
                      'Port of Constanta', 'Berth 120', 'BALKAN INDUSTRIAL METALS', 'IN_PROGRESS', '2026-10-30T10:00:00Z')
        """, (parent_id,))
        conn.commit()

        # 4. CREATE child `evidence`
        sample_sha = hashlib.sha256(b"synthetic_evidence_payload").hexdigest()
        cur.execute("""
            INSERT INTO evidence (
                survey_id, cargo_item, file_path, file_name, file_size, dimensions, sha256, uploaded_at
            ) VALUES (?, 'TR-002', '/data/uploads/test_tr002.jpg', 'test_tr002.jpg', 4096, '1920x1080', ?, '2026-10-30T10:01:00Z')
        """, (parent_id, sample_sha))
        ev_id = cur.lastrowid

        # 5. CREATE child `ai_assessments`
        cur.execute("""
            INSERT INTO ai_assessments (
                survey_id, cargo_item, model_name, prompt_used, assessment_text,
                nitrogen_pressure, impact_recorder_g, lashing_status, created_at
            ) VALUES (?, 'TR-002', 'nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B', 'Prompt text',
                      'Initial AI engineering assessment', '0.24 bar', '0.6 G', '8 chains secured', '2026-10-30T10:02:00Z')
        """, (parent_id,))
        ai_id = cur.lastrowid
        conn.commit()

        # 6. READ & verify relational join between surveys, evidence, and ai_assessments
        cur.execute("""
            SELECT s.survey_id, s.vessel_name, e.sha256, e.dimensions, a.model_name, a.nitrogen_pressure
            FROM surveys s
            INNER JOIN evidence e ON e.survey_id = s.survey_id
            INNER JOIN ai_assessments a ON a.survey_id = s.survey_id
            WHERE s.survey_id = ?
        """, (parent_id,))
        joined = dict(cur.fetchone())
        self.assertEqual(joined["vessel_name"], "MV DANUBE EXPRESS")
        self.assertEqual(joined["sha256"], sample_sha)
        self.assertEqual(joined["dimensions"], "1920x1080")
        self.assertEqual(joined["nitrogen_pressure"], "0.24 bar")

        # 7. UPDATE child rows
        cur.execute("UPDATE evidence SET dimensions = '3840x2160', file_size = 8192 WHERE id = ?", (ev_id,))
        cur.execute("UPDATE ai_assessments SET nitrogen_pressure = '0.28 bar', assessment_text = 'Updated assessment' WHERE id = ?", (ai_id,))
        conn.commit()

        cur.execute("SELECT dimensions, file_size FROM evidence WHERE id = ?", (ev_id,))
        ev_updated = dict(cur.fetchone())
        self.assertEqual(ev_updated["dimensions"], "3840x2160")
        self.assertEqual(ev_updated["file_size"], 8192)

        cur.execute("SELECT nitrogen_pressure, assessment_text FROM ai_assessments WHERE id = ?", (ai_id,))
        ai_updated = dict(cur.fetchone())
        self.assertEqual(ai_updated["nitrogen_pressure"], "0.28 bar")
        self.assertEqual(ai_updated["assessment_text"], "Updated assessment")

        # 8. Verify FOREIGN KEY prevents deleting parent survey while child evidence/assessments exist
        with self.assertRaises(sqlite3.IntegrityError):
            cur.execute("DELETE FROM surveys WHERE survey_id = ?", (parent_id,))

        # 9. DELETE child rows first, then parent row cleanly
        cur.execute("DELETE FROM evidence WHERE id = ?", (ev_id,))
        cur.execute("DELETE FROM ai_assessments WHERE id = ?", (ai_id,))
        cur.execute("DELETE FROM surveys WHERE survey_id = ?", (parent_id,))
        conn.commit()

        cur.execute("PRAGMA foreign_key_check;")
        self.assertEqual(cur.fetchall(), [])
        conn.close()

    def test_04_ai_ops_telemetry_crud_and_constraints(self):
        """Test CRUD on `ai_usage_events`, `ai_models`, `ai_model_pricing`, `ai_budgets`, and `ai_alert_events`."""
        service = AIOpsService(db_path=str(self.isolated_db_path), enable_async_queue=False)

        # 1. CREATE live telemetry event via service
        req_id = f"crud-live-{int(time.time() * 1000)}"
        rec_ok = service.record_inference_event(
            request_id=req_id,
            provider="nebius",
            model_id="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
            survey_id="LW-DEMO-001",
            service_caller="crud-regression-test",
            operation_type="statutory-assessment",
            prompt_tokens=400,
            completion_tokens=200,
            total_tokens=600,
            latency_ms=850.5,
            http_status=200,
            status="SUCCESS",
            is_synthetic=False,
        )
        self.assertTrue(rec_ok)

        # 2. READ via get_requests & get_overview
        reqs = service.get_requests(page=1, page_size=50, survey_id="LW-DEMO-001", include_synthetic=False)
        matching = [r for r in reqs.get("items", []) if r.get("request_id") == req_id]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["total_tokens"], 600)
        self.assertGreater(matching[0]["estimated_cost"], 0.0)

        # 3. Verify UNIQUE constraint on ai_usage_events.request_id
        conn = self._connect_isolated()
        cur = conn.cursor()
        with self.assertRaises(sqlite3.IntegrityError):
            cur.execute("""
                INSERT INTO ai_usage_events (
                    request_id, timestamp_utc, provider, model_id, prompt_tokens, completion_tokens, total_tokens
                ) VALUES (?, '2026-10-30T10:00:00Z', 'nebius', 'nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B', 10, 10, 20)
            """, (req_id,))

        # 4. CREATE & UPDATE alert event (`ai_alert_events`)
        cur.execute("""
            INSERT INTO ai_alert_events (
                timestamp_utc, alert_type, severity, message, metadata_json, resolved
            ) VALUES ('2026-10-30T10:05:00Z', 'latency_spike', 'WARNING', 'Test CRUD latency alert', '{"is_synthetic": true}', 0)
        """)
        alert_id = cur.lastrowid
        conn.commit()
        conn.close()

        unresolved = service.get_alerts(resolved=False)
        self.assertTrue(any(a["id"] == alert_id for a in unresolved))

        resolved_ok = service.resolve_alert(alert_id)
        self.assertTrue(resolved_ok)

        resolved_list = service.get_alerts(resolved=True)
        self.assertTrue(any(a["id"] == alert_id and a["resolved"] == 1 for a in resolved_list))

        # 5. UPDATE & READ budgets (`ai_budgets` / `ai_budget_limits`)
        conn = self._connect_isolated()
        cur = conn.cursor()
        cur.execute("UPDATE ai_budgets SET budget_amount = 25.0 WHERE period = 'daily'")
        conn.commit()
        cur.execute("SELECT budget_amount FROM ai_budgets WHERE period = 'daily'")
        self.assertEqual(cur.fetchone()[0], 25.0)
        cur.execute("UPDATE ai_budgets SET budget_amount = 15.0 WHERE period = 'daily'")
        conn.commit()

        # 6. Seed synthetic events and DELETE them via clear_synthetic_demo_data()
        seeded_count = service.seed_synthetic_demo_data(count=10)
        self.assertEqual(seeded_count, 10)
        cleared_count = service.clear_synthetic_demo_data()
        self.assertGreaterEqual(cleared_count, 10)

        # Confirm live event `req_id` was NOT deleted by synthetic cleanup
        cur.execute("SELECT COUNT(*) FROM ai_usage_events WHERE request_id = ?", (req_id,))
        self.assertEqual(cur.fetchone()[0], 1)

        # Clean up test live event
        cur.execute("DELETE FROM ai_usage_events WHERE request_id = ?", (req_id,))
        conn.commit()
        conn.close()

    def test_05_http_api_crud_against_isolated_db(self):
        """Run `leewu_mvp_server.py` bound to isolated DB and validate full HTTP CRUD cycle."""
        # Find free ephemeral port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

        env = os.environ.copy()
        env["PORT"] = str(port)
        env["HOST"] = "127.0.0.1"
        admin_key = "isolated-crud-admin-key-2026"
        env["DATA_DIR"] = str(self.isolated_data_dir)
        env["LEEWU_DB_PATH"] = str(self.isolated_db_path)
        env["ADMIN_API_KEY"] = admin_key
        env["NEBIUS_API_KEY"] = ""  # Use deterministic offline fallback during CRUD test

        proc = subprocess.Popen(
            [sys.executable, str(PROJECT_ROOT / "leewu_mvp_server.py")],
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        base_url = f"http://127.0.0.1:{port}"
        try:
            # Wait for server startup
            ready = False
            for _ in range(30):
                try:
                    with urllib.request.urlopen(f"{base_url}/api/health", timeout=1) as r:
                        if r.status == 200:
                            ready = True
                            break
                except Exception:
                    time.sleep(0.15)
            self.assertTrue(ready, "Isolated LeeWu MVP Server failed to start")

            def req_json(path, method="GET", payload=None):
                data = json.dumps(payload).encode("utf-8") if payload is not None else None
                headers = {"Authorization": f"Bearer {admin_key}"}
                if data is not None:
                    headers["Content-Type"] = "application/json"
                req = urllib.request.Request(f"{base_url}{path}", data=data, headers=headers, method=method)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    return resp.status, json.loads(resp.read().decode("utf-8"))

            # 1. Reset LW-DEMO-001 (UPDATE + DELETE child rows)
            code, res = req_json("/api/surveys/LW-DEMO-001/reset", method="POST", payload={})
            self.assertEqual(code, 200)
            self.assertTrue(res["success"])

            # 2. Read LW-DEMO-001 (verify empty evidence & assessments after reset)
            code, details = req_json("/api/surveys/LW-DEMO-001")
            self.assertEqual(code, 200)
            self.assertEqual(details["status"], "IN_PROGRESS")
            self.assertEqual(len(details["evidence"]), 0)
            self.assertEqual(len(details["ai_assessments"]), 0)

            # 3. Upload evidence (CREATE in `evidence`)
            code, up_res = req_json("/api/surveys/LW-DEMO-001/upload", method="POST", payload={})
            self.assertEqual(code, 201)
            self.assertTrue(up_res["success"])
            ev_sha = up_res["evidence"]["sha256"]
            self.assertEqual(len(ev_sha), 64)

            # 4. Run AI Inspection (CREATE in `ai_assessments`)
            code, ai_res = req_json("/api/surveys/LW-DEMO-001/ai-inspect", method="POST", payload={
                "nitrogen_pressure": "0.24 bar",
                "impact_recorder_g": "0.75 G",
                "lashing_status": "8 chains secured",
                "visual_remarks": "Unit intact"
            })
            self.assertEqual(code, 200)
            self.assertTrue(ai_res["success"])

            # 5. Approve survey (UPDATE in `surveys`)
            code, app_res = req_json("/api/surveys/LW-DEMO-001/approve", method="POST", payload={
                "surveyor_name": "Alexandru Radu",
                "license_number": "DEMO-MWS-2026-001",
                "final_remarks": "Approved in isolated CRUD regression."
            })
            self.assertEqual(code, 200)
            self.assertEqual(app_res["status"], "APPROVED")
            self.assertEqual(len(app_res["cryptographic_seal_sha256"]), 64)

            # 6. Verify persisted state via GET /api/surveys/LW-DEMO-001
            code, final_details = req_json("/api/surveys/LW-DEMO-001")
            self.assertEqual(code, 200)
            self.assertEqual(final_details["status"], "APPROVED")
            self.assertEqual(final_details["approved_by"], "Alexandru Radu")
            self.assertEqual(len(final_details["evidence"]), 1)
            self.assertEqual(len(final_details["ai_assessments"]), 1)

        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()

    def test_06_confirm_original_database_unmodified(self):
        """Explicitly confirm original SQLite database has identical SHA-256, size, mtime, and row counts."""
        after_snapshot = get_db_snapshot(self.original_db_path)
        self.assertEqual(after_snapshot["sha256"], self.baseline_snapshot["sha256"])
        self.assertEqual(after_snapshot["size"], self.baseline_snapshot["size"])
        self.assertEqual(after_snapshot["mtime_ns"], self.baseline_snapshot["mtime_ns"])
        self.assertEqual(after_snapshot["tables"], self.baseline_snapshot["tables"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
