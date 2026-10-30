# LeeWu AI — Cloudflare Preparation & Release Plan (Phase 6)

**Phase Status**: **PASS (Configuration Prepared & Reconciled; Tunnel NOT Activated, DNS Unchanged)**

---

## 1. Architectural Separation Confirmed

| Component | Hosting Tier | Public Exposure | Notes |
| :--- | :--- | :--- | :--- |
| **Static Frontend (`*.html`, `ai_ops.js`, `ai_ops.css`, `_headers`)** | Cloudflare Pages (or Local Offline HTTP) | Public HTTPS (Read-Only UI) | Zero secrets in frontend bundle; `ADMIN_API_KEY` never embedded in JS. |
| **Python REST API (`leewu_mvp_server.py`)** | Local Server (`127.0.0.1:8080`) | Scoped `/api/*` only (when Tunnel enabled) | All `POST` write routes & `/api/ai-ops/*` require `Authorization: Bearer <ADMIN_API_KEY>`. |
| **SQLite Database (`data/leewu_mvp.db`)** | Local Server Disk | **NEVER EXPOSED** | Protected by OS filesystem permissions and `.gitignore`. |
| **Telegram Bot (`telegram_bot_daemon.py`)** | Local Server Daemon | Outbound Long-Polling Only | Requires zero inbound ports; restricted to numeric ID `8143220589`. |
| **Legacy Node-RED (`:1880`) & n8n (`:5678`)** | Localhost Only | **DISABLED / REMOVED FROM INGRESS** | Reconciled in `cloudflare/config.yml` so admin UIs are never exposed. |

---

## 2. Reconciled `cloudflare/config.yml`

`cloudflare/config.yml` has been updated and verified by `tests/test_cloudflare_preflight.py`:
- Exposes **only** `hostname: api.leewuai.ro` with path filter `path: ^/api/.*` -> `http://127.0.0.1:8080`.
- Removes active ingress mappings for `automation.leewuai.ro` (`localhost:1880`) and `n8n.leewuai.ro` (`localhost:5678`).
- Enforces `- service: http_status:404` catch-all rule at the bottom of the ingress list.

---

## 3. Security Headers (`_headers` & `leewu_mvp_server.py`)

Both Cloudflare Pages (`_headers`) and the Python API (`leewu_mvp_server.py`) emit:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: SAMEORIGIN`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- `Content-Security-Policy: default-src 'self' https: data: blob: 'unsafe-inline'; frame-ancestors 'self'; object-src 'none'; base-uri 'self'`
