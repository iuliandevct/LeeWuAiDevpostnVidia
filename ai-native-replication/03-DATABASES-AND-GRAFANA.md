# Databases and Grafana

## PostgreSQL 15

Run the native Supabase-compatible database on port `54322`, separately from
any existing PostgreSQL installation:

```bash
/usr/local/opt/postgresql@15/bin/postgres \
  -D /usr/local/var/postgresql@15 \
  -p 54322 \
  -h 127.0.0.1
```

Create the configured role and database, then apply:

```text
supabase/migrations/001_multitenant_foundation.sql
supabase/migrations/002_automaton_activity.sql
```

Use `psql -v ON_ERROR_STOP=1`. Never put database passwords directly into
documentation or shell history.

Acceptance query:

```sql
select slug, status
from public.companies
order by slug;
```

Expected company slugs:

```text
biteight
bitsense
atdeco
vice_engineering
lp_mar
gabinfy
accounting
lawyers
```

## MariaDB and WordPress

Create a dedicated database and local-only user. Install WordPress into a
user-owned folder and protect `wp-config.php`:

```bash
chmod 600 PATH_TO_WORDPRESS/wp-config.php
```

If WP-CLI reaches the PHP 128 MB extraction limit, invoke WP-CLI with a
temporary higher memory limit. Do not change the global PHP limit solely for
installation.

## InfluxDB 2 and Telegraf

Initialize InfluxDB with a fresh organization, bucket, user, password, and
token for each destination.

Telegraf output:

```toml
[[outputs.influxdb_v2]]
  urls = ["http://127.0.0.1:8086"]
  token = "$INFLUXDB_TOKEN"
  organization = "$INFLUXDB_ORG"
  bucket = "$INFLUXDB_BUCKET"
```

## Grafana

Configure native data sources:

- InfluxDB: `http://127.0.0.1:8086`
- PostgreSQL: `127.0.0.1:54322`

Import these dashboards into the `Local Stack` folder:

```text
Local Stack Observability
Cloudflare — LeeWu Maritime Services
Conway Automaton Observability
```

Store datasource passwords and tokens through Grafana secure fields. Do not
embed them in dashboard JSON.
