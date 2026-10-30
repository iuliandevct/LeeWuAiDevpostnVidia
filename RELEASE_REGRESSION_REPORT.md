# LeeWu AI — Release Regression Report (Phase 3)

**Date**: 2026-10-30  
**Branch**: `release/security-hardening`  
**Database Mode**: Isolated temporary SQLite copies (`tempfile.mkdtemp`) + Mocked Nebius HTTP server (`0` paid API credits consumed).  
**Phase Status**: **PASS (96/96 tests executed, 95 passed, 1 live-network check skipped by design, 0 failures, 0 errors)**

---

## 1. Command Executed

```powershell
C:\Users\PC\.local\bin\python3.11.exe -m unittest discover -s "C:\Users\PC\Documents\ProiecteAutomatizareSincron\proiecte\LeeWuAiDevpostnVidia\tests" -p "test_*.py" -v
```

---

## 2. Subsystem Verification Matrix

| Subsystem Requirement | Test Suite / Method | Result | Evidence |
| :--- | :--- | :---: | :--- |
| **API Startup & Health** | `test_crud_regression_isolated.py`, `test_complete_demo_validation.py` | **PASS** | Ephemeral local server starts cleanly and returns `200 OK` on `/api/health`. |
| **SQLite Integrity (`PRAGMA integrity_check`)** | `test_01_isolated_copy_fidelity_and_pragma_integrity` | **PASS** | Returns `"ok"` with `0` page errors. |
| **Foreign Key Integrity (`PRAGMA foreign_key_check`)** | `test_03_evidence_and_ai_assessments_crud_and_foreign_key_integrity` | **PASS** | Orphan inserts into `evidence` and `ai_assessments` raise `sqlite3.IntegrityError`; parent delete blocked while children exist. |
| **Survey CRUD Lifecycle** | `test_02_surveys_table_crud_lifecycle` | **PASS** | Verified `INSERT`, `SELECT`, `UPDATE` (approve/reset), and `DELETE` on `surveys`. |
| **Evidence & Photo Association** | `test_03_upload_photos_and_evidence` | **PASS** | `POST /api/surveys/LW-DEMO-001/upload` (with Bearer auth) hashes `TR-001` photo (`sha256: cbfd090e...`) and links to `LW-DEMO-001`. |
| **AI Inspection (Mocked Nebius)** | `test_04_ai_analysis_via_nebius`, `test_08_valid_bearer_token...` | **PASS** | `POST /api/surveys/LW-DEMO-001/ai-inspect` stores structured MWS assessment in `ai_assessments`. |
| **Survey Approval & SHA-256 Seal** | `test_05_verification_and_approval` | **PASS** | `POST /api/surveys/LW-DEMO-001/approve` transitions status to `APPROVED` and computes deterministic SHA-256 seal. |
| **Statutory Report Export** | `test_06_report_generation_and_export` | **PASS** | `GET /api/surveys/LW-DEMO-001/export` renders HTML report with `OBSERVED & MEASURED`, `AI_INFERRED`, `HUMAN_APPROVED`, and XSS escaping. |
| **Telegram Bot Security & History** | `test_telegram_auth_hardening.py` (12 tests), `test_telegram_security.py` (6 tests) | **PASS** | Numeric ID allowlist fail-closed, username spoofing blocked, 100-msg per-chat isolated history verified. |
| **Nebius Provider & Extraction (Mocked)** | `test_nebius_provider.py` (16 tests), `test_nebius_integration.py` (6 tests), `test_transformer_extraction.py` (1 test) | **PASS** | Retries, timeout handling, key masking, and JSON extraction verified without consuming paid credits. |
| **Original Database Preservation** | `test_06_confirm_original_database_unmodified`, `test_10_original_sqlite_database_unchanged` | **PASS** | `data/leewu_mvp.db` remains at `sha256: 3ffd6c05de47923d4d2db094877ae8c543e94ec1a415fb079a2d2724bea6e345` (`282624` bytes). |
