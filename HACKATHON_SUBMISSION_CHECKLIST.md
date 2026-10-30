# LEEWU AI — NEBIUS × NVIDIA GLOBAL AI HACKATHON SUBMISSION CHECKLIST

**Project Title:** LeeWu AI — Autonomous Maritime Intelligence & Cargo Operations Platform  
**Competition:** Nebius × NVIDIA Global AI Hackathon (Devpost)  
**Submission Category:** Autonomous Agents & Enterprise Operations  

---

## 1. SUBMISSION REQUIREMENTS CROSS-REFERENCE

| Requirement | Implementation Details | Status |
|---|---|---|
| **NVIDIA Technology Usage** | Powered by **NVIDIA Nemotron** family (`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`) for heavy lift warranty inspection, damage remark classification, and IMO CSS Code compliance synthesis. | **VERIFIED** |
| **Nebius Token Factory Integration** | Native OpenAI-compatible adapter (`scripts/nebius_provider.py`) connecting directly to `https://api.tokenfactory.nebius.com/v1`. Live token usage and latency extracted from responses. | **VERIFIED** |
| **AI Operations Observability** | Independent Grafana-inspired monitoring dashboard (`/ai-ops.html`) tracking request volume, token consumption, cost breakdown, latency percentiles, and alerts. | **VERIFIED** |
| **Working Code & Reproducibility** | Zero-dependency local backend (`leewu_mvp_server.py`) with native SQLite, Vanilla HTML/CSS/JS frontend, and automated test suite (33/33 tests passing). | **VERIFIED** |
| **Demonstrable Workflow** | Complete 10-step maritime inspection lifecycle (`LW-DEMO-001` transformer warranty assessment) demonstrable locally on `http://127.0.0.1:8080`. | **VERIFIED** |
| **Field Surveyor Telegram Bot** | Daemon (`telegram_bot_daemon.py`) with multi-turn persistent conversational memory, EXIF timestamp logging, and strict numeric-only authorization. | **VERIFIED** |
| **Responsible Security & Safety** | Zero active credentials in working tree; strict fail-closed allowlist; constant-time API authentication; RFC 9116 security policy. | **VERIFIED** |

---

## 2. MANUAL SUBMISSION FIELDS FOR DEVPOST

The following items must be entered manually by the user in the Devpost submission portal:

1. **Project Video URL:** Record a 3-minute video demonstration covering:
   - Maritime survey console (`http://127.0.0.1:8080/demo.html`).
   - Telegram field surveyor bot interaction.
   - AI Operations & Cost Observatory (`http://127.0.0.1:8080/ai-ops.html`).
   - Report export with SHA-256 integrity checksum.
2. **Repository URL:** `https://github.com/imlazar/LeeWuAiDevpostnVidia` (or authorized clean public remote).
3. **Track Selection:** Enterprise AI / Autonomous Operations.
4. **License Confirmation:** BSD 2-Clause License (confirmed in `LICENSE`).
5. **Team Members:** Julian Lazar / Michael Lazarus.
