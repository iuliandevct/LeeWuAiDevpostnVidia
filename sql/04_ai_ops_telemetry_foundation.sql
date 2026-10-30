-- ==============================================================================
-- LeeWu AI - AI Operations Telemetry Foundation Schema Migration
-- Standard: Antigravity AI Operations & Cost Observatory
-- Target RDBMS: SQLite 3 with WAL Mode and Foreign Keys
-- Idempotent: Safe to execute repeatedly without data loss or table truncation
-- ==============================================================================

PRAGMA foreign_keys = ON;

-- 1. AI Inference Usage Events (Telemetry Log)
CREATE TABLE IF NOT EXISTS ai_usage_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL UNIQUE,
    timestamp_utc TEXT NOT NULL,
    provider TEXT NOT NULL,
    model_id TEXT NOT NULL,
    survey_id TEXT,
    service_caller TEXT NOT NULL DEFAULT 'mws-survey-server',
    operation_type TEXT NOT NULL DEFAULT 'statutory-assessment',
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    cached_tokens INTEGER NOT NULL DEFAULT 0,
    latency_ms REAL NOT NULL DEFAULT 0.0,
    http_status INTEGER NOT NULL DEFAULT 200,
    status TEXT NOT NULL DEFAULT 'SUCCESS',  -- 'SUCCESS', 'FAILURE', 'TIMEOUT'
    error_category TEXT,                    -- 'AUTH_ERROR', 'RATE_LIMIT', 'TIMEOUT', 'VALIDATION_ERROR', 'SERVER_ERROR', 'CLIENT_ERROR'
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    estimated_cost REAL NOT NULL DEFAULT -1.0,
    currency TEXT NOT NULL DEFAULT 'EUR',
    is_synthetic INTEGER NOT NULL DEFAULT 0, -- 0 = Live, 1 = Synthetic
    usage_source TEXT NOT NULL DEFAULT 'api_response', -- 'api_response', 'estimated', 'unavailable'
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Required Indexes on ai_usage_events
CREATE INDEX IF NOT EXISTS idx_ai_usage_timestamp ON ai_usage_events(timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_ai_usage_provider ON ai_usage_events(provider);
CREATE INDEX IF NOT EXISTS idx_ai_usage_model_id ON ai_usage_events(model_id);
CREATE INDEX IF NOT EXISTS idx_ai_usage_status ON ai_usage_events(status);
CREATE INDEX IF NOT EXISTS idx_ai_usage_request_id ON ai_usage_events(request_id);
CREATE INDEX IF NOT EXISTS idx_ai_usage_survey ON ai_usage_events(survey_id);
CREATE INDEX IF NOT EXISTS idx_ai_usage_synthetic ON ai_usage_events(is_synthetic);

-- 2. AI Models Inventory
CREATE TABLE IF NOT EXISTS ai_models (
    model_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    display_name TEXT NOT NULL,
    category TEXT NOT NULL,
    context_window INTEGER DEFAULT 32768,
    is_verified INTEGER NOT NULL DEFAULT 0,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    last_status TEXT NOT NULL DEFAULT 'UNKNOWN',
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_ai_models_provider ON ai_models(provider);
CREATE INDEX IF NOT EXISTS idx_ai_models_verified ON ai_models(is_verified);

-- 2b. Backward Compatible Table: ai_model_registry
CREATE TABLE IF NOT EXISTS ai_model_registry (
    model_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    display_name TEXT NOT NULL,
    category TEXT NOT NULL,
    context_window INTEGER DEFAULT 32768,
    is_verified INTEGER NOT NULL DEFAULT 0,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    last_status TEXT NOT NULL DEFAULT 'UNKNOWN',
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- 3. AI Model Pricing Registry
CREATE TABLE IF NOT EXISTS ai_model_pricing (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    model_id TEXT NOT NULL,
    input_price_per_million REAL,
    output_price_per_million REAL,
    cached_input_price_per_million REAL DEFAULT 0.0,
    currency TEXT NOT NULL DEFAULT 'EUR',
    effective_date TEXT,
    source_url TEXT,
    pricing_source_url TEXT,
    verification_timestamp TEXT,
    last_verified_date TEXT,
    pricing_status TEXT NOT NULL DEFAULT 'VERIFIED', -- 'VERIFIED', 'UNAVAILABLE', 'DEPRECATED'
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_ai_pricing_model ON ai_model_pricing(model_id, is_active);
CREATE INDEX IF NOT EXISTS idx_ai_pricing_provider ON ai_model_pricing(provider);

-- 4. AI Budgets & FinOps Guardrails
CREATE TABLE IF NOT EXISTS ai_budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period TEXT NOT NULL UNIQUE, -- 'daily', 'monthly'
    budget_amount REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'EUR',
    warning_threshold_pct REAL NOT NULL DEFAULT 80.0,
    hard_limit_enabled INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- 4b. Backward Compatible Table: ai_budget_limits
CREATE TABLE IF NOT EXISTS ai_budget_limits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period TEXT NOT NULL UNIQUE, -- 'daily', 'monthly'
    budget_amount REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'EUR',
    warning_threshold_pct REAL NOT NULL DEFAULT 80.0,
    hard_limit_enabled INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- 5. AI Operational & FinOps Alert Events
CREATE TABLE IF NOT EXISTS ai_alert_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp_utc TEXT NOT NULL,
    alert_type TEXT NOT NULL, -- 'budget_warning', 'budget_exceeded', 'latency_spike', 'failure_spike', 'unknown_pricing', 'anomaly'
    severity TEXT NOT NULL DEFAULT 'WARNING', -- 'INFO', 'WARNING', 'CRITICAL'
    message TEXT NOT NULL,
    metadata_json TEXT,
    resolved INTEGER NOT NULL DEFAULT 0,
    resolved_at TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_ai_alerts_timestamp ON ai_alert_events(timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_ai_alerts_resolved ON ai_alert_events(resolved);
CREATE INDEX IF NOT EXISTS idx_ai_alerts_type ON ai_alert_events(alert_type);
