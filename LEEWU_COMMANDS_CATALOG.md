# LeeWu AI — Master Commands, API Endpoints & AI Capabilities Catalog (`LEEWU_COMMANDS_CATALOG.md`)

> **Audit Scope & Methodology**: This catalog reflects the exact code-level inspection of the active **LeeWu AI** codebase (`telegram_bot_daemon.py`, `leewu_mvp_server.py`, `scripts/nebius_provider.py`, `scripts/ai_ops_service.py`, `node-red/flows.json`, `ai-containers-stack/graph-api/server.py`, and `docs/*.md`). Every command, natural-language query, and REST endpoint is categorized strictly as **`IMPLEMENTED`**, **`PARTIAL`**, or **`NOT IMPLEMENTED`**, with explicit authorization levels and concrete invocations.

---

## 1. Master Command & Capability Matrix

### Legend — Status & Permission Levels
- **Status**:
  - `IMPLEMENTED`: Fully wired in code, executes deterministically or via live Nebius Token Factory inference, and persists/reads real state.
  - `PARTIAL`: Implemented with static/preset data, scoped to the synthetic demo survey (`LW-DEMO-001`), or answered conversationally by the LLM without mutating the database.
  - `NOT IMPLEMENTED`: Documented in architectural guides (`README.md`, `docs/help3.md`, `docs/help4.md`) or proposed as user examples, but no code handler or endpoint is wired to execute the action.
- **Permission Levels**:
  - **Public Demo (Read-Only)**: Accessible without credentials on `http://127.0.0.1:8080`. Never triggers paid Nebius inference or mutates SQLite state.
  - **Telegram Allowlist (`TELEGRAM_ALLOWED_USERS` / `TELEGRAM_CHAT_ID`)**: Requires the sender's numeric Telegram User ID or Chat ID to match the server allowlist (fail-closed; usernames rejected).
  - **Admin / Authenticated Write (`Authorization: Bearer <ADMIN_API_KEY>`)**: Validated via constant-time `secrets.compare_digest` in `check_admin_auth()`. Rejects loopback bypasses (`127.0.0.1`), proxy headers (`X-Forwarded-For`), and URL query-string credentials.

### Complete Summary Table

| # | Channel | Command / Endpoint / Natural Prompt | Handler / Source File | Permission Required | Status | Description & Actual Behavior |
| :- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | Telegram | `/start`, `/help`, `/ajutor` | `telegram_bot_daemon.py` | Telegram Numeric Allowlist | **IMPLEMENTED** | Displays the interactive field surveyor command menu and records the event in `telegram_chat_history.json`. |
| **2** | Telegram | `/status`, `/inspectie` | `telegram_bot_daemon.py` (`build_live_status_html`) | Telegram Numeric Allowlist | **IMPLEMENTED** | Queries `data/leewu_mvp.db` (immutable read-only) for `LW-DEMO-001` status/evidence/seal and `survey_remarks.json` for `MV WAN FU` (Dana 52) discharge progress. |
| **3** | Telegram | `/remark <text>` | `telegram_bot_daemon.py` (`handle_remark`) | Telegram Numeric Allowlist | **IMPLEMENTED** | Parses hold number (`Hold 1`–`Hold 5`), generates `REM-xxx`, writes a critical damage entry to `data/survey_remarks.json`, and returns Hague-Visby Art. III r.2 confirmation. |
| **4** | Telegram | `/avarii`, `/remarks` | `telegram_bot_daemon.py` | Telegram Numeric Allowlist | **IMPLEMENTED** | Reads and lists up to 8 recorded cargo damage remarks from `data/survey_remarks.json`. |
| **5** | Telegram | `/raport` | `telegram_bot_daemon.py` | Telegram Numeric Allowlist | **IMPLEMENTED** | Displays the statutory MWS summary for `LW-DEMO-001` (`TR-001` 110kV Transformer, N2 `0.24 bar`, `0.75 G`, Clean Mate's Receipt). |
| **6** | Telegram | `/pontaj` | `telegram_bot_daemon.py` | Telegram Numeric Allowlist | **PARTIAL** | Displays the EXIF-reconstructed surveyor timesheet (`08:14:22`–`17:08:45`, `8.15h` net billable = `1,507.75 RON`). Uses preset shift figures from `MV WAN FU`. |
| **7** | Telegram | `/foaie` | `telegram_bot_daemon.py` | Telegram Numeric Allowlist | **PARTIAL** | Displays vehicle logbook sheet `LPM-FP-6258` for `CT-88-LPM` (`48 km`, `3.45 L` Diesel, `0.89 RON/km`). Uses preset route telemetry. |
| **8** | Telegram | `/acte` | `telegram_bot_daemon.py` | Telegram Numeric Allowlist | **PARTIAL** | Displays fleet document expiry alerts for `CT-88-LPM` (ITP 18 days) and `CT-22-LPM` (Rovinietă 7 days). |
| **9** | Telegram | `/nava` | `telegram_bot_daemon.py` | Telegram Numeric Allowlist | **PARTIAL** | Displays discharge progress for `MV WAN FU` (IMO `9482184`, Berth 52, `4,820 / 15,420 MT`, `31.2%`). |
| **10** | Telegram | `/juridic` | `telegram_bot_daemon.py` | Telegram Numeric Allowlist | **PARTIAL** | Displays statutory legal compliance block (Law 51/1995 Bar Gate, Hague-Visby 1968, Gard P&I Club, 10% discount). |
| **11** | Telegram | `/istoric`, `/history` | `telegram_bot_daemon.py` (`get_recent_context`) | Telegram Numeric Allowlist | **IMPLEMENTED** | Displays the last 6 messages from the caller's isolated conversation history in `data/telegram_chat_history.json`. |
| **12** | Telegram | `/reset`, `/clear` | `telegram_bot_daemon.py` (`clear_chat_history`) | Telegram Numeric Allowlist | **IMPLEMENTED** | Atomically clears the caller's chat history in `data/telegram_chat_history.json`. |
| **13** | Telegram | `[Photo Upload]` | `telegram_bot_daemon.py` | Telegram Numeric Allowlist | **PARTIAL** | Acknowledges photo upload with timestamp and logs `[Foto încărcată la HH:MM:SS]` in chat history, but does not download the binary image from Telegram or run Vision AI. |
| **14** | Telegram | Free-text message (RO/EN) | `telegram_bot_daemon.py` (`query_nemotron_with_history`) | Telegram Numeric Allowlist | **IMPLEMENTED** | Calls `nvidia/Nemotron-3-Ultra-550b-a55b` (fallback `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`) via Nebius Token Factory with live SQLite + `survey_remarks.json` + 8-turn memory. |
| **15** | Prompt (EN/RO) | *"Show active surveys"* | `telegram_bot_daemon.py` / `GET /api/surveys` | Telegram Allowlist / Public Demo | **IMPLEMENTED** | In Telegram, Nemotron lists active inspections (`LW-DEMO-001` at Berth 120 & `MV WAN FU` at Berth 52) from live context; via API, `GET /api/surveys` returns SQLite rows. |
| **16** | Prompt (EN/RO) | *"Show survey LW-DEMO-001"* | `telegram_bot_daemon.py` / `GET /api/surveys/LW-DEMO-001` | Telegram Allowlist / Public Demo | **IMPLEMENTED** | In Telegram, `/status`, `/raport`, or natural text returns full `LW-DEMO-001` telemetry; via API, returns survey + `evidence` + `ai_assessments`. |
| **17** | Prompt (EN/RO) | *"Summarize survey operations"* | `telegram_bot_daemon.py` | Telegram Numeric Allowlist | **IMPLEMENTED** | Grounded in `get_live_operational_context()`, Nemotron summarizes Berth 120 (`TR-001`), Berth 52 (`MV WAN FU`), damage remarks, EXIF timesheet, and fleet alerts. |
| **18** | Prompt (EN/RO) | *"Generate survey report"* | `telegram_bot_daemon.py` / `GET /api/surveys/LW-DEMO-001/export` | Telegram Allowlist / Public Demo | **PARTIAL** | In Telegram, `/raport` or natural prompt drafts a text summary; via API (`GET /api/surveys/LW-DEMO-001/export`), generates the printable HTML/A4 certificate. Not yet wired to send a PDF file directly in Telegram. |
| **19** | Prompt (EN/RO) | *"Create new survey"* | None (`init_db` only seeds `LW-DEMO-001`) | Admin Bearer Token | **NOT IMPLEMENTED** | No `POST /api/surveys` endpoint or Telegram `/newsurvey` handler exists to create arbitrary new survey IDs in SQLite; the LLM will only answer conversationally. |
| **20** | Prompt (EN/RO) | *"Analyze these cargo photos"* | None (Vision model not wired in daemon/API) | Admin Bearer Token | **NOT IMPLEMENTED** | `POST /api/surveys/LW-DEMO-001/ai-inspect` evaluates text telemetry parameters (`nitrogen_pressure`, `impact_recorder_g`, `lashing_status`, `visual_remarks`), not raw image pixels. |
| **21** | Prompt (EN/RO) | *"Check missing documents"* | `telegram_bot_daemon.py` (`/acte`) | Telegram Numeric Allowlist | **PARTIAL** | Checks expiring/missing vehicle fleet documents (`ITP`, `RCA`, `Rovinietă`), but does not check missing shipping documents (`Bill of Lading`, `Packing List`, `Mate's Receipt`) per survey. |
| **22** | HTTP API (`:8080`) | `GET /api/health` | `leewu_mvp_server.py` | Public Demo (Read-Only) | **IMPLEMENTED** | Returns service health, version, Nebius provider configuration status, default model, and SQLite connectivity. |
| **23** | HTTP API (`:8080`) | `GET /api/surveys` | `leewu_mvp_server.py` | Public Demo (Read-Only) | **IMPLEMENTED** | Lists all records from the SQLite `surveys` table. |
| **24** | HTTP API (`:8080`) | `GET /api/surveys/LW-DEMO-001` | `leewu_mvp_server.py` (`send_survey_details`) | Public Demo (Read-Only) | **IMPLEMENTED** | Returns full survey record for `LW-DEMO-001` including attached `evidence` and `ai_assessments` arrays. |
| **25** | HTTP API (`:8080`) | `GET /api/surveys/LW-DEMO-001/export` | `leewu_mvp_server.py` (`render_statutory_export`) | Public Demo (Read-Only) | **IMPLEMENTED** | Renders the complete printable A4 HTML Statutory Survey Certificate with XSS-escaped fields, photo checksums, AI assessment, and SHA-256 seal. |
| **26** | HTTP API (`:8080`) | `POST /api/surveys/LW-DEMO-001/upload` | `leewu_mvp_server.py` (`handle_upload`) | Admin (`Bearer <ADMIN_API_KEY>`) | **IMPLEMENTED** | Accepts `image_base64` (or copies default HD transformer photo), computes SHA-256 checksum, stores file in `data/uploads/`, and inserts an `evidence` row. |
| **27** | HTTP API (`:8080`) | `POST /api/surveys/LW-DEMO-001/ai-inspect` | `leewu_mvp_server.py` (`handle_ai_inspect`) | Admin (`Bearer <ADMIN_API_KEY>`) | **IMPLEMENTED** | Calls Nebius Token Factory (`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` with deterministic fallback), logs telemetry in `ai_ops_service`, and saves row in `ai_assessments`. |
| **28** | HTTP API (`:8080`) | `POST /api/surveys/LW-DEMO-001/approve` | `leewu_mvp_server.py` (`handle_approve`) | Admin (`Bearer <ADMIN_API_KEY>`) | **IMPLEMENTED** | Marks `LW-DEMO-001` as `APPROVED`, records `approved_by` and `surveyor_license`, and computes the SHA-256 statutory seal. |
| **29** | HTTP API (`:8080`) | `POST /api/surveys/LW-DEMO-001/reset` | `leewu_mvp_server.py` (`handle_reset`) | Admin (`Bearer <ADMIN_API_KEY>`) | **IMPLEMENTED** | Deletes attached `evidence` and `ai_assessments` for `LW-DEMO-001` and resets status to `IN_PROGRESS`. |
| **30** | HTTP API (`:8080`) | `GET /api/ai-ops/overview` | `leewu_mvp_server.py` + `ai_ops_service.py` | Admin (`Bearer <ADMIN_API_KEY>`) | **IMPLEMENTED** | Returns aggregated AI token usage, latency, error rate, and cost metrics (`currency=EUR|USD|RON`, `include_synthetic=true|false`). |
| **31** | HTTP API (`:8080`) | `GET /api/ai-ops/usage` | `leewu_mvp_server.py` + `ai_ops_service.py` | Admin (`Bearer <ADMIN_API_KEY>`) | **IMPLEMENTED** | Returns daily/hourly token and request timeline (`period=daily|hourly`, `limit=14`). |
| **32** | HTTP API (`:8080`) | `GET /api/ai-ops/models` | `leewu_mvp_server.py` + `ai_ops_service.py` | Admin (`Bearer <ADMIN_API_KEY>`) | **IMPLEMENTED** | Lists configured AI models, token pricing rates, and per-model invocation counts. |
| **33** | HTTP API (`:8080`) | `GET /api/ai-ops/costs` | `leewu_mvp_server.py` + `ai_ops_service.py` | Admin (`Bearer <ADMIN_API_KEY>`) | **IMPLEMENTED** | Returns cost breakdown by model, operation type, and survey ID. |
| **34** | HTTP API (`:8080`) | `GET /api/ai-ops/health` | `leewu_mvp_server.py` + `ai_ops_service.py` | Admin (`Bearer <ADMIN_API_KEY>`) | **IMPLEMENTED** | Returns AI Observatory telemetry database health and provider status. |
| **35** | HTTP API (`:8080`) | `GET /api/ai-ops/alerts` | `leewu_mvp_server.py` + `ai_ops_service.py` | Admin (`Bearer <ADMIN_API_KEY>`) | **IMPLEMENTED** | Lists active or resolved cost/latency/error alerts (`resolved=true|false`). |
| **36** | HTTP API (`:8080`) | `GET /api/ai-ops/requests` | `leewu_mvp_server.py` + `ai_ops_service.py` | Admin (`Bearer <ADMIN_API_KEY>`) | **IMPLEMENTED** | Paginated audit log of LLM API calls (`page`, `page_size`, `model`, `survey_id`, `status`). |
| **37** | HTTP API (`:8080`) | `GET /api/ai-ops/export` | `leewu_mvp_server.py` + `ai_ops_service.py` | Admin (`Bearer <ADMIN_API_KEY>`) | **IMPLEMENTED** | Downloads AI Ops telemetry ledger as attachment (`format=csv|json`). |
| **38** | HTTP API (`:8080`) | `POST /api/ai-ops/seed-demo` | `leewu_mvp_server.py` + `ai_ops_service.py` | Admin (`Bearer <ADMIN_API_KEY>`) | **IMPLEMENTED** | Seeds synthetic AI telemetry events (`count=42`) into SQLite for dashboard evaluation. |
| **39** | HTTP API (`:8080`) | `POST /api/ai-ops/clear-demo` | `leewu_mvp_server.py` + `ai_ops_service.py` | Admin (`Bearer <ADMIN_API_KEY>`) | **IMPLEMENTED** | Removes synthetic demonstration telemetry rows from SQLite. |
| **40** | HTTP API (`:8080`) | `POST /api/ai-ops/alerts/resolve` | `leewu_mvp_server.py` + `ai_ops_service.py` | Admin (`Bearer <ADMIN_API_KEY>`) | **IMPLEMENTED** | Marks a specific AI Ops alert (`alert_id`) as resolved. |
| **41** | Node-RED (`:1880`) | `POST /api/telegram-notify` | `node-red/flows.json` | Local Microservice (Optional) | **PARTIAL** | Dispatches a Telegram message (or returns simulated receipt if Node-RED is in demo mode). Note: Node-RED `:1880` is an optional companion flow, not running by default. |
| **42** | Node-RED (`:1880`) | `POST /api/rag/search` | `node-red/flows.json` | Local Microservice (Optional) | **PARTIAL** | Searches a 6-chunk in-memory maritime/legal corpus (`MV WAN FU`, `Hague-Visby`, `Law 51/1995`, `Berth 120 SOP`, `Gard P&I`) using keyword + simulated cosine scoring. |
| **43** | Node-RED (`:1880`) | `GET /api/kanban/cards`, `POST /api/kanban/card`, `PATCH /api/kanban/card/:id/stage` | `node-red/flows.json` | Local Microservice (Optional) | **PARTIAL** | Reads/writes `data/kanban_cards.json` for the Mission Console Kanban board when Node-RED is active. |
| **44** | Node-RED (`:1880`) | `GET /api/telegram/remarks`, `POST /api/telegram/remark` | `node-red/flows.json` | Local Microservice (Optional) | **PARTIAL** | Reads/appends `data/survey_remarks.json` via HTTP when Node-RED is active. |
| **45** | Node-RED (`:1880`) | `GET /api/fleet/reminders`, `POST /api/fleet/trip`, `POST /api/survey/process-photos` | `node-red/flows.json` | Local Microservice (Optional) | **PARTIAL** | Returns fleet reminders, calculates logbook cost/km (`0.89 RON/km`), and returns the 6-photo EXIF timeline for `MV WAN FU`. |

---

## 2. Detailed Inspection by Subsystem

### 2.1 Telegram Bot (`@Leewubot` — `telegram_bot_daemon.py`)

#### Architecture & Security Gate
- **Transport**: Native Python HTTP long-polling (`GET /getUpdates?timeout=10`) with zero external third-party bot framework dependencies.
- **Mandatory Authorization Gate (`is_authorized`)**: Executed **before** any command, photo, callback query, or natural-language prompt is processed:
  - Reads `TELEGRAM_CHAT_ID` and `TELEGRAM_ALLOWED_USERS` from `.env`.
  - Accepts **only numeric IDs** (e.g., `8143220589`). Usernames (`@user`) or alphabetic strings invalidate the entire allowlist (fail-closed).
  - Unauthorized users receive `⛔ Acces Neautorizat` and their message is dropped before reaching any command handler or Nebius API call.
- **Callback Queries (`callback_query`)**:
  - `answer_callback_query()` is implemented and protected by `is_authorized()`, returning an alert if unauthorized. No inline keyboard buttons (`reply_markup`) are currently emitted by the bot commands, so authorized callback queries simply `continue`.

#### Registered Slash Commands (Exact Match on Lowercase Prefix)
1. **`/start`**, **`/help`**, **`/ajutor`**
   - **Parameters**: None.
   - **Action**: Sends the HTML command menu listing `/remark`, `/pontaj`, `/foaie`, `/acte`, `/status`, `/avarii`, `/raport`, `/nava`, `/juridic`, `/istoric`, `/reset`.
2. **`/status`**, **`/inspectie`**
   - **Parameters**: None.
   - **Action**: Calls `build_live_status_html()`. Opens `data/leewu_mvp.db` in immutable read-only mode (`?mode=ro&immutable=1`), reads `status`, `approved_by`, `cryptographic_hash`, and `COUNT(*)` of `evidence` for `LW-DEMO-001`, counts remarks in `data/survey_remarks.json`, and returns a combined live dashboard for Berth 120 (`TR-001`) and Berth 52 (`MV WAN FU`).
3. **`/remark <descriere>`**
   - **Parameters**: Free text describing hold, item, and defect (up to 500 chars).
   - **Action**: Calls `handle_remark()`. Automatically extracts `hold_no` (`Hold 1`–`Hold 5`, defaults to `3`), generates `REM-<3_digits>`, writes the entry to `data/survey_remarks.json` with severity `CRITIC` and legal basis `Hague-Visby Art. III r.2`, and confirms on Telegram.
4. **`/avarii`**, **`/remarks`**
   - **Parameters**: None.
   - **Action**: Reads `data/survey_remarks.json` and formats the latest 8 damage entries (`ID`, `Magazia`, `Descriere`, `Timestamp`).
5. **`/raport`**
   - **Parameters**: None.
   - **Action**: Sends the structured statutory MWS certificate summary for `LW-DEMO-001` (`TR-001`, `MV DEMO CARRIER`, `0.24 bar` N2, `0.75 G` longitudinal / `0.35 G` transverse, 8 Grade 80 chains, `UNCONDITIONAL CLEAN MATE'S RECEIPT`).
6. **`/pontaj`**
   - **Parameters**: None.
   - **Action**: Returns the EXIF-reconstructed shift breakdown for `Alexandru Radu` (`08:14:22`–`17:08:45`, `8.90h` gross, `-0.75h` rain stoppage, `8.15h` net billable @ `185 RON/h` = `1,507.75 RON`).
7. **`/foaie`**
   - **Parameters**: None.
   - **Action**: Returns logbook sheet `LPM-FP-6258` for `Dacia Duster 4x4 (CT-88-LPM)` (`142,310` -> `142,358` = `48 km`, `3.45 L` Diesel, `0.89 RON/km`).
8. **`/acte`**
   - **Parameters**: None.
   - **Action**: Returns expiry countdowns for `CT-88-LPM` (`ITP` expires in 18 days on `17.11.2026`) and `CT-22-LPM` (`Rovinietă` expires in 7 days on `06.11.2026`).
9. **`/nava`**
   - **Parameters**: None.
   - **Action**: Returns vessel discharge telemetry for `MV WAN FU (IMO 9482184)` at Berth 52 (`15,420 MT` steel coils, `4,820 MT` discharged = `31.2%`, Cranes 2 & 3 active, wind `12 kt ESE`).
10. **`/juridic`**
    - **Parameters**: None.
    - **Action**: Returns Law 51/1995 Bar Attorney gate status, Hague-Visby 1968 applicability, Gard P&I Club Norway reference, and 10% statutory discount.
11. **`/istoric`**, **`/history`**
    - **Parameters**: None.
    - **Action**: Reads `data/telegram_chat_history.json` for the current `chat_id` and displays the last 6 messages.
12. **`/reset`**, **`/clear`**
    - **Parameters**: None.
    - **Action**: Wipes the message array for the current `chat_id` in `data/telegram_chat_history.json`.

---

### 2.2 Local REST API (`http://127.0.0.1:8080` — `leewu_mvp_server.py`)

#### Public Read-Only Endpoints (No Token Required)
- `GET /api/health`
  - Returns JSON with service status, Nebius adapter configuration validity, model name, and SQLite status.
- `GET /api/surveys`
  - Returns JSON array of all surveys in SQLite (`LW-DEMO-001` by default).
- `GET /api/surveys/LW-DEMO-001`
  - Returns JSON object for `LW-DEMO-001` with nested `evidence: [...]` and `ai_assessments: [...]`.
- `GET /api/surveys/LW-DEMO-001/export`
  - Returns `text/html` printable A4 Statutory Survey Report with SHA-256 seal.

#### Protected Survey Write Endpoints (`Authorization: Bearer <ADMIN_API_KEY>` Mandatory)
- `POST /api/surveys/LW-DEMO-001/upload`
  - **Body (optional JSON)**: `{"image_base64": "data:image/jpeg;base64,..."}` (if omitted, uses `data/media/transformer_TR001_source.jpg`).
  - **Effect**: Writes image to `data/uploads/evidence_LW-DEMO-001_TR001_<ts>.jpg`, computes SHA-256 hash, inserts into `evidence` table, returns HTTP `201`.
- `POST /api/surveys/LW-DEMO-001/ai-inspect`
  - **Body (optional JSON)**:
    - `nitrogen_pressure` (default `"0.25 bar"`)
    - `impact_recorder_g` (default `"0.8 G (longitudinal), 0.4 G (transverse)"`)
    - `lashing_status` (default `"8 x Grade 80 16mm chains verified at 45° angle with turnbuckles secured"`)
    - `visual_remarks` (default transformer exterior observation string)
  - **Effect**: Calls Nebius Token Factory via `nebius_adapter.complete()`, records token/cost metrics in `AIOpsService`, inserts assessment into `ai_assessments`, returns HTTP `200`.
- `POST /api/surveys/LW-DEMO-001/approve`
  - **Body (optional JSON)**:
    - `surveyor_name` (default `"Alexandru Radu"`)
    - `license_number` (default `"DEMO-MWS-2026-001"`)
    - `final_remarks`
  - **Effect**: Computes SHA-256 seal over `survey_id:surveyor_name:license_no:timestamp:APPROVED`, updates `surveys` status to `APPROVED`, returns HTTP `200`.
- `POST /api/surveys/LW-DEMO-001/reset`
  - **Body**: `{}`
  - **Effect**: Deletes `evidence` and `ai_assessments` rows for `LW-DEMO-001` and resets `surveys.status` to `'IN_PROGRESS'`.

#### Protected AI Operations & Cost Observatory Endpoints (`Authorization: Bearer <ADMIN_API_KEY>` Mandatory)
- `GET /api/ai-ops/overview?currency=EUR&include_synthetic=true`
- `GET /api/ai-ops/usage?period=daily&limit=14&include_synthetic=true`
- `GET /api/ai-ops/models?include_synthetic=true`
- `GET /api/ai-ops/costs?include_synthetic=true`
- `GET /api/ai-ops/health`
- `GET /api/ai-ops/alerts?resolved=false`
- `GET /api/ai-ops/requests?page=1&page_size=25&model=&survey_id=&status=&include_synthetic=true`
- `GET /api/ai-ops/export?format=csv&include_synthetic=true` (or `format=json`)
- `POST /api/ai-ops/seed-demo` (`{"count": 42}`)
- `POST /api/ai-ops/clear-demo` (`{}`)
- `POST /api/ai-ops/alerts/resolve` (`{"alert_id": 1}`)

---

### 2.3 Documented vs. Implemented Capabilities Gap Analysis

The following features are described in architectural documentation (`README.md`, `docs/help.md`, `docs/help3.md`, `docs/help4.md`) or user prompt examples, and their exact implementation state in the repository is as follows:

1. **Dynamic Multi-Survey Creation (`POST /api/surveys` / *"Create new survey"*)** — **`NOT IMPLEMENTED`**
   - `leewu_mvp_server.py` currently hardcodes routes for `/api/surveys/LW-DEMO-001` (`/upload`, `/ai-inspect`, `/approve`, `/reset`, `/export`). Creating a new survey ID (e.g., `LW-2026-002`) via API or Telegram is not yet wired.
2. **Multimodal Vision Defect Analysis on Uploaded Photos (`nvidia/nemotron-vision-4b` / *"Analyze these cargo photos"*)** — **`NOT IMPLEMENTED`**
   - Documented in `docs/help3.md` (`cargo_photo_analysis`). In actual code, `telegram_bot_daemon.py` logs the timestamp of uploaded Telegram photos without downloading the image buffer, and `handle_ai_inspect` in `leewu_mvp_server.py` sends a structured text prompt to Nemotron rather than a base64 vision payload.
3. **Hermes 4-Skill Pipeline Runner & Tavily Live Web Search (`scripts/hermes_skills_engine.py`, `scripts/tavily_engine.py`)** — **`NOT IMPLEMENTED` (Documentation Blueprints Only)**
   - Both scripts appear as code listings inside `docs/help3.md` and `docs/help4.md`, but do not exist as executable files in `scripts/` (which contains `ai_ops_service.py`, `nebius_provider.py`, and `cloudflare_security_audit.*`).
4. **Shipping Document Completeness Check (*"Check missing documents"*)** — **`PARTIAL`**
   - Vehicle fleet document checks (`/acte` for ITP/RCA/Rovinietă) are implemented, whereas checking missing shipping documents (`Bill of Lading`, `Mate's Receipt`, `Cargo Manifest`, `Certificate of Origin`) per vessel is only handled conversationally if asked to Nemotron.

---

## 3. Concrete Usage Examples

### 3.1 Telegram Bot (`@Leewubot`) Examples

```text
# 1. Open interactive field menu
/start

# 2. Check live combined status (SQLite LW-DEMO-001 + MV WAN FU Berth 52 + damage count)
/status

# 3. Log a damaged steel coil on Hold 3 (persists to data/survey_remarks.json)
/remark Hold 3 Coil #485 margine flambata 35mm la scoaterea din cala cu chinga metalica

# 4. List all recorded field damages
/avarii

# 5. View statutory certificate summary for TR-001
/raport

# 6. Check EXIF shift timesheet & billable RON
/pontaj

# 7. Generate vehicle trip sheet (CT-88-LPM)
/foaie

# 8. Check fleet document expiry warnings
/acte

# 9. Natural language query (powered by Nemotron-3-Ultra-550b-a55b + live operational context)
Redactează o notă de protest (Letter of Protest) conform Hague-Visby Art. III r.2 pentru avariile critice din Magazia 3 la MV WAN FU.
```

### 3.2 Local REST API (`http://127.0.0.1:8080`) Examples

#### PowerShell (Windows)

```powershell
# 1. Public Read-Only: Check server & Nebius health
Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/health" -Method Get

# 2. Public Read-Only: Inspect survey LW-DEMO-001 (includes evidence & AI assessments)
Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/surveys/LW-DEMO-001" -Method Get

# 3. Authenticated Write: Attach photographic evidence (requires ADMIN_API_KEY in header)
$headers = @{
    "Authorization" = "Bearer $env:ADMIN_API_KEY"
    "Content-Type"  = "application/json"
}
Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/surveys/LW-DEMO-001/upload" `
    -Method Post -Headers $headers -Body "{}"

# 4. Authenticated Write: Trigger NVIDIA Nemotron AI Engineering Inspection
$inspectPayload = @{
    nitrogen_pressure = "0.24 bar"
    impact_recorder_g = "0.75 G (longitudinal), 0.35 G (transverse)"
    lashing_status    = "8 x Grade 80 16mm chains verified at 45° angle with turnbuckles secured"
    visual_remarks    = "Tank exterior intact, zero oil weeping, silica gel cobalt blue."
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/surveys/LW-DEMO-001/ai-inspect" `
    -Method Post -Headers $headers -Body $inspectPayload

# 5. Authenticated Write: Certify & seal survey with SHA-256
$approvePayload = @{
    surveyor_name  = "Ing. Alexandru Radu"
    license_number = "DEMO-MWS-2026-001"
    final_remarks  = "Unconditional Clean Mate's Receipt issued."
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/surveys/LW-DEMO-001/approve" `
    -Method Post -Headers $headers -Body $approvePayload

# 6. Authenticated Admin Read: Query AI Ops Cost & Token Observatory
Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/ai-ops/overview?currency=EUR&include_synthetic=true" `
    -Method Get -Headers $headers
```

#### `curl` (Bash / Cross-Platform)

```bash
# Public Read-Only: Download Printable HTML Statutory Certificate
curl -s http://127.0.0.1:8080/api/surveys/LW-DEMO-001/export -o certificate_LW_DEMO_001.html

# Authenticated Write: Trigger AI Inspection (Fail-Closed Bearer Auth)
curl -X POST http://127.0.0.1:8080/api/surveys/LW-DEMO-001/ai-inspect \
  -H "Authorization: Bearer ${ADMIN_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"nitrogen_pressure":"0.24 bar","impact_recorder_g":"0.75 G","lashing_status":"8 x Grade 80 chains OK"}'
```

---

## 4. Top 10 Recommended Next Commands for a Marine Cargo Surveyor

To evolve LeeWu AI from a fixed single-survey MVP (`LW-DEMO-001` + `MV WAN FU`) into a full multi-vessel field command system, the following **10 high-value commands** are recommended in priority order:

| Priority | Proposed Command (Telegram & API) | Target Persona | Operational Purpose & Value |
| :- | :--- | :--- | :--- |
| **1** | `/newsurvey <vessel> <imo> <berth> <cargo>`<br>`POST /api/surveys` | Field Surveyor / Admin | **Dynamic Survey Creation**: Initialize a new `survey_id` (e.g., `LW-2026-002`) in SQLite directly from the quay, setting it as the active context for subsequent photos and remarks. |
| **2** | `/lop <hold> <party> <reason>`<br>`POST /api/surveys/:id/letter-of-protest` | Field Surveyor / Legal | **Instant Letter of Protest (Note of Protest) Generator**: Drafts a bilingual (EN/RO) Hague-Visby Art. III r.6 formal notice against Stevedores or Vessel Master, ready for counter-signature on deck. |
| **3** | `/draft <fwd_port> <fwd_stbd> <mid_p> <mid_s> <aft_p> <aft_s> <density>`<br>`POST /api/surveys/:id/draft-survey` | Marine Surveyor | **UN ECE Draft Survey Calculator**: Computes Quarter Mean Draft, trim corrections, dock water density displacement adjustment, and net cargo discharged/loaded in Metric Tons. |
| **4** | `/sof <event_type> <start_hhmm> [end_hhmm] <note>`<br>`POST /api/surveys/:id/sof` | Field Surveyor / Charterers | **Statement of Facts (SOF) & Laytime Logger**: Logs weather stoppages (rain/wind), crane breakdowns, hatch opening/closing, and automatically calculates net laytime vs. demurrage/despatch. |
| **5** | `/vision` (attached to a Telegram photo)<br>`POST /api/surveys/:id/vision-inspect` | Field Surveyor | **Live Multimodal Photo Defect Analysis**: Downloads the Telegram photo buffer, computes its SHA-256 hash, attaches it to SQLite `evidence`, and runs a Vision-Language model (`Nemotron-VL`) to classify rust grade (ISO 8501-1) or mechanical denting. |
| **6** | `/silvernitrate <hold> <item_ref> <positive|negative>`<br>`POST /api/surveys/:id/chemical-test` | Field Surveyor / P&I Auditor | **AgNO3 Chloride Titration Logger**: Records silver nitrate test results on steel cargo to legally differentiate fresh rain/condensation rust from seawater ingress (crucial for Gard/Skuld P&I claims). |
| **7** | `/ullage <hold> <bilge_port_cm> <bilge_stbd_cm> <hatch_db>`<br>`POST /api/surveys/:id/hatch-ultrasonic` | Field Surveyor | **Ultrasonic Hatch Tightness & Bilge Sounding Log**: Records Sherlog ultrasonic dB readings across hatch coamings and bilge well soundings prior to/after discharge. |
| **8** | `/lashing <weight_mt> <chains_count> <wll_t> <angle_deg> <mu>`<br>`POST /api/surveys/:id/css-annex13` | Marine Warranty Surveyor (MWS) | **IMO CSS Code Annex 13 Lashing Check**: Calculates transverse/longitudinal sliding and tipping safety factors on the spot and flags if additional Grade 80 chains or timber dunnage are required before sailing. |
| **9** | `/docs <survey_id>`<br>`GET /api/surveys/:id/checklist` | Surveyor / Client / Admin | **Shipping Document Completeness Gate**: Tracks mandatory statutory documents per vessel (`Bill of Lading`, `Cargo Manifest`, `Packing List`, `Mate's Receipt`, `Lashing Certificate`, `Time Sheet`) and flags missing items before final sign-off. |
| **10** | `/pdf [survey_id]`<br>`GET /api/surveys/:id/export.pdf` | Surveyor / Client / Auditor | **Direct Telegram Document Delivery**: Generates the signed statutory report (with embedded photos, remarks table, and SHA-256 seal) and sends it directly into the Telegram chat via `sendDocument` so the surveyor can forward it to the ship's Master or P&I Club from their phone. |
