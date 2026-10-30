# Hermes and Telegram

## Install Hermes

Use the official installer and inspect it before execution:

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh \
  -o /tmp/hermes-install.sh
sh -n /tmp/hermes-install.sh
bash /tmp/hermes-install.sh \
  --skip-setup \
  --skip-browser \
  --non-interactive
```

Chromium was skipped because of compatibility concerns on the reference Mac.

Hermes layout:

```text
~/.hermes/                 configuration, secrets, data, logs
~/.hermes/hermes-agent/    source/runtime
~/.local/bin/hermes        command
```

Protect the environment file:

```bash
chmod 600 ~/.hermes/.env
```

## Gemini

Hermes accepts either:

```text
GOOGLE_API_KEY
GEMINI_API_KEY
```

Configure the provider and model:

```bash
hermes config set model.provider gemini
hermes config set model.default gemini-2.5-flash
```

Validate with a minimal one-shot request. A `429 RESOURCE_EXHAUSTED` response
means the key reached Google successfully but the project lacks quota or
prepaid billing.

## Telegram

Required variables:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_ALLOWED_USERS
```

Always set `TELEGRAM_ALLOWED_USERS`. Without an allowlist, Hermes denies users
by default; do not enable allow-all mode on a real bot.

Verify the bot with the official Telegram `getMe` method, without logging the
token.

Install and start the gateway:

```bash
hermes gateway install
hermes gateway start
hermes gateway status
```

Logs:

```text
~/.hermes/logs/gateway.log
~/.hermes/logs/gateway.error.log
```

Hermes intentionally ignores Telegram `/start` as a platform ping. Test with a
normal text message. Gateway connectivity and model-provider availability are
separate health checks.

## Skills

Create skills under:

```text
~/.hermes/skills/SKILL_NAME/
```

Each skill should include a focused `SKILL.md`, explicit trigger conditions,
safe defaults, input validation, and no embedded credentials.
