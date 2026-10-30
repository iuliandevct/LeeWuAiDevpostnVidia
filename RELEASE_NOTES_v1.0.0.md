# LeeWu AI — Release Notes (`v1.0.0-rc1`)

**Release Tag**: `v1.0.0-rc1`  
**Branch**: `release/security-hardening`  
**Date**: 2026-10-30

---

## 1. Highlights

1. **Fail-Closed Write & AI Ops Authentication (`leewu_mvp_server.py`)**:
   - All write endpoints (`POST /api/surveys/LW-DEMO-001/upload`, `ai-inspect`, `approve`, `reset`, and `/api/ai-ops/*`) require `Authorization: Bearer <ADMIN_API_KEY>` verified with `secrets.compare_digest`.
   - Removed loopback (`127.0.0.1`, `localhost`, `::1`) and `"demo-admin-local"` authentication bypasses so reverse-proxy / Cloudflare Tunnel requests cannot bypass authentication.
   - Global rejection (`401`) of credentials passed in URL query strings (`?admin_key=`, `?token=`, `?api_key=`, etc.).
2. **Read-Only Public Demo & Hardened Login Portal (`demo.html`, `login.html`, `web/login.html`)**:
   - Public visitors can inspect synthetic survey `LW-DEMO-001` (`MV DEMO CARRIER`, Transformer `TR-001` 124.5 MT) and export the statutory A4 certificate (`GET /api/surveys/LW-DEMO-001/export`) in read-only mode without triggering paid Nebius inference or mutating SQLite data.
   - Removed client-side `password.length >= 6` and `"local-demo-jwt"` fallbacks in `login.html` / `web/login.html`; separated unauthenticated `READ_ONLY_PREVIEW` from authenticated sessions.
3. **Reconciled Cloudflare Configuration (`cloudflare/config.yml`, `_headers`)**:
   - Restricted tunnel ingress strictly to `api.leewuai.ro` (`^/api/.*` -> `http://127.0.0.1:8080`) and excluded legacy Node-RED (`:1880`) and n8n (`:5678`) ports.
   - Added `Content-Security-Policy` headers alongside `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and `Permissions-Policy`.
4. **Upgraded Telegram Field Surveyor Bot (`@Leewubot`)**:
   - Powered by NVIDIA Nemotron (`nvidia/Nemotron-3-Ultra-550b-a55b` with fallback to `Nemotron-3-Nano-30B-A3B`), grounded in real-time immutable read-only SQLite context (`LW-DEMO-001`) and `survey_remarks.json`, protected by fail-closed numeric ID allowlist (`8143220589`).

---

## 2. Known Limitations

- **Single Symmetric Admin Bearer Token**: Write operations on the local MVP backend use a single server-side `ADMIN_API_KEY` rather than per-user OAuth/OIDC JWTs.
- **Offline / Local-First Deployment Mode**: Per operator decision (domain `leewuai.ro` not purchased), the backend and web console operate locally (`http://127.0.0.1:8080`) while `@Leewubot` operates live on Telegram via outbound long-polling.
