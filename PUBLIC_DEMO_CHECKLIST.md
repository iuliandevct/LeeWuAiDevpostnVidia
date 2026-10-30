# LeeWu AI — Public Read-Only Demo Checklist (Phase 4)

**Synthetic Dataset**: `LW-DEMO-001` (Vessel: `MV DEMO CARRIER`, IMO: `9845120`, Cargo: `Industrial Transformer TR-001`, `124.5 MT`, Berth 120 Port of Constanța)  
**Phase Status**: **PASS**

---

## 1. Public Read-Only Verification Matrix

- [x] **Dashboard & Landing Pages (`index.html`, `landing.html`, `demo.html`, `survey-console.html`)**: Render cleanly with zero embedded API keys or administrative credentials.
- [x] **Synthetic Cargo Information (`LW-DEMO-001`)**: `GET /api/surveys` and `GET /api/surveys/LW-DEMO-001` return 100% synthetic inspection metadata (`MV DEMO CARRIER`, `SIEMENS ENERGY GLOBAL`, `TR-001`, `124.5 MT`, `N2 = 0.24 bar`, `0.75 G`).
- [x] **Photographic Evidence (`cbfd090e07a67ab20818c3e113fa6276ad37f3ba9da9479528fdf4dc2e0464b7`)**: High-resolution synthetic transformer photo (`1280x720`) verified and displayed with SHA-256 integrity metadata.
- [x] **AI Assessment Results**: Pre-computed NVIDIA Nemotron statutory engineering assessment displayed in `demo.html` and `/api/surveys/LW-DEMO-001/export` without triggering live Nebius billing for public visitors.
- [x] **Statutory Printable A4 / PDF Report (`GET /api/surveys/LW-DEMO-001/export` & `survey.html`)**: Includes explicit synthetic disclaimer banner (`⚠️ DEMONSTRATION WORKFLOW — SYNTHETIC DATASET (LW-DEMO-001)`), data provenance labels (`OBSERVED & MEASURED`, `AI_INFERRED`, `HUMAN_APPROVED`), HTML-escaped fields, and SHA-256 integrity checksum.
- [x] **Responsive Mobile & Desktop Layout**: CSS grid breakpoints (`@media (max-width: 900px)`) and Tailwind responsive containers verified across `demo.html`, `login.html`, `landing.html`, and `survey-console.html`.
- [x] **Incognito / Unauthenticated Access**:
  - `GET` requests succeed with `200 OK` without cookies or tokens.
  - Unauthenticated `POST` attempts (`/upload`, `/ai-inspect`, `/approve`, `/reset`) return `401 Unauthorized` (`AUTH_REQUIRED`) and display a clear read-only toast in `demo.html`.
  - Role preview buttons in `login.html` explicitly enter `READ_ONLY_PREVIEW` (`authenticated: false`, `read_only: true`) and never claim backend authentication.
- [x] **Zero Real Customer PII or Paid Inference**: All personal names, license numbers, and corporate entities in tracked files are synthetic (`Ing. Alexandru Radu`, `DEMO-MWS-2026-001`, `LeeWu Maritime Survey`, `GLOBAL OCEAN SHIPPING`).
