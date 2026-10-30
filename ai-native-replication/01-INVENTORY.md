# Installed inventory

## Native services

| Component | Version used | Port | Startup |
|---|---:|---:|---|
| Grafana OSS | 13.1.0 | 3000 | Homebrew service |
| InfluxDB | 2.9.1 | 8086 | Homebrew service |
| Telegraf | 1.39.2 | n/a | LaunchAgent |
| MariaDB | 12.3.2 | 3306 | Homebrew service |
| PHP | 8.5.8 | internal / 8081 | Homebrew + LaunchAgent |
| WordPress | 7.0.2 | 8081 | LaunchAgent |
| PostgreSQL | 15.18 | 54322 | LaunchAgent |
| Nginx | 1.31.3 | 8080 | Homebrew service |
| Obsidian-style graph | static | 8090 | LaunchAgent |
| Graph API | Python | 8091 | LaunchAgent |
| Hermes Agent | 0.19.0 | Telegram gateway | Hermes LaunchAgent |
| OpenClaw | 2026.7.1-2 | not started | global Node package |
| Conway Automaton | 0.2.1 | setup pending | global Node link |
| Repetier-Host | 1.2.1 | desktop app | `/Applications` |

## Local URLs

- Grafana: `http://localhost:3000`
- InfluxDB: `http://localhost:8086`
- WordPress: `http://localhost:8081`
- Obsidian Graph: `http://localhost:8090`
- Graph API: `http://localhost:8091/status`

## Security state

- Conway remains `SETUP_PENDING`.
- OpenClaw is installed but not onboarded or launched.
- Hermes Telegram access uses an explicit user allowlist.
- The Graph API exposes only service health metadata and allows CORS for the
  Second Brain website.
- Grafana is reachable over the LAN for the Second Brain integration. Do not
  expose it through router port forwarding.

## Known limitations

- Supabase Studio and Postgres Meta require the official Docker deployment and
  are not part of this native replica.
- Hermes can be online while its model provider is unavailable. Monitor both
  gateway health and provider billing/quota.
- The Second Brain integration currently uses LAN IP addresses. Prefer DHCP
  reservations, `.local` names, or a private VPN for durable addressing.
