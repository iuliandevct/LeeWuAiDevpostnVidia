# LeeWu AI — Post-Release Security Audit

**Repository**: `LeeWuAiDevpostnVidia`  
**Branch**: `main`  
**Baseline Published Commit**: `feb0c31cbc726ac8e99ada4a07c3b5fbcf57dd30`  
**Audit Date**: 2026-10-30  
**Scope**: Post-release security audit of write endpoints, authentication enforcement, loopback/proxy trust boundaries, and frontend demo login handling. No new features, schema migrations, DNS changes, or Cloudflare Tunnel activation.  
**Audit Verdict**: **PASS (All P0 & P1 Defects Remediated and Verified)**

---

## 1. Executive Summary

Following the initial repository cleanup and release (`feb0c31cbc726ac8e99ada4a07c3b5fbcf57dd30`), a targeted security audit was conducted on `leewu_mvp_server.py`, `login.html`, `web/login.html`, `dist/login.html`, `demo.html`, and `.env.example`.

Three high-priority defect classes were identified and remediated:
1. **P0 — Unauthenticated Write Endpoints & Paid Inference Exposure (`leewu_mvp_server.py`)**: Write operations defaulted to fail-open (`REQUIRE_AUTH_FOR_WRITES="false"`) and explicitly exempted `/api/surveys/LW-DEMO-001/*` (`upload`, `ai-inspect`, `approve`, `reset`), allowing unauthenticated callers to mutate SQLite survey records and trigger paid Nebius Token Factory inference.
2. **P0 — Loopback Authentication Bypass Across Cloudflare Tunnel (`check_admin_auth()`)**: When `ADMIN_API_KEY` was unset or empty, `check_admin_auth()` trusted loopback client addresses (`127.0.0.1`, `localhost`, `::1`) and a static fallback token (`demo-admin-local`). Because `cloudflared` connects to the local Python backend from `127.0.0.1`, this loopback assumption created an authentication bypass risk if `ADMIN_API_KEY` was omitted.
3. **P1 — Client-Side Arbitrary Password Acceptance & Demo Session Misrepresentation (`web/login.html` / `login.html`)**: When the authentication backend was unreachable, `handleEmailSignIn()` accepted any password of 6 or more characters (`password.length >= 6`) for recognized demo accounts, and `handleSignUp()` issued a synthetic `"local-demo-jwt"` token.

---

## 2. Detailed Defect Inventory

| Defect ID | Severity | Component / File | Vulnerability Description | Impact Prior to Fix | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **SEC-P0-01** | **P0 (Critical)** | `leewu_mvp_server.py` (`do_POST`) | `REQUIRE_AUTH_FOR_WRITES` defaulted to `"false"` and exempted `/api/surveys/LW-DEMO-001/*` (`upload`, `ai-inspect`, `approve`, `reset`). | Unauthenticated public requests could trigger paid Nebius AI inference (`ai-inspect`), upload files, overwrite approval seals, or reset survey data. | **REMEDIATED** |
| **SEC-P0-02** | **P0 (Critical)** | `leewu_mvp_server.py` (`check_admin_auth`) | Missing `ADMIN_API_KEY` fell back to trusting `client_ip in ("127.0.0.1", "::1", "localhost")` or `token == "demo-admin-local"`. | Requests proxied via `cloudflared` originate from `127.0.0.1` at the TCP socket layer, bypassing admin authentication if `ADMIN_API_KEY` was not set. | **REMEDIATED** |
| **SEC-P0-03** | **P0 (High)** | `leewu_mvp_server.py` (`do_GET`, `do_POST`, `check_admin_auth`) | Query-string credential parameters (`?admin_key=`, `?token=`, `?api_key=`, etc.) were only checked inside `check_admin_auth` for `?admin_key=` and `?token=`. | Credentials passed in URL query strings could leak into access logs, browser history, or proxy telemetry if not globally rejected across all endpoints. | **REMEDIATED** |
| **SEC-P1-01** | **P1 (High)** | `web/login.html`, `login.html`, `dist/login.html` (`handleEmailSignIn`) | Client-side fallback matched `DEMO_ACCOUNTS` and accepted any password with `password.length >= 6` when backend auth was offline. | Misled operators/evaluators into treating arbitrary client-side input as a verified session and stored `"DEMO_FALLBACK"` tokens in `localStorage`. | **REMEDIATED** |
| **SEC-P1-02** | **P1 (Medium)** | `web/login.html`, `login.html`, `dist/login.html` (`handleSignUp`, `quickLogin`) | Offline sign-up fallback generated a fake `"local-demo-jwt"` token, and role preview buttons invoked `completeAuth()` as if a backend session existed. | Blurred the boundary between unauthenticated UI role preview and authenticated backend sessions. | **REMEDIATED** |

---

## 3. Security Architecture & Trust Boundary Verification

### 3.1 Write Endpoint & Nebius Cost Protection
- All `POST` routes (`/api/surveys/LW-DEMO-001/upload`, `/api/surveys/LW-DEMO-001/ai-inspect`, `/api/surveys/LW-DEMO-001/approve`, `/api/surveys/LW-DEMO-001/reset`, and `/api/ai-ops/*`) are gated by `check_admin_auth()`.
- `REQUIRE_AUTH_FOR_WRITES` defaults to `"true"` (fail-closed), and `do_POST` enforces `check_admin_auth()` unconditionally.
- Public synthetic demo endpoints (`GET /api/health`, `GET /api/surveys`, `GET /api/surveys/LW-DEMO-001`, `GET /api/surveys/LW-DEMO-001/export`) remain strictly read-only (`GET`) and cannot invoke `nebius_adapter.complete()` or mutate SQLite tables.
- `demo.html` never embeds `ADMIN_API_KEY` in frontend JavaScript; it reads an operator token only if explicitly supplied in `sessionStorage`/`localStorage` (`leewu_admin_token`) and displays a clear read-only notice on HTTP `401`.

### 3.2 Loopback & Cloudflare Tunnel Request Path
- `check_admin_auth()` does not inspect `self.client_address`, `X-Forwarded-For`, `CF-Connecting-IP`, `X-Real-IP`, or `Host` for authentication decisions.
- If `ADMIN_API_KEY` is missing or empty in the server environment, `check_admin_auth()` immediately returns `False` (fail-closed).
- Token validation uses `secrets.compare_digest(token.encode("utf-8"), admin_key.encode("utf-8"))` to prevent timing side-channel attacks.

### 3.3 SQLite Database Preservation
- Original database (`data/leewu_mvp.db`) was preserved intact throughout the audit and test execution:
  - **SHA-256**: `3ffd6c05de47923d4d2db094877ae8c543e94ec1a415fb079a2d2724bea6e345`
  - **Size**: `282,624` bytes

---

## 4. Remaining Risks & Operational Recommendations

1. **Single Shared Bearer Key (`ADMIN_API_KEY`) for MVP Write Operations**:
   - *Risk*: The local MVP server uses a single symmetric Bearer token (`ADMIN_API_KEY`) for administrative and write endpoints rather than per-user short-lived JWTs signed by an external IdP.
   - *Mitigation*: Keep `ADMIN_API_KEY` stored exclusively in server-side `.env` (gitignored), rotate it periodically, and never embed it in static frontend bundles.
2. **Rate Limiting at Edge When Tunnel is Activated in Future**:
   - *Risk*: While unauthenticated POST requests now immediately return HTTP `401` without touching Nebius or SQLite, volumetric HTTP floods could still reach the local Python HTTP server if Cloudflare Tunnel is activated later.
   - *Mitigation*: Enforce Cloudflare WAF rate-limiting rules and Cloudflare Access policies on `api.leewuai.ro` before enabling any public tunnel.
