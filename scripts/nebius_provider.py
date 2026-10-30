"""
scripts/nebius_provider.py
Production-Oriented Nebius Token Factory AI Provider.

Provides an enterprise OpenAI-compatible HTTP interface to NVIDIA Nemotron models hosted on
Nebius Token Factory GPU clusters, engineered with strict security and FinOps guarantees:
- Zero hardcoded credentials; strictly reads constructor args -> environment -> verified project defaults.
- Safe API key masking (`mask_api_key`) and header redaction in all exceptions and logs.
- Strict error propagation: No silent fallbacks to mocks or secondary providers.
- Bounded retries with exponential backoff and jitter for transient errors (429, 5xx, network drops).
- No retries on authentication failures (401/403) or invalid requests (400/422).
- URL construction preventing `/v1` duplication.
- Typed `NebiusResponse` dataclass with exact usage accounting (no guessing when absent).
- Integrated non-blocking AIOps telemetry and model fleet discovery.
"""

import os
import sys
import json
import time
import re
import socket
import random
import logging
import urllib.request
import urllib.error
import urllib.parse
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union

# Ensure UTF-8 output on Windows console
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Set up dedicated logger with secret redaction
logger = logging.getLogger("LeeWuAI.NebiusProvider")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)


def _get_ai_ops():
    """Lazily resolves AIOps telemetry singleton without circular imports."""
    try:
        from scripts.ai_ops_service import AIOpsService
        return AIOpsService.get_instance()
    except Exception:
        try:
            from ai_ops_service import AIOpsService
            return AIOpsService.get_instance()
        except Exception:
            return None


# ==============================================================================
# Security & Secret Masking Utilities
# ==============================================================================

def mask_api_key(key: Optional[str]) -> str:
    """
    Exposes only a minimal prefix and suffix without revealing the credential.
    Example: 'v1.SYNTHETIC_TEST_KEY_...' -> '[REDACTED_NEBIUS_KEY][REDACTED]...SUF [MASKED]'
    """
    if not key:
        return "[NOT CONFIGURED]"
    cleaned = key.strip().strip('"').strip("'")
    if len(cleaned) <= 10:
        return "[CONFIGURED - TOO SHORT TO SAFELY MASK]"
    prefix = cleaned[:6]
    suffix = cleaned[-3:]
    return f"{prefix}...[REDACTED]...{suffix} [MASKED]"


# Backward compatibility alias
mask_key = mask_api_key


def sanitize_text(text: str, secret: Optional[str] = None) -> str:
    """Strips API keys, tokens, and authorization headers from strings and stack traces."""
    if not text:
        return ""
    sanitized = text
    if secret and secret in sanitized:
        sanitized = sanitized.replace(secret, "[REDACTED_API_KEY]")
    # Redact common token patterns and Authorization headers
    sanitized = re.sub(r'Bearer\s+[A-Za-z0-9_\-\.]+', 'Bearer [REDACTED_TOKEN]', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'v1\.[A-Za-z0-9_\-\.]{16,}', '[REDACTED_KEY]', sanitized)
    return sanitized


# ==============================================================================
# Exception Hierarchy
# ==============================================================================

class NebiusError(Exception):
    """Base exception for all Nebius Token Factory provider errors."""
    pass


# Backward compatibility alias
NebiusException = NebiusError


class NebiusConfigurationError(NebiusError):
    """Raised when environment variables or required settings are missing or invalid."""
    pass


class NebiusAuthenticationError(NebiusError):
    """Raised on HTTP 401 or 403 unauthorized responses."""
    def __init__(self, message: str, status_code: int = 401):
        super().__init__(sanitize_text(message))
        self.status_code = status_code


class NebiusRateLimitError(NebiusError):
    """Raised on HTTP 429 rate limit or quota depletion."""
    def __init__(self, message: str, status_code: int = 429, retry_after: Optional[float] = None):
        super().__init__(sanitize_text(message))
        self.status_code = status_code
        self.retry_after = retry_after


class NebiusTimeoutError(NebiusError):
    """Raised when request exceeds the configured network timeout threshold."""
    pass


class NebiusValidationError(NebiusError):
    """Raised when API response fails schema or content validation."""
    pass


class NebiusAPIError(NebiusError):
    """Raised on upstream 4xx or 5xx HTTP responses from Nebius."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[str] = None):
        super().__init__(sanitize_text(message))
        self.status_code = status_code
        self.response_body = sanitize_text(response_body) if response_body else None


# ==============================================================================
# Typed Response Model
# ==============================================================================

class NebiusResponse:
    """
    Typed response object encapsulating a verified completion from Nebius Token Factory.
    Accurately represents usage tokens without heuristics or guessing.
    """
    def __init__(
        self,
        content: str,
        model: str,
        provider: str = "nebius",
        request_id: Optional[str] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        latency_ms: float = 0.0,
        finish_reason: Optional[str] = None,
        usage_available: bool = False,
        raw_metadata: Optional[Dict[str, Any]] = None,
        # Backward compatibility keyword arguments
        usage: Optional[Dict[str, Any]] = None,
        latency_seconds: Optional[float] = None,
        raw_response: Optional[Dict[str, Any]] = None,
        reasoning: Optional[str] = None
    ):
        self.content = content
        self.model = model
        self.provider = provider
        self.request_id = request_id
        self.finish_reason = finish_reason
        self.reasoning = reasoning
        self.raw_metadata = raw_metadata or raw_response or {}

        # Latency resolution
        if latency_seconds is not None and latency_ms == 0.0:
            self.latency_ms = latency_seconds * 1000.0
        else:
            self.latency_ms = latency_ms

        # Usage resolution
        if usage is not None:
            self.usage_available = bool(usage)
            self.input_tokens = input_tokens if input_tokens is not None else usage.get("prompt_tokens")
            self.output_tokens = output_tokens if output_tokens is not None else usage.get("completion_tokens")
            self.total_tokens = total_tokens if total_tokens is not None else usage.get("total_tokens")
        else:
            self.usage_available = usage_available
            self.input_tokens = input_tokens
            self.output_tokens = output_tokens
            self.total_tokens = total_tokens

    @property
    def latency_seconds(self) -> float:
        """Returns latency in seconds for backward compatibility."""
        return round(self.latency_ms / 1000.0, 3)

    @property
    def prompt_tokens(self) -> int:
        """Returns input token count or 0."""
        return self.input_tokens if self.input_tokens is not None else 0

    @property
    def completion_tokens(self) -> int:
        """Returns output token count or 0."""
        return self.output_tokens if self.output_tokens is not None else 0

    @property
    def usage(self) -> Dict[str, Any]:
        """Returns standard usage dict if available."""
        if not self.usage_available:
            return {}
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens if self.total_tokens is not None else (self.prompt_tokens + self.completion_tokens)
        }

    @property
    def raw_response(self) -> Dict[str, Any]:
        """Backward compatibility alias for raw_metadata."""
        return self.raw_metadata

    def to_dict(self) -> Dict[str, Any]:
        """Serializes response to clean dictionary without sensitive payloads."""
        return {
            "content": self.content,
            "model": self.model,
            "provider": self.provider,
            "request_id": self.request_id,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "latency_ms": round(self.latency_ms, 2),
            "latency_seconds": self.latency_seconds,
            "finish_reason": self.finish_reason,
            "usage_available": self.usage_available,
            "reasoning": self.reasoning,
            "usage": self.usage
        }

    def __repr__(self) -> str:
        tok_str = f"tokens={self.total_tokens}" if self.usage_available else "tokens=N/A"
        return (
            f"<NebiusResponse model={self.model!r} "
            f"finish={self.finish_reason!r} "
            f"{tok_str} "
            f"latency={self.latency_ms:.1f}ms>"
        )


# ==============================================================================
# Production Nebius Provider Implementation
# ==============================================================================

class NebiusProvider:
    """
    Production-oriented Nebius Token Factory Provider using OpenAI-compatible HTTP interface.

    Configuration Precedence:
    1. Explicit constructor arguments.
    2. Environment variables (`NEBIUS_API_KEY`, `NEBIUS_BASE_URL`, `NEBIUS_MODEL`).
    3. Project defaults (only for verified endpoints and models).
    """

    DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1"
    DEFAULT_MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
    DEFAULT_TIMEOUT = 45
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_DELAY = 1.0

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
        max_retries: Optional[int] = None,
        retry_delay: Optional[float] = None,
        env_file_paths: Optional[List[str]] = None
    ):
        # 1. Load local .env files if present (without overwriting pre-set OS environment)
        self._load_local_env_files(env_file_paths)

        # 2. Resolve API Key with documented precedence:
        # 1) Explicit constructor arg, 2) Environment variables, 3) Empty string
        if api_key is not None:
            self.api_key = api_key.strip().strip('"').strip("'")
        else:
            raw_key = (
                os.environ.get("NEBIUS_API_KEY") or
                os.environ.get("OPENAI_API_KEY") or
                os.environ.get("NVIDIA_API_KEY") or
                ""
            )
            self.api_key = raw_key.strip().strip('"').strip("'")

        # 3. Resolve Base URL with documented precedence:
        # 1) Explicit constructor arg, 2) NEBIUS_BASE_URL / OPENAI_API_BASE, 3) Project Default
        if base_url is not None:
            self.base_url = base_url.strip().rstrip("/")
        else:
            raw_base = (
                os.environ.get("NEBIUS_BASE_URL") or
                os.environ.get("OPENAI_API_BASE") or
                self.DEFAULT_BASE_URL
            )
            self.base_url = raw_base.strip().rstrip("/")

        # 4. Resolve Model with documented precedence:
        # 1) Explicit constructor arg (model or default_model), 2) NEBIUS_MODEL, 3) Project Default
        if model is not None:
            target_model = model.strip()
        elif default_model is not None:
            target_model = default_model.strip()
        else:
            raw_model = (
                os.environ.get("NEBIUS_MODEL") or
                os.environ.get("AIDER_DEFAULT_MODEL") or
                self.DEFAULT_MODEL
            )
            target_model = raw_model.strip()

        if target_model.startswith("openai/"):
            target_model = target_model[len("openai/"):]
        self.model = target_model
        self.default_model = self.model  # Backward compatibility alias

        # 5. Network, Timeout & Retry Configuration
        self.timeout_seconds = int(
            timeout or
            timeout_seconds or
            os.environ.get("NEBIUS_TIMEOUT") or
            self.DEFAULT_TIMEOUT
        )
        self.max_retries = int(
            max_retries or
            os.environ.get("NEBIUS_MAX_RETRIES") or
            self.DEFAULT_MAX_RETRIES
        )
        self.retry_delay = float(
            retry_delay or
            os.environ.get("NEBIUS_RETRY_DELAY") or
            self.DEFAULT_RETRY_DELAY
        )

    def _load_local_env_files(self, custom_paths: Optional[List[str]] = None) -> None:
        """Loads .env files using project's existing configuration discovery mechanism."""
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        candidate_paths = custom_paths or [
            os.path.join(project_root, ".env"),
            os.path.join(project_root, ".env.nebius"),
            os.path.join(os.getcwd(), ".env"),
            os.path.join(os.getcwd(), ".env.nebius")
        ]

        for env_path in candidate_paths:
            if os.path.exists(env_path) and os.path.isfile(env_path):
                try:
                    with open(env_path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line or line.startswith("#") or "=" not in line:
                                continue
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip('"').strip("'")
                            if k not in os.environ and v:
                                os.environ[k] = v
                except Exception as e:
                    logger.debug(f"Could not read env file {env_path}: {e}")

    def _sanitize(self, text: str) -> str:
        """Sanitizes strings using provider instance credentials."""
        return sanitize_text(text, self.api_key)

    @staticmethod
    def _validate_base_url(url: str) -> None:
        """
        Validates that base URL uses secure HTTPS, except explicitly permitted localhost development.
        """
        if not url:
            raise NebiusConfigurationError("Base URL cannot be empty.")
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme == "https":
            return
        # Permitted localhost development
        if parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1"):
            return
        raise NebiusConfigurationError(
            f"Insecure or invalid base URL scheme: '{parsed.scheme}'. Base URL must use HTTPS (except localhost development)."
        )

    def _build_url(self, path: str) -> str:
        """
        Constructs an API endpoint URL safely ensuring no duplicate '/v1'.
        Examples:
          base_url='https://api.tokenfactory.nebius.com/v1', path='chat/completions' -> .../v1/chat/completions
          base_url='https://api.tokenfactory.nebius.com/v1', path='v1/chat/completions' -> .../v1/chat/completions
          base_url='https://api.tokenfactory.nebius.com', path='chat/completions' -> .../v1/chat/completions
        """
        base = self.base_url.rstrip("/")
        clean_path = path.lstrip("/")

        if base.endswith("/v1") and clean_path.startswith("v1/"):
            return f"{base}/{clean_path[3:]}"
        elif not base.endswith("/v1") and not clean_path.startswith("v1/"):
            return f"{base}/v1/{clean_path}"
        else:
            return f"{base}/{clean_path}"

    def validate_config(self) -> Dict[str, Any]:
        """
        Audits current provider configuration without leaking credentials.
        Returns a structured dictionary with status and diagnostic error messages.
        """
        errors: List[str] = []

        if not self.api_key:
            errors.append("NEBIUS_API_KEY is missing or empty.")
        elif not (self.api_key.startswith("v1.") or len(self.api_key) >= 16):
            errors.append("NEBIUS_API_KEY does not conform to expected Token Factory format.")

        if not self.model:
            errors.append("NEBIUS_MODEL is missing or empty.")

        try:
            self._validate_base_url(self.base_url)
        except NebiusConfigurationError as ce:
            errors.append(str(ce))

        is_valid = len(errors) == 0
        return {
            "status": "VALID" if is_valid else "INVALID",
            "base_url": self.base_url,
            "model": self.model,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "key_present": bool(self.api_key),
            "key_masked": mask_api_key(self.api_key),
            "errors": errors
        }

    # Backward compatibility alias
    validate_configuration = validate_config

    # ==========================================================================
    # Model Fleet Discovery
    # ==========================================================================

    def list_models(self) -> List[str]:
        """
        Queries Nebius Token Factory for the list of deployed models.
        Preserves exact model identifiers; never falls back to invented names.
        """
        config_check = self.validate_config()
        if not config_check["key_present"]:
            raise NebiusConfigurationError("Cannot list models: NEBIUS_API_KEY is not configured.")

        url = self._build_url("models")
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "LeeWuAI-NebiusProvider/2.0",
                "Accept": "application/json"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                body = resp.read().decode("utf-8")
                data = json.loads(body)
                models = [item["id"] for item in data.get("data", []) if "id" in item]
                return sorted(models)
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8", errors="replace")
            sanitized = self._sanitize(err_body)
            if he.code in (401, 403):
                raise NebiusAuthenticationError(f"Nebius Token Factory Authentication Failed (HTTP {he.code}): {sanitized}", status_code=he.code)
            elif he.code == 429:
                raise NebiusRateLimitError(f"Nebius Token Factory Rate Limit (HTTP 429): {sanitized}", status_code=429)
            else:
                raise NebiusAPIError(f"Nebius Token Factory HTTP {he.code}: {sanitized}", status_code=he.code, response_body=sanitized)
        except (socket.timeout, TimeoutError):
            raise NebiusTimeoutError(f"Nebius Token Factory model query timed out after {self.timeout_seconds}s.")
        except NebiusError:
            raise
        except Exception as e:
            raise NebiusAPIError(f"Nebius Token Factory model discovery failed: {self._sanitize(str(e))}")

    def get_available_nemotron_models(self) -> List[str]:
        """
        Discovers active NVIDIA Nemotron models hosted on Nebius Token Factory
        using case-insensitive matching for 'nemotron'.
        """
        all_models = self.list_models()
        return [m for m in all_models if "nemotron" in m.lower()]

    def health_check(self) -> Dict[str, Any]:
        """
        Performs a lightweight health and connectivity check.
        Verifies configuration and queries the model catalog endpoint.
        """
        cfg = self.validate_config()
        if cfg["status"] != "VALID":
            return {
                "status": "UNHEALTHY",
                "reason": "Configuration invalid",
                "details": cfg
            }

        try:
            models = self.list_models()
            nemotrons = [m for m in models if "nemotron" in m.lower()]
            return {
                "status": "HEALTHY",
                "total_models": len(models),
                "nemotron_models_count": len(nemotrons),
                "active_model": self.model,
                "active_model_in_catalog": self.model in models
            }
        except Exception as e:
            return {
                "status": "DEGRADED",
                "reason": self._sanitize(str(e)),
                "details": cfg
            }

    # ==========================================================================
    # Chat Completion & Inference Engine
    # ==========================================================================

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: Optional[int] = 500,
        temperature: Optional[float] = 0.2,
        top_p: Optional[float] = 0.95,
        extra_body: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        survey_id: Optional[str] = None,
        operation_type: str = "statutory-assessment",
        service_caller: str = "mws-survey-server"
    ) -> NebiusResponse:
        """
        Executes an OpenAI-compatible chat completion against Nebius Token Factory.

        Guarantees:
        - Validates input message schema.
        - Bounded retries with exponential backoff and jitter for transient errors (429, 5xx, network drops).
        - Strict abort (no retries) on authentication failures (401/403) and validation errors (400/422).
        - Accurate latency and token usage extraction (no guessing when absent).
        - Non-blocking AIOps telemetry ingestion.
        """
        # 1. Input Validation
        if not messages or not isinstance(messages, list):
            raise NebiusValidationError("Invalid prompt: 'messages' must be a non-empty list of message dicts.")

        for idx, m in enumerate(messages):
            if not isinstance(m, dict) or "role" not in m or "content" not in m:
                raise NebiusValidationError(f"Invalid message format at index {idx}: must contain 'role' and 'content' keys.")

        # 2. Configuration Check
        config_audit = self.validate_config()
        if not config_audit["key_present"]:
            raise NebiusConfigurationError("Cannot execute completion: NEBIUS_API_KEY is not configured.")

        try:
            self._validate_base_url(self.base_url)
        except NebiusConfigurationError as ce:
            raise ce

        target_model = model or self.model
        if not target_model:
            raise NebiusConfigurationError("Cannot execute completion: target model is not configured.")

        endpoint = self._build_url("chat/completions")

        payload: Dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "max_tokens": max_tokens if max_tokens is not None else 500,
            "temperature": temperature if temperature is not None else 0.2,
            "top_p": top_p if top_p is not None else 0.95
        }
        if extra_body:
            payload.update(extra_body)

        body_bytes = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "LeeWuAI-NebiusProvider/2.0",
            "Accept": "application/json"
        }
        if request_id:
            headers["X-Request-ID"] = request_id

        # 3. Execution with Bounded Retries & Backoff
        attempt = 0
        last_exception: Optional[Exception] = None
        raw_body: Optional[str] = None
        latency_ms: float = 0.0

        while attempt <= self.max_retries:
            t0 = time.time()
            try:
                logger.info(
                    f"Dispatching inference to Nebius Token Factory [Model: {target_model}, "
                    f"MaxTokens: {payload['max_tokens']}, Attempt: {attempt + 1}/{self.max_retries + 1}]"
                )
                req = urllib.request.Request(endpoint, data=body_bytes, headers=headers)
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    raw_body = resp.read().decode("utf-8")
                    latency_ms = (time.time() - t0) * 1000.0
                    break  # Success!

            except urllib.error.HTTPError as he:
                latency_ms = (time.time() - t0) * 1000.0
                err_body = he.read().decode("utf-8", errors="replace")
                sanitized_body = self._sanitize(err_body)

                # Strict NO-RETRY on Authentication & Client Validation errors
                if he.code in (401, 403):
                    self._record_telemetry_failure(target_model, latency_ms, he.code, "FAILURE", sanitized_body, survey_id, operation_type, service_caller, attempt, error_category="AUTH_ERROR")
                    raise NebiusAuthenticationError(f"Nebius Token Factory Auth Error (HTTP {he.code}): {sanitized_body}", status_code=he.code)
                elif he.code in (400, 422):
                    self._record_telemetry_failure(target_model, latency_ms, he.code, "FAILURE", sanitized_body, survey_id, operation_type, service_caller, attempt, error_category="VALIDATION_ERROR")
                    raise NebiusValidationError(f"Nebius Token Factory Invalid Request (HTTP {he.code}): {sanitized_body}")

                # Transient errors: 429 (Rate Limit) or 5xx (Server Error)
                is_transient = (he.code == 429) or (500 <= he.code <= 599)
                if is_transient and attempt < self.max_retries:
                    attempt += 1
                    # Extract Retry-After header if present
                    retry_after_hdr = he.headers.get("Retry-After") if hasattr(he, "headers") else None
                    backoff = self._calculate_backoff(attempt, retry_after_hdr)
                    logger.warning(
                        f"Nebius Token Factory HTTP {he.code} on attempt {attempt}. Retrying in {backoff:.2f}s... Error: {sanitized_body}"
                    )
                    time.sleep(backoff)
                    continue

                # Final failure after exhausting retries
                err_cat = "RATE_LIMIT" if he.code == 429 else "SERVER_ERROR"
                self._record_telemetry_failure(target_model, latency_ms, he.code, "FAILURE", sanitized_body, survey_id, operation_type, service_caller, attempt, error_category=err_cat)
                if he.code == 429:
                    raise NebiusRateLimitError(f"Nebius Token Factory Rate Limit (HTTP 429): {sanitized_body}", status_code=429)
                else:
                    raise NebiusAPIError(f"Nebius Token Factory API Error (HTTP {he.code}): {sanitized_body}", status_code=he.code, response_body=sanitized_body)

            except (socket.timeout, TimeoutError):
                latency_ms = (time.time() - t0) * 1000.0
                if attempt < self.max_retries:
                    attempt += 1
                    backoff = self._calculate_backoff(attempt)
                    logger.warning(f"Nebius request timed out on attempt {attempt}. Retrying in {backoff:.2f}s...")
                    time.sleep(backoff)
                    continue
                self._record_telemetry_failure(target_model, latency_ms, 408, "TIMEOUT", f"Timeout ({self.timeout_seconds}s)", survey_id, operation_type, service_caller, attempt, error_category="TIMEOUT")
                raise NebiusTimeoutError(f"Nebius Token Factory request exceeded timeout threshold ({self.timeout_seconds}s).")

            except urllib.error.URLError as ue:
                latency_ms = (time.time() - t0) * 1000.0
                sanitized_msg = self._sanitize(str(ue))
                if attempt < self.max_retries:
                    attempt += 1
                    backoff = self._calculate_backoff(attempt)
                    logger.warning(f"Nebius network error on attempt {attempt}. Retrying in {backoff:.2f}s... ({sanitized_msg})")
                    time.sleep(backoff)
                    continue
                self._record_telemetry_failure(target_model, latency_ms, 503, "FAILURE", sanitized_msg, survey_id, operation_type, service_caller, attempt, error_category="SERVER_ERROR")
                raise NebiusAPIError(f"Nebius Token Factory network failure: {sanitized_msg}")

            except Exception as e:
                latency_ms = (time.time() - t0) * 1000.0
                sanitized_msg = self._sanitize(str(e))
                self._record_telemetry_failure(target_model, latency_ms, 500, "FAILURE", sanitized_msg, survey_id, operation_type, service_caller, attempt, error_category="CLIENT_ERROR")
                raise NebiusAPIError(f"Unexpected Nebius client error: {sanitized_msg}")

        # 4. Response Parsing and Validation
        if not raw_body:
            raise NebiusValidationError("Empty response body returned by Nebius Token Factory.")

        try:
            data = json.loads(raw_body)
        except Exception as je:
            raise NebiusValidationError(f"Invalid JSON returned by Nebius Token Factory: {je}")

        if not isinstance(data, dict):
            raise NebiusValidationError("Nebius Token Factory returned a non-dictionary JSON root.")

        if "choices" not in data or not isinstance(data["choices"], list) or len(data["choices"]) == 0:
            raise NebiusValidationError("Nebius Token Factory returned a payload without 'choices'.")

        choice = data["choices"][0]
        finish_reason = choice.get("finish_reason")
        msg = choice.get("message", {})

        content = msg.get("content")
        reasoning = msg.get("reasoning")

        # Handle reasoning model nuances (e.g. Nemotron-3-Nano reasoning field)
        if (content is None or not str(content).strip()) and reasoning:
            content = f"[Reasoning Summary]:\n{str(reasoning).strip()}"
        elif content is None:
            content = ""
        else:
            content = str(content).strip()

        if not content and not reasoning:
            raise NebiusValidationError(
                f"Nebius Token Factory returned an empty message (finish_reason: '{finish_reason}'). "
                f"Ensure max_tokens ({max_tokens}) provides sufficient budget."
            )

        actual_model = data.get("model", target_model)
        server_req_id = data.get("id") or request_id

        # 5. Extract Real Usage (No Estimation when absent)
        raw_usage = data.get("usage")
        usage_available = False
        prompt_tokens: Optional[int] = None
        completion_tokens: Optional[int] = None
        total_tokens: Optional[int] = None
        cached_tokens = 0

        if isinstance(raw_usage, dict) and raw_usage:
            usage_available = True
            prompt_tokens = raw_usage.get("prompt_tokens")
            completion_tokens = raw_usage.get("completion_tokens")
            total_tokens = raw_usage.get("total_tokens")
            if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
                total_tokens = prompt_tokens + completion_tokens

            if isinstance(raw_usage.get("prompt_tokens_details"), dict):
                cached_tokens = raw_usage["prompt_tokens_details"].get("cached_tokens", 0)

        # 6. Instrument Successful Telemetry Non-Blockingly
        ops = _get_ai_ops()
        if ops:
            ops.record_inference_event(
                provider="nebius",
                model_id=actual_model,
                latency_ms=latency_ms,
                http_status=200,
                status="SUCCESS",
                prompt_tokens=prompt_tokens or 0,
                completion_tokens=completion_tokens or 0,
                total_tokens=total_tokens or 0,
                cached_tokens=cached_tokens,
                request_id=server_req_id,
                survey_id=survey_id,
                operation_type=operation_type,
                service_caller=service_caller,
                retry_count=attempt,
                usage_source="api_response" if usage_available else "unavailable"
            )

        logger.info(
            f"Nebius inference complete. Model: {actual_model} | "
            f"Latency: {latency_ms:.1f}ms | "
            f"Tokens: Prompt={prompt_tokens if usage_available else 'N/A'}, "
            f"Completion={completion_tokens if usage_available else 'N/A'}, "
            f"Total={total_tokens if usage_available else 'N/A'}"
        )

        # Construct sanitized metadata dictionary
        safe_metadata = {
            "id": server_req_id,
            "created": data.get("created"),
            "model": actual_model,
            "object": data.get("object"),
            "system_fingerprint": data.get("system_fingerprint")
        }

        return NebiusResponse(
            content=content,
            model=actual_model,
            provider="nebius",
            request_id=server_req_id,
            input_tokens=prompt_tokens,
            output_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            finish_reason=finish_reason,
            usage_available=usage_available,
            raw_metadata=safe_metadata,
            reasoning=reasoning
        )

    # Backward compatibility alias
    complete = chat_completion

    def _calculate_backoff(self, attempt: int, retry_after_hdr: Optional[str] = None) -> float:
        """Computes exponential backoff with random jitter or honors Retry-After header."""
        if retry_after_hdr:
            try:
                val = float(retry_after_hdr)
                if val > 0:
                    return min(val, 30.0)
            except (ValueError, TypeError):
                pass
        # Exponential backoff: base * 2^(attempt-1) + jitter
        delay = self.retry_delay * (2 ** max(0, attempt - 1))
        jitter = random.uniform(0.05, 0.25)
        return min(delay + jitter, 15.0)

    def _record_telemetry_failure(
        self,
        model_id: str,
        latency_ms: float,
        http_status: int,
        status: str,
        error_msg: str,
        survey_id: Optional[str],
        operation_type: str,
        service_caller: str,
        retry_count: int,
        error_category: Optional[str] = None
    ) -> None:
        """Safely records failed telemetry events without interrupting execution."""
        ops = _get_ai_ops()
        if ops:
            try:
                ops.record_inference_event(
                    provider="nebius",
                    model_id=model_id,
                    latency_ms=latency_ms,
                    http_status=http_status,
                    status=status,
                    survey_id=survey_id,
                    operation_type=operation_type,
                    service_caller=service_caller,
                    retry_count=retry_count,
                    error_category=error_category,
                    error_message=self._sanitize(error_msg)
                )
            except Exception:
                pass

    # ==========================================================================
    # Domain Survey Workflow Helper
    # ==========================================================================

    def generate_survey_assessment(
        self,
        vessel_name: str,
        cargo_description: str,
        telemetry: Optional[Dict[str, Any]] = None,
        max_tokens: int = 600
    ) -> NebiusResponse:
        """
        High-level domain helper: Generates an authoritative Marine Warranty Surveyor (MWS)
        statutory cargo assessment for Port of Constanta discharge operations.
        """
        telemetry = telemetry or {}
        n2_pressure = telemetry.get("n2_pressure_bar", 0.32)
        impact_g = telemetry.get("impact_g", "0.28 G longitudinal / 0.34 G transverse / 0.19 G vertical")
        timestamp = telemetry.get("timestamp", time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()))

        system_prompt = (
            "You are LeeWu AI, Senior Marine Warranty Surveyor (MWS) in Port of Constanta. "
            "Generate authoritative, legally defensible cargo warranty survey notes under IMO CSS Code Annex 13. "
            "Be precise, technical, and concise."
        )

        user_prompt = (
            f"Perform cargo condition assessment for discharge nomination:\n"
            f"- Vessel: {vessel_name}\n"
            f"- Cargo: {cargo_description}\n"
            f"- Nitrogen Blanket: {n2_pressure} bar positive pressure\n"
            f"- Tri-axial Impact Recorder: {impact_g}\n"
            f"- Inspection Time: {timestamp}\n\n"
            f"Structure statutory note into 4 sections:\n"
            f"1. Executive Cargo Condition Summary\n"
            f"2. Environmental & Internal Atmosphere Verification (Nitrogen seal)\n"
            f"3. Transit Dynamics & Shock Recorder Evaluation (IMO CSS Code)\n"
            f"4. Statutory Warranty Recommendation (Clean Mate's Receipt determination)"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        return self.chat_completion(messages, max_tokens=max_tokens, temperature=0.2)


# ==============================================================================
# Backward Compatibility Class Alias
# ==============================================================================
NebiusTokenFactoryAdapter = NebiusProvider


# ==============================================================================
# CLI Diagnostics & Self-Test Utility
# ==============================================================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Nebius Token Factory AI Provider Utility")
    parser.add_argument("--check-config", action="store_true", help="Audit local Nebius configuration safely without leaking keys.")
    parser.add_argument("--list-models", action="store_true", help="Query Nebius Token Factory for deployed models.")
    parser.add_argument("--prompt", type=str, default=None, help="Send a test prompt to the configured Nemotron model.")
    parser.add_argument("--model", type=str, default=None, help="Override target model.")
    parser.add_argument("--health", action="store_true", help="Run provider health check.")
    args = parser.parse_args()

    provider = NebiusProvider()

    if args.check_config:
        cfg = provider.validate_config()
        print("=" * 60)
        print("NEBIUS TOKEN FACTORY CONFIGURATION AUDIT")
        print("=" * 60)
        print(f"Status:          {cfg['status']}")
        print(f"Base URL:        {cfg['base_url']}")
        print(f"Default Model:   {cfg['model']}")
        print(f"Timeout:         {cfg['timeout_seconds']}s")
        print(f"Max Retries:     {cfg['max_retries']}")
        print(f"API Key Present: {cfg['key_present']}")
        print(f"API Key Masked:  {cfg['key_masked']}")
        if cfg["errors"]:
            print("Errors:")
            for err in cfg["errors"]:
                print(f"  - {err}")
        print("=" * 60)

    elif args.health:
        h = provider.health_check()
        print("=" * 60)
        print(f"PROVIDER HEALTH: {h['status']}")
        print("=" * 60)
        print(json.dumps(h, indent=2))

    elif args.list_models:
        print("Fetching deployed models from Nebius Token Factory...")
        try:
            models = provider.list_models()
            nemotron_models = [m for m in models if "nemotron" in m.lower()]
            print(f"Total Models Available: {len(models)}")
            print(f"NVIDIA Nemotron Models ({len(nemotron_models)}):")
            for m in nemotron_models:
                print(f"  • {m}")
        except Exception as e:
            print(f"Error querying models: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.prompt:
        target = args.model or provider.model
        print(f"Sending prompt to Nebius Token Factory [Model: {target}]...")
        try:
            resp = provider.chat_completion(
                [{"role": "user", "content": args.prompt}],
                model=target,
                max_tokens=400
            )
            print("-" * 60)
            print(f"Response (Latency: {resp.latency_ms:.1f}ms, Finish: {resp.finish_reason}):")
            print(resp.content)
            print("-" * 60)
            print(f"Usage: {resp.usage} (Available: {resp.usage_available})")
        except Exception as e:
            print(f"Inference failed: {e}", file=sys.stderr)
            sys.exit(1)

    else:
        # Default behavior: run config audit
        cfg = provider.validate_config()
        print(f"Nebius Token Factory Provider initialized. Status: {cfg['status']} | Model: {cfg['model']} | Key: {cfg['key_masked']}")
