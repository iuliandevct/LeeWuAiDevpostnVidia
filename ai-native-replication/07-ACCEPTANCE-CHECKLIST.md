# Acceptance checklist

## Packages and processes

```bash
brew services list
hermes --version
hermes gateway status
openclaw --version
automaton --version
```

Expected:

- Grafana, InfluxDB 2, MariaDB, PHP, and Nginx started;
- native LaunchAgents running;
- Hermes supervised by launchd;
- Conway installed but not autonomously activated.

## HTTP

```bash
curl -fsS http://127.0.0.1:3000/api/health
curl -fsS http://127.0.0.1:8086/health
curl -I http://127.0.0.1:8081/
curl -I http://127.0.0.1:8090/
curl -fsS http://127.0.0.1:8091/live
curl -fsS http://127.0.0.1:8091/status
```

Expected status codes:

```text
Grafana       200
InfluxDB      200
WordPress     200 or 302
Graph page    200
Graph API     200
```

## Databases

```bash
/usr/local/opt/postgresql@15/bin/pg_isready \
  -h 127.0.0.1 -p 54322
mariadb-admin ping
```

Verify eight company records in PostgreSQL and the WordPress database in
MariaDB.

## Grafana

Confirm:

- InfluxDB datasource succeeds;
- PostgreSQL datasource succeeds;
- `Local Stack` folder exists;
- all three required dashboards load.

## Hermes and Telegram

Confirm gateway log entries:

```text
telegram connected
Gateway running with 1 platform(s)
```

Send a normal message, not only `/start`. If delivery works but AI generation
does not, verify provider quota and billing.

## Second Brain

From the Second Brain Mac:

```bash
curl -fsS http://NATIVE_MAC_IP:3000/api/health
curl -fsS http://NATIVE_MAC_IP:8091/status
```

Expected native status:

```text
Jay Mac Pro · Grafana — online
Jay Mac Pro · Hermes  — online
```

Refresh the website and verify both rows appear and update automatically.

## Git safety

Before any commit:

```bash
git status -sb
git diff --check
git ls-files | grep -E '(^|/)(\\.env|auth\\.json)$'
```

The final command must produce no tracked secret files. Inspect every staged
diff before pushing.
