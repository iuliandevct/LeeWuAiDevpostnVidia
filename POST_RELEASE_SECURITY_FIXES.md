# LeeWu AI — Post-Release Security Fixes

**Repository**: `LeeWuAiDevpostnVidia`  
**Branch**: `main`  
**Baseline Commit**: `feb0c31cbc726ac8e99ada4a07c3b5fbcf57dd30`  
**Date**: 2026-10-30  
**Status**: **PASS**

---

## 1. Exact Files Changed

### Repository (`LeeWuAiDevpostnVidia`) & Working Project (`youtube`)
1. `leewu_mvp_server.py`
2. `.env.example`
3. `login.html`
4. `web/login.html` (in `LeeWuAiDevpostnVidia`) / `dist/login.html` (in `youtube`)
5. `demo.html`
6. `tests/test_post_release_security.py` *(new comprehensive security test suite)*
7. `tests/test_crud_regression_isolated.py` *(updated to pass Bearer token for isolated HTTP CRUD writes)*
8. `tests/test_complete_demo_validation.py` *(updated to pass Bearer token for authorized writes and mock Nebius by default)*
9. `tests/test_ai_ops.py` *(updated `test_08_admin_authorization` to assert fail-closed loopback behavior)*
10. `tests/test_nebius_integration.py` & `tests/test_transformer_extraction.py` *(updated to use local deterministic Nebius mock server by default unless `RUN_LIVE_NEBIUS_TESTS=1` so zero paid API credits are consumed)*

---

## 2. Defect-by-Defect Remediation Summary

### P0 — Protect All Write Endpoints (`leewu_mvp_server.py`)

1. **Default `REQUIRE_AUTH_FOR_WRITES` Changed to Fail Closed**:
   - Changed `REQUIRE_AUTH_FOR_WRITES` in `do_POST()` from `os.getenv("REQUIRE_AUTH_FOR_WRITES", "false")` to:
     ```python
     REQUIRE_AUTH_FOR_WRITES = os.getenv("REQUIRE_AUTH_FOR_WRITES", "true").strip().lower() not in ("false", "0")
     ```
   - Updated `.env.example` to document `REQUIRE_AUTH_FOR_WRITES="true"`.
2. **Removed `LW-DEMO-001` Write Exemption**:
   - Removed the `not path.startswith("/api/surveys/LW-DEMO-001/")` bypass in `do_POST()`.
   - Every `POST` operation—including `/api/surveys/LW-DEMO-001/upload`, `/api/surveys/LW-DEMO-001/ai-inspect`, `/api/surveys/LW-DEMO-001/approve`, `/api/surveys/LW-DEMO-001/reset`, and `/api/ai-ops/*`—now requires a valid `Authorization: Bearer <ADMIN_API_KEY>` header.
3. **Constant-Time Token Comparison (`secrets.compare_digest`)**:
   - `check_admin_auth()` validates the Bearer token exclusively via `secrets.compare_digest(token.encode("utf-8"), admin_key.encode("utf-8"))`.
4. **Strict Rejection of Query-String Credentials**:
   - Added `has_query_credentials(parsed_url)` checking `FORBIDDEN_QUERY_CREDENTIAL_KEYS` (`admin_key`, `token`, `api_key`, `apikey`, `key`, `access_token`, `auth`, `bearer`, `password`, `secret`).
   - Enforced at the top of `do_GET()`, `do_POST()`, and `check_admin_auth()` so any request carrying credentials in URL query parameters immediately returns HTTP `401` (`AUTH_REQUIRED`), even if a valid Bearer header is also present.
5. **Public Synthetic Demo Kept Strictly Read-Only (`demo.html` & `leewu_mvp_server.py`)**:
   - Unauthenticated `GET /api/surveys/LW-DEMO-001` and `GET /api/surveys/LW-DEMO-001/export` remain publicly readable (`200 OK`) for hackathon inspection without incurring Nebius API costs or mutating SQLite rows.
   - `demo.html` does not contain or expose `ADMIN_API_KEY`; write buttons send an `Authorization: Bearer` header only if an operator has configured `leewu_admin_token` in storage, and gracefully display a read-only notice on HTTP `401`.

---

### P0 — Remove Loopback Authentication Bypass (`check_admin_auth()`)

1. **Removed `127.0.0.1`, `localhost`, and `::1` Loopback Trust**:
   - Deleted the fallback branch in `check_admin_auth()` that checked `client_ip in ("127.0.0.1", "::1", "localhost")` and `token == "demo-admin-local"`.
2. **Fail-Closed on Missing `ADMIN_API_KEY`**:
   - If `ADMIN_API_KEY` is unset or empty (`not admin_key`), `check_admin_auth()` returns `False` unconditionally for all callers (including loopback and `cloudflared`).
3. **Zero Trust in Client-Controlled / Proxy Headers**:
   - `check_admin_auth()` ignores `X-Forwarded-For`, `CF-Connecting-IP`, `X-Real-IP`, `X-Forwarded-Host`, and `Host`.

---

### P1 — Harden Demo Login (`web/login.html`, `login.html`, `dist/login.html`)

1. **Removed Arbitrary `>= 6` Character Password Fallback**:
   - Removed the fallback in `handleEmailSignIn()` that matched `DEMO_ACCOUNTS` by email and accepted any password with `password.length >= 6`.
   - When backend authentication fails or is unreachable, `handleEmailSignIn()` now rejects the login attempt with an explicit error banner (`"Authentication rejected: Invalid credentials or authentication server unreachable. Arbitrary client-side passwords are not accepted..."`).
2. **Removed Offline Sign-Up Fake JWT Fallback**:
   - Removed the fallback in `handleSignUp()` that created a local profile with `"local-demo-jwt"` when the backend was unreachable.
3. **Separated Read-Only UI Preview from Authenticated Sessions**:
   - Added `enterReadOnlyDemoPreview(userProfile)` for the quick-preview role cards (`quickLogin()`).
   - Stores `{ authenticated: false, read_only: true, mode: "READ_ONLY_PREVIEW" }`, explicitly removes `leewu_auth_token` (`localStorage.removeItem("leewu_auth_token")`), sets `leewu_demo_mode = "READ_ONLY_PREVIEW"`, and displays a clear notice that preview mode is unauthenticated and read-only.
   - Updated UI labels from `"Instant Demo Role Switcher"` / `"1-CLICK JWT"` to `"Read-Only UI Role Preview (Unauthenticated)"` / `"READ-ONLY"`.
