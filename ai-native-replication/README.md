# AI Native Stack — replication package

Updated: 31 July 2026

This folder documents the native macOS deployment created from
`ai-containers-stack` on a machine that cannot run Docker virtualization.

It contains instructions only. It intentionally contains no passwords, API
keys, OAuth tokens, private SSH keys, database contents, logs, or `.env`
files.

## Documents

1. `01-INVENTORY.md` — installed components, ports, and known limitations.
2. `02-NATIVE-INSTALL.md` — native installation and service setup.
3. `03-DATABASES-AND-GRAFANA.md` — database migrations and dashboards.
4. `04-HERMES-TELEGRAM.md` — Hermes, Gemini, and Telegram configuration.
5. `05-SECOND-BRAIN-AND-SSH.md` — SSH and cross-Mac Second Brain integration.
6. `06-SECRETS-TRANSFER.md` — safe secret provisioning for each destination.
7. `07-ACCEPTANCE-CHECKLIST.md` — validation commands and expected results.
8. `08-HERMES-ACER-MIGRATION.md` — additive migration of Hermes memory,
   conversations, and skills from the Acer PC to the native Mac installation.

## Replication principle

Treat every destination as an independent installation:

- install packages from trusted sources;
- generate a new SSH key on each Mac;
- configure OAuth again on each Mac;
- use separate API keys and bot tokens where practical;
- never transfer credentials through Git or this documentation folder;
- bind services to localhost unless LAN access is explicitly required.

Vibe Trading is excluded, matching the second-Mac replication requirements.
Supabase Studio and Postgres Meta are not installed natively because the
official supported self-hosting path requires Docker. PostgreSQL and the
required application schema run natively.
