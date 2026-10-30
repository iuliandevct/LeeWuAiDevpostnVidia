# LEEWU AI — TELEMETRY & AI OPERATIONS VALIDATION REPORT

**Module:** LeeWu AI – AI Operations & Cost Observatory  
**Component:** `ai_ops_service.py` & `scripts/nebius_provider.py`  
**Database:** SQLite (`data/leewu_mvp.db`) with WAL Mode  
**Test Suite:** `tests/test_ai_ops_foundation.py` (15/15 PASS)  

---

## 1. INFERENCE TRACEABILITY & INTEGRITY

- **Single Event Guarantee:** Exactly one telemetry event is recorded per logical inference request. Provider retries within `nebius_provider.py` do not generate duplicate billable events.
- **Provider Request ID:** Preserved exactly from Nebius / OpenAI response headers (`x-request-id` or UUID).
- **Latency Measurement:** Recorded via monotonic high-resolution timer (`time.perf_counter()`).
- **Token Count Veracity:** Extracted strictly from provider response metadata (`usage.prompt_tokens`, `usage.completion_tokens`, `usage.total_tokens`). Missing usage metadata is explicitly recorded as `-1` (UNAVAILABLE), never fabricated.
- **Privacy Enforcement:** Prompts, completions, personal names, and authorization headers are strictly excluded from telemetry tables (`ai_ops_events`).

---

## 2. NEBIUS TOKEN FACTORY INTEGRATION

- **Endpoint:** `https://api.tokenfactory.nebius.com/v1/chat/completions` (OpenAI-compatible)
- **Primary Model:** `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`
- **Fallback Models:** `nvidia/nemotron-4-340b-instruct`, `meta-llama/Meta-Llama-3.1-70B-Instruct`
- **Configuration Precedence:**
  1. Explicit constructor arguments.
  2. Environment variables (`NEBIUS_API_KEY`, `NEBIUS_BASE_URL`, `NEBIUS_MODEL`).
  3. Safe defaults (no silent fallback to OpenAI or NVIDIA developer keys).

---

## 3. PRICING CONFIGURATION & ACCURACY

Tariffs loaded from `config/ai_pricing.json`:
- `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`:
  - Input: $0.20 / 1M tokens
  - Output: $0.60 / 1M tokens
  - Source: Nebius Token Factory Public Tariffs
- `nvidia/nemotron-4-340b-instruct`:
  - Input: $1.80 / 1M tokens
  - Output: $5.40 / 1M tokens
- **Sentinel Rule:** Unknown or unpriced models return `-1.0` (UNAVAILABLE). Pricing calculations never default to zero cost for unknown models.
- **Currency Conversion:** Default currency EUR; fixed conversion rate $1.08 / €1.00 documented with source timestamp.

---

## 4. QUEUE RELIABILITY & STORAGE

- **Queue Architecture:** Bounded in-memory FIFO queue (`maxsize=1000`).
- **Non-blocking Dispatch:** Background daemon thread flushes events asynchronously; inference latency is decoupled from SQLite disk I/O.
- **Saturation Protection:** Queue overflow drops events gracefully with monotonic counter logging; database locks never crash inference callers.
- **SQLite Concurrency:** Configured with `PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON`, and `PRAGMA busy_timeout=5000`.
