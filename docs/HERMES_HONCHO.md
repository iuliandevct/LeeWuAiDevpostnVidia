# Hermes + Honcho local

Hermes Agent 0.20.4 uses the existing Windows installation as its runtime, while its configuration, Telegram credentials, profile memory, logs, and gateway state live under `data/hermes/` in this project. The original Hermes home remains available as a rollback copy.

Honcho runs locally in Docker: API at `http://127.0.0.1:8018`, PostgreSQL with pgvector, Redis, and the background deriver. PostgreSQL and Redis data are bind-mounted under `stack/honcho/data/`, so they persist in this project. Gemini powers Hermes responses, Honcho reasoning, and Honcho embeddings. The Telegram allowlist was copied from the working Hermes setup.

The Honcho containers trust the machine's existing Avast root certificate through a mounted CA bundle; TLS certificate verification remains enabled.

## Start

From PowerShell:

```powershell
& 'C:\Users\PC\Desktop\the last super\stack\start-hermes.ps1'
```

This starts Honcho, stops the old Hermes gateway poller, and starts the project-configured Hermes gateway. The current gateway is connected to Telegram. Logs are in `data/hermes/logs/`.

To stop the project gateway only:

```powershell
& 'C:\Users\PC\Desktop\the last super\stack\stop-hermes.ps1'
```

To stop Honcho while retaining memory data:

```powershell
& 'C:\Users\PC\Desktop\the last super\stack\honcho\stop.ps1'
```

Do not use `docker compose down -v` unless you intend to erase the Honcho database.

## Storage and secrets

- Telegram bot token, allowed Telegram IDs, and Google API key: `data/hermes/.env`
- Gemini API key and Honcho database password: `stack/honcho/.env`
- Hermes config and Honcho connector config: `data/hermes/config.yaml`, `data/hermes/honcho.json`
- Durable Honcho data: `stack/honcho/data/postgres/` and `stack/honcho/data/redis/`
- Existing Hermes user profile copied to `data/hermes/memories/USER.md`

All secret and runtime data paths are excluded from Git. Keep the Telegram allowlist in place; only approved Telegram IDs can reach the bot.

## Google Flow video generation

The Google Flow web application has no documented official API for an unattended local pipeline. The project can use Flow interactively, but automated video jobs should use a documented Google video API (Gemini/Veo) unless Google publishes a supported Flow API. The current video worker is separate from Hermes and is not an API integration with the Flow website.
