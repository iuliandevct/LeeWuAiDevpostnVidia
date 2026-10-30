# AI Containers Stack

Docker Compose workspace for:

- Grafana, InfluxDB, Telegraf
- WordPress with MariaDB
- Supabase local base: Postgres, Studio, Postgres Meta
- Hermes Agent in a separate container
- OpenClaw in a separate container
- Conway Automaton in a hardened, isolated container
- Automaton-to-Supabase heartbeat bridge
- Vibe Trading in a separate container
- Obsidian-style graph webpage served from Downloads

## Start

```bash
cd /Users/iulian/Downloads/ai-containers-stack
docker compose up -d
```

## URLs

- Grafana: http://localhost:3000
- InfluxDB: http://localhost:8086
- WordPress: http://localhost:8081
- Supabase Studio: http://localhost:54323
- Supabase Postgres: localhost:54322
- Hermes gateway: http://localhost:8642
- Hermes dashboard: http://localhost:9119
- OpenClaw: http://localhost:18789
- Vibe Trading API: http://localhost:8899/docs
- Vibe Trading UI: http://localhost:5899
- Obsidian Graph: http://localhost:8090
- Obsidian Graph Live API: http://localhost:8091/status
- Maritime Knowledge API: http://localhost:8091/knowledge

## Maritime knowledge flow

The Second Brain graph includes a live `MARITIME AI` branch for the cargo-securing
knowledge base. Its Knowledge Flow panel polls the local API every five seconds and
shows the current document count, chunk count, embedding dimensions, and installed
Hermes skills directly from Supabase.

The reproducible components are included in this repository:

- `supabase/migrations/003_maritime_knowledge.sql` creates the vector knowledge tables and search function.
- `supabase/migrations/004_maritime_document_metadata.sql` adds source metadata used by the graph.
- `document-ingestion/` extracts supported office documents, chunks them, and generates local multilingual embeddings.
- `hermes-skills/` contains the MetaCAD and sea-fastening skills used to route maritime engineering requests.
- `social-media-agency/workflows/` contains reviewed n8n workflow sources imported from the dedicated agency repository.

Apply the maritime migrations in order, then follow `document-ingestion/README.md`
to ingest documents. The graph API reads database credentials from `.env`; secrets
must remain local and must not be committed.

Grafana provisions two dashboards in the `Local Stack` folder:

- `Local Stack Observability`
- `Cloudflare — LeeWu Maritime Services` (read-only inventory from the authorized Cloudflare MCP connection)

The Cloudflare OAuth grant belongs to Codex and is not copied into Grafana. Continuous
Cloudflare analytics requires a separate least-privilege user API token; keep it in
`.env`, never in a dashboard JSON or committed provisioning file.

## Conway Automaton

The `automaton` container is installed but intentionally remains in `SETUP_PENDING`
until its wallet, genesis prompt, creator address, API access, and financial limits
are explicitly configured. It runs non-root, without the Docker socket, with dropped
Linux capabilities and a read-only root filesystem.

`automaton-supabase-bridge` writes a heartbeat every 30 seconds to
`public.automaton_activity`. This confirms the container/Supabase connection without
granting the agent database credentials. Auto-replication is not enabled.

## Supabase multi-company model

`supabase/migrations/001_multitenant_foundation.sql` creates a shared tenant catalog:

- companies and commercial projects
- shared or dedicated project isolation
- a registry of local, cloud, and self-hosted Supabase instances
- project-to-instance mappings
- membership placeholders for the later Auth/RLS phase

Apply an idempotent migration to the running local database with:

```bash
docker compose exec -T supabase-db psql -U postgres -d postgres \
  -f /dev/stdin < supabase/migrations/001_multitenant_foundation.sql
```

## Important Notes

Edit `.env` before exposing this outside your laptop. The checked-in values are local development placeholders.

For Supabase API/Auth/Realtime, this compose file currently starts the local database, Studio, and Postgres Meta. If you want the full official Supabase self-hosted stack, add Kong, Auth, REST, Realtime, Storage, Imgproxy, and Analytics services.

Hermes is assumed to mean `nousresearch/hermes-agent:latest`. If you meant Facebook Hermes JS engine or another Hermes project, replace the `hermes` service image/command.

OpenClaw uses the official container image `ghcr.io/openclaw/openclaw:latest`.

Vibe Trading uses the PyPI package `vibe-trading-ai` inside a local Docker image built from `vibe-trading/Dockerfile`.

The Obsidian-style graph is copied from `/Users/iulian/Downloads/second-brain-graph-2.html` into `obsidian-graph/index.html` and served by Nginx.

## Useful Commands

```bash
docker compose ps
docker compose logs -f grafana
docker compose logs -f hermes
docker compose logs -f openclaw
docker compose logs -f vibe-trading
docker compose down
```

To remove persistent data too:

```bash
docker compose down -v
```
