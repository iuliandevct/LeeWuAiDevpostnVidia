# LeeWu AI — Release Baseline (Phase 0)

**Date**: 2026-10-30  
**Repository**: `iuliandevct/LeeWuAiDevpostnVidia`  
**Release Branch**: `release/security-hardening` (branched from `main` @ `440ceef` / `feb0c31`)  
**Phase Status**: **PASS**

---

## 1. Git Status, Branches & Remotes

- **Working Tree**: Clean (`0` untracked secrets, `.env` and `data/*.db` properly ignored in `.gitignore`).
- **Active Branches**:
  - `main` (`440ceef` — `security(release): enforce authentication on all write endpoints`)
  - `release/security-hardening` (Release Candidate v1.0.0-rc1 hardening branch)
- **Configured Remotes**:
  - `origin`: `https://github.com/iuliandevct/LeeWuAiDevpostnVidia.git`

---

## 2. Original SQLite Database Baseline & Integrity

- **Database Path**: `data/leewu_mvp.db`
- **Byte Size**: `282624` bytes (`282,624` bytes)
- **SHA-256 Checksum**: `3ffd6c05de47923d4d2db094877ae8c543e94ec1a415fb079a2d2724bea6e345`
- **`PRAGMA integrity_check`**: `ok`
- **`PRAGMA foreign_key_check`**: `[]` (`0` violations)
- **Baseline Table Row Counts**:
  - `surveys`: `1` (`LW-DEMO-001` synthetic survey)
  - `evidence`: `1`
  - `ai_assessments`: `1`
  - `ai_models`: `8`
  - `ai_model_pricing`: `151`
  - `ai_budgets`: `2`
  - `ai_budget_limits`: `2`
  - `ai_usage_events`: `114`
  - `ai_alert_events`: `61`

---

## 3. Application Entry Points & Write Endpoints Inventory

### 3.1 Process Entry Points
1. **`leewu_mvp_server.py`**: Zero-dependency Python HTTP/REST backend server (default bind `127.0.0.1:8080`).
2. **`telegram_bot_daemon.py`**: Persistent Telegram field surveyor bot (`@Leewubot`) with numeric allowlist authorization.
3. **`scripts/nebius_provider.py`**: OpenAI-compatible Nebius Token Factory client (`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` / `nvidia/Nemotron-3-Ultra-550b-a55b`).
4. **`scripts/ai_ops_service.py` / `ai_ops_service.py`**: FinOps & token telemetry observability service.

### 3.2 HTTP Read Endpoints (Public / Read-Only Demo vs. Protected Admin GET)
| Method | Route | Access Level | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/health` | Public Read-Only | Service health & AI configuration validity (redacted). |
| `GET` | `/api/surveys` | Public Read-Only | Lists synthetic survey metadata (`LW-DEMO-001`). |
| `GET` | `/api/surveys/LW-DEMO-001` | Public Read-Only | Returns `LW-DEMO-001` details, attached evidence, and AI notes. |
| `GET` | `/api/surveys/LW-DEMO-001/export` | Public Read-Only | Renders printable A4 statutory HTML certificate with SHA-256 seal. |
| `GET` | `/api/ai-ops/overview` | **Protected (`Bearer ADMIN_API_KEY`)** | FinOps token & budget summary. |
| `GET` | `/api/ai-ops/usage` | **Protected (`Bearer ADMIN_API_KEY`)** | Daily/hourly token usage timeline. |
| `GET` | `/api/ai-ops/models` | **Protected (`Bearer ADMIN_API_KEY`)** | Model catalog and pricing rates. |
| `GET` | `/api/ai-ops/costs` | **Protected (`Bearer ADMIN_API_KEY`)** | Cost breakdown by model and survey. |
| `GET` | `/api/ai-ops/health` | **Protected (`Bearer ADMIN_API_KEY`)** | Telemetry subsystem health check. |
| `GET` | `/api/ai-ops/alerts` | **Protected (`Bearer ADMIN_API_KEY`)** | Active/resolved budget and latency alerts. |
| `GET` | `/api/ai-ops/requests` | **Protected (`Bearer ADMIN_API_KEY`)** | Paginated inference event log. |
| `GET` | `/api/ai-ops/export` | **Protected (`Bearer ADMIN_API_KEY`)** | CSV/JSON telemetry export. |

### 3.3 HTTP Write Endpoints (All Strictly Protected by `check_admin_auth()`)
| Method | Route | Protection | Side Effects |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/surveys/LW-DEMO-001/upload` | **Protected (`Bearer ADMIN_API_KEY`)** | Hashes & stores evidence photo in `data/uploads/` and inserts into `evidence`. |
| `POST` | `/api/surveys/LW-DEMO-001/ai-inspect` | **Protected (`Bearer ADMIN_API_KEY`)** | Invokes Nebius AI model and inserts assessment into `ai_assessments`. |
| `POST` | `/api/surveys/LW-DEMO-001/approve` | **Protected (`Bearer ADMIN_API_KEY`)** | Marks survey `APPROVED` and computes SHA-256 seal in `surveys`. |
| `POST` | `/api/surveys/LW-DEMO-001/reset` | **Protected (`Bearer ADMIN_API_KEY`)** | Resets `LW-DEMO-001` to draft state (`IN_PROGRESS`). |
| `POST` | `/api/ai-ops/seed-demo` | **Protected (`Bearer ADMIN_API_KEY`)** | Seeds synthetic telemetry rows (`is_synthetic=1`). |
| `POST` | `/api/ai-ops/clear-demo` | **Protected (`Bearer ADMIN_API_KEY`)** | Deletes synthetic telemetry rows (`is_synthetic=1`). |
| `POST` | `/api/ai-ops/alerts/resolve` | **Protected (`Bearer ADMIN_API_KEY`)** | Marks an alert ID resolved in `ai_alert_events`. |
