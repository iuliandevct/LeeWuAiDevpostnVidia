#!/bin/zsh
set -eu

HERMES_ENV="${HOME}/.hermes/.env"
VIBE_ROOT="${VIBE_TRADING_ROOT:-${HOME}/Downloads/ai-containers-stack/vibe-trading-src}"
VIBE_PYTHON="${VIBE_ROOT}/.venv/bin/python"

if [[ ! -x "${VIBE_PYTHON}" ]]; then
  print -u2 "VibeTrading virtual environment is missing: ${VIBE_PYTHON}"
  exit 1
fi

if [[ -f "${HERMES_ENV}" ]]; then
  set -a
  source "${HERMES_ENV}"
  set +a
fi

if [[ -z "${GEMINI_API_KEY:-}" && -n "${GOOGLE_API_KEY:-}" ]]; then
  export GEMINI_API_KEY="${GOOGLE_API_KEY}"
fi

if [[ -z "${GEMINI_API_KEY:-}" ]]; then
  print -u2 "GEMINI_API_KEY/GOOGLE_API_KEY is not configured."
  exit 1
fi

cd "${VIBE_ROOT}"
exec "${VIBE_PYTHON}" -m cli serve --host 127.0.0.1 --port 8899
