# Secrets and credentials

## Never include

Do not place any of the following in this folder, Git, screenshots, chat, or
dashboard JSON:

- Gemini, OpenAI, Anthropic, or OpenRouter API keys;
- Telegram bot tokens;
- Grafana, MariaDB, PostgreSQL, or WordPress passwords;
- InfluxDB tokens;
- Cloudflare OAuth tokens;
- `.env` files;
- `auth.json`;
- SSH private keys;
- database dumps containing personal or production data.

## Configure independently

On every destination:

1. generate new database passwords;
2. generate a new InfluxDB token;
3. create or restrict provider API keys;
4. configure a dedicated Telegram bot where practical;
5. set an explicit Telegram user allowlist;
6. authenticate Cloudflare MCP through OAuth again;
7. generate a new SSH keypair;
8. apply `chmod 600` to secret files.

## Safe transfer options

If an existing secret must be reused temporarily:

- use AirDrop between trusted Macs;
- use an encrypted removable drive;
- use a password manager with per-device access;
- rotate the secret immediately after migration.

Do not send credentials through ordinary chat. Any credential already pasted
into a conversation should be considered exposed and rotated.

## Template categories

Create a local `.env` containing only the categories required on that Mac:

```text
InfluxDB credentials and token
Grafana administrator credentials
WordPress/MariaDB credentials
PostgreSQL credentials
Hermes model-provider credentials
Hermes Telegram token and allowlist
OpenClaw token/provider credentials, if enabled
Local port overrides
```

Keep `.env` excluded in `.gitignore`.
