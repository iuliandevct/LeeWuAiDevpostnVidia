# Technical Architecture & Operations Guide: FlowForge, Homelab AI Stack & LeeWu Maritime

An exhaustive, production-grade technical manual covering the complete system architecture, flow topologies, Docker container orchestration, media engine pipelines, remote SSH operations, and Nebius Token Factory P&L economics.

---

## Table of Contents
1. [Executive Summary & Global Architecture](#1-executive-summary--global-architecture)
2. [FlowForge YouTube Studio Architecture (Node-RED + Ant Design)](#2-flowforge-youtube-studio-architecture-node-red--ant-design)
3. [Python Media Engine & FFmpeg Audio/Video Pipeline](#3-python-media-engine--ffmpeg-audiovideo-pipeline)
4. [Distributed Homelab Docker Compose Stack (13 Services)](#4-distributed-homelab-docker-compose-stack-13-services)
5. [Remote SSH Operations & Cross-Machine Deployment](#5-remote-ssh-operations--cross-machine-deployment)
6. [LeeWu AI Maritime Architecture: Gemini to Nebius Token Factory](#6-leewu-ai-maritime-architecture-gemini-to-nebius-token-factory)
7. [Unified Port Allocations, Network Topologies & Volumes](#7-unified-port-allocations-network-topologies--volumes)
8. [Production Maintenance, Diagnostics & Runbook](#8-production-maintenance-diagnostics--runbook)

---

## 1. Executive Summary & Global Architecture

The ecosystem consists of three interconnected subsystems operating together:
1. **FlowForge Creator Studio**: A lightweight, resilient orchestration system combining a React 19 + Ant Design frontend served directly by Node-RED 4.1 on port `1880`, with local Python 3.11 media engines and zero-loss JSON disk persistence.
2. **Homelab AI & Monitoring Stack**: A 13-service Docker container suite combining TIG monitoring (Telegraf, InfluxDB v2, Grafana), AI contextual memory (Plastic Labs Honcho), workflow automation (n8n), scalable backend (Supabase DB/Auth/Kong/Studio), and autonomous agent gateways (Nous Research Hermes Harness).
3. **LeeWu AI Maritime Cargo Platform**: An enterprise marine cargo inspection and automated surveying engine upgraded from Google Gemini to NVIDIA-accelerated models via **Nebius Token Factory**, tracked under an integrated departmental P&L ledger.

### Global System Topology

```mermaid
graph TB
    subgraph Client_Tier["Client Interaction Tier"]
        UI["React 19 + Ant Design (Port 1880/)"]
        NR_ADMIN["Node-RED Editor (Port 1880/admin)"]
        TG_CLIENT["Telegram App (@iwillbekingbot)"]
        GRAF_UI["Grafana Dashboards (Port 3001)"]
        SU_STUDIO["Supabase Studio (Port 3002)"]
    end

    subgraph Orchestration_Tier["Local Runtime Orchestration (Node-RED)"]
        NR_SRV["Node-RED Core (127.0.0.1:1880)"]
        API_ROUTER["API Router & Flow Dispatcher"]
        GLOBAL_CTX["functionGlobalContext (fs, path, cp, env)"]
        DISK_STORE[("Local Disk JSON Storage\ndata/jobs.json | data/planner.json")]
    end

    subgraph Media_Engine_Tier["Media Engines & Local Microservices"]
        PY_MEDIA["scripts/media_tools.py (Python 3.11 / uv)"]
        FFMPEG["FFmpeg 9.0 Full Build (Gyan.dev)"]
        VEO_WORKER["Docker Video Worker (:3000 / Veo & Flow Bridge)"]
    end

    subgraph Homelab_Docker_Stack["Dockerized Homelab Stack (Target Laptop)"]
        subgraph Monitoring_Subsystem["TIG Monitoring Stack"]
            TELEGRAF["Telegraf 1.30 Agent"]
            INFLUX["InfluxDB 2.7 (Port 8086)"]
            GRAFANA["Grafana (Port 3001)"]
        end

        subgraph Core_Data_Subsystem["Core Database & Cache"]
            PG["PostgreSQL 15 + pgvector (Port 5432)"]
            REDIS["Redis 7 Alpine (Port 6379)"]
        end

        subgraph Automation_AI_Subsystem["Automation & Agent Harness"]
            N8N["n8n Automation Engine (Port 5678)"]
            HONCHO_API["Honcho API (Port 8018)"]
            HONCHO_DERIVER["Honcho Deriver Worker"]
            HERMES["Hermes Agent & Gateway (Port 8642/9119)"]
        end

        subgraph Supabase_Core_Subsystem["Supabase Backend"]
            KONG["Kong Gateway (Port 8000)"]
            GOTRUE["GoTrue Auth Service"]
            POSTGREST["PostgREST API Service"]
            STUDIO["Supabase Studio (Port 3002)"]
        end
    end

    subgraph Cloud_AI_Tier["Cloud Infrastructure & Model Inference"]
        NEBIUS["Nebius Token Factory\n(NVIDIA H100 / L40S Cluster)"]
        GEMINI["Google Gemini API (Veo / Flash)"]
        TAVILY["Tavily Search API (Maritime Domain)"]
    end

    UI -->|HTTP GET/POST /api/*| NR_SRV
    NR_SRV --> API_ROUTER
    API_ROUTER --> GLOBAL_CTX
    GLOBAL_CTX -->|Read / Write| DISK_STORE
    GLOBAL_CTX -->|spawn uv run| PY_MEDIA
    PY_MEDIA --> FFMPEG
    NR_SRV -->|Health Check :3000| VEO_WORKER

    TELEGRAF -->|Docker socket / System stats| INFLUX
    INFLUX -->|Flux Query Engine| GRAFANA
    HONCHO_API --> PG
    HONCHO_API --> REDIS
    HONCHO_DERIVER --> HONCHO_API
    N8N --> PG
    HERMES --> HONCHO_API
    HERMES --> TG_CLIENT

    KONG --> POSTGREST
    KONG --> GOTRUE
    POSTGREST --> PG
    GOTRUE --> PG

    HERMES --> NEBIUS
    PY_MEDIA -.->|Future Model Hook| NEBIUS
    VEO_WORKER --> GEMINI
```

---

## 2. FlowForge YouTube Studio Architecture (Node-RED + Ant Design)

### 2.1 Backend Runtime Design
Node-RED acts as a zero-latency, event-driven API gateway and static file server. Rather than running a heavyweight Express server, Node-RED hosts both the REST endpoints and the production assets built with Vite:

- **Host & Port**: `127.0.0.1:1880`
- **Static Assets Root (`httpStatic`)**: `path.resolve(__dirname, '..', 'dist')`
- **Administrative Editor (`httpAdminRoot`)**: `/admin`
- **Application Endpoints (`httpNodeRoot`)**: `/`

#### Configuration (`node-red/settings.cjs`)
```javascript
const path = require('node:path');

module.exports = {
  uiPort: Number(process.env.NODE_RED_PORT || 1880),
  uiHost: '127.0.0.1',
  httpAdminRoot: '/admin',
  httpNodeRoot: '/',
  httpStatic: path.resolve(__dirname, '..', 'dist'),
  flowFile: 'flows.json',
  contextStorage: {
    default: { module: 'localfilesystem' },
    memoryOnly: { module: 'memory' },
  },
  functionGlobalContext: {
    fs: require('node:fs'),
    path: require('node:path'),
    child_process: require('node:child_process'),
    env: process.env,
    projectRoot: path.resolve(__dirname, '..'),
  },
  functionTimeout: 15,
  logging: { console: { level: 'info', metrics: false, audit: false } },
};
```

### 2.2 API Specifications

| Method | Endpoint | Description | Payload / Response |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/health` | Service liveness, Node-RED & Python engine status | `{"ok":true,"runtime":"Node-RED 4.1 + Python 3.11"}` |
| `GET` | `/api/dashboard` | Aggregated projects, 7-day planner, integration health | `{"jobs":[...],"planner":{"slots":[...]},"integrations":{...}}` |
| `POST` | `/api/jobs` | Creates a new video production draft with atomic disk write | `{"topic":"...","format":"9:16","durationSeconds":30}` |
| `PATCH`| `/api/jobs/:id/status` | Advances lifecycle stage (`draft` $\rightarrow$ `ready` $\rightarrow$ `published`) | `{"status":"approved"}` |
| `POST` | `/api/jobs/:id/tts` | Spawns Python worker, generates audio, updates job entity | `{"lang":"ro"}` $\rightarrow$ `{"ok":true,"media":{"filename":"..."}}` |
| `POST` | `/api/tools/tts` | Direct synthesis playground for arbitrary strings | `{"text":"...","lang":"ro"}` $\rightarrow$ returns playable audio URL |
| `POST` | `/api/tools/suno`| Resolves Suno track UUID, fetches artwork and stream URL | `{"url":"https://suno.com/song/..."}` |
| `GET` | `/api/media/:file` | Streams raw audio/video with `Accept-Ranges: bytes` | Audio buffer stream with `audio/mpeg` header |
| `POST` | `/api/planner/schedule`| Binds a project entity to a fixed editorial slot | `{"slotId":"slot_2026-10-30_0900","item":{...}}` |
| `POST` | `/api/planner/clear`| Unbinds and frees an editorial slot | `{"slotId":"slot_2026-10-30_0900"}` |

### 2.3 Ant Design Frontend (`src/App.jsx`)
The UI is structured as a single-page responsive dashboard using Ant Design 6 components:
- **Overview**: Real-time KPI statistics (Total, Active Pipeline, Awaiting Review, Published), rapid timeline view, and recent production jobs.
- **Production (`projects`)**: Complete tabular registry with multi-status sorting, quick filters, and an inspection Drawer with audio preview and one-click Python voice synthesis.
- **AI & Media Studio (`studio`)**: Dual-pane workspace offering direct TTS voice synthesis (Romanian AI Natural, US English, UK English) and Suno CDN metadata extraction.
- **Editorial Planner (`planner`)**: 28-slot matrix representing 7 consecutive calendar days (fixed intervals: 09:00, 12:00, 18:00, 21:00) with modal assignment.
- **Integrations (`integrations`)**: Heartbeat monitor for Node-RED, Python 3.11, local FFmpeg, Docker Video Worker, YouTube API, and Telegram gateway, with direct deep link to the Node-RED editor.

---

## 3. Python Media Engine & FFmpeg Audio/Video Pipeline

All media generation tasks are executed natively using Python 3.11 managed via Astral's `uv` package runner. This guarantees consistent sub-second cold starts without maintaining cumbersome virtual environment paths manually.

### 3.1 Text-To-Speech (TTS) Synthesis Sequence

```mermaid
sequenceDiagram
    autonumber
    actor User as Surveyor / Content Creator
    participant UI as React + Ant Design (Port 1880)
    participant NR as Node-RED Function Node
    participant UV as uv run python
    participant PY as scripts/media_tools.py
    participant TTS as Google / Edge Neural TTS Endpoint
    participant FFMPEG as System FFmpeg & FFprobe
    participant DISK as data/media/

    User->>UI: Clicks "Generează Narațiune TTS"
    UI->>NR: POST /api/jobs/:id/tts
    NR->>NR: Load project prompt from data/jobs.json
    NR->>UV: execFile("uv", ["run", "python", "scripts/media_tools.py", "tts", ...])
    UV->>PY: Invokes generate_tts(text, lang)
    PY->>PY: Regex sentence boundary segmentation (<= 140 chars)
    loop For each chunk
        PY->>TTS: GET translate_tts?tl=ro&q=chunk
        TTS-->>PY: Binary MP3 chunk buffer
    end
    alt Single Chunk
        PY->>DISK: Write directly to data/media/tts_{ts}.mp3
    else Multiple Chunks
        PY->>DISK: Write temporary part files
        PY->>DISK: Generate concat manifest (list_{ts}.txt)
        PY->>FFMPEG: ffmpeg -y -f concat -safe 0 -i list.txt -c copy output.mp3
        FFMPEG-->>PY: Concatenation complete (Exit code 0)
        PY->>DISK: Unlink manifest & temp chunks
    end
    PY->>FFMPEG: ffprobe -show_entries format=duration output.mp3
    FFMPEG-->>PY: Extracted duration: 4.80s
    PY-->>UV: stdout: JSON {"ok":true,"filename":"tts_...mp3","duration":4.8}
    UV-->>NR: ChildProcess on('close', code 0)
    NR->>DISK: Persist audioUrl to data/jobs.json
    NR-->>UI: HTTP 200 OK {"ok":true,"job":{...}}
    UI->>User: Displays audio player & enables "Play"
```

### 3.2 Subtitle Generation & Viral Captioning Preset (`captions-engine.mjs`)
For vertical short-form video assembly, subtitles are styled dynamically using the Advanced SubStation Alpha (`.ass`) specification:
- **Typography**: Bold uppercase Montserrat / Impact / Arial Black
- **Color Profiles**: Alex Hormozi Gold (`&H0000FFFF`), Cyberpunk Cyan (`&H00FFFF00`), TikTok Neon Green (`&H0000FF66`)
- **Word Chunking**: Sentences are grouped into 2 to 4 words per display chunk with millisecond timestamp offsets:
  $$\text{Chunk Duration} = \frac{\text{Total Audio Duration}}{\text{Number of Chunks}}$$
- **Burn-In Filter**:
  ```bash
  ffmpeg -i video.mp4 -vf "ass=captions.ass" -c:v libx264 -crf 18 -preset fast -c:a copy final_short.mp4
  ```

---

## 4. Distributed Homelab Docker Compose Stack (13 Services)

The stack located at `C:\Users\PC\Downloads\docker-stack\compose.yaml` coordinates 13 services across four architectural domains:

```
+----------------------------------------------------------------------------------------------------+
|                                    HOMELAB DOCKER COMPOSE STACK                                    |
+--------------------------+----------------------------+------------------------+-------------------+
|  1. MONITORING (TIG)     |  2. AI STATE & MEMORY      |  3. CORE BACKEND       |  4. AUTOMATION    |
|  - InfluxDB 2.7 (:8086)  |  - Honcho API (:8018)      |  - Postgres 15 (:5432) |  - n8n (:5678)    |
|  - Telegraf 1.30 (Host)  |  - Honcho Deriver (Worker) |  - PostgREST REST API  |  - Hermes Agent   |
|  - Grafana (:3001)       |  - Redis 7 (:6379)         |  - GoTrue Auth         |    (:8642 / :9119)|
|                          |                            |  - Kong Gateway (:8000)|                   |
|                          |                            |  - Studio UI (:3002)   |                   |
+--------------------------+----------------------------+------------------------+-------------------+
```

### 4.1 Service Breakdown & Container Specifications

#### Subsystem 1: Core Database & Cache
1. **`postgres` (`pgvector/pgvector:pg15`)**:
   - Primary relational database with vector search capabilities (`pgvector`).
   - Mapped volume: `postgres_data:/var/lib/postgresql/data`.
   - Initialization: Mounts `./init-scripts/01-init-databases.sql` to automatically provision `n8n` and `honcho` databases and activate vector extensions (`vector`, `pgcrypto`, `uuid-ossp`).
   - Healthcheck: `pg_isready -U postgres` every 5s.
2. **`redis` (`redis:7-alpine`)**:
   - In-memory data store for Honcho session cache and agent state synchronization.
   - Command: `redis-server --appendonly yes` with persistent volume `redis_data:/data`.

#### Subsystem 2: Monitoring (TIG Stack)
3. **`influxdb` (`influxdb:2.7-alpine`)**:
   - High-throughput time-series database.
   - Port: `8086:8086`.
   - Initialized automatically via environment variables: Organization `homelab`, Bucket `monitoring`, Admin Token `admin-token-super-secret-2026`.
4. **`telegraf` (`telegraf:1.30-alpine`)**:
   - Metrics collection daemon running with read-only mounts to host filesystems (`/:/hostfs:ro`) and the Docker daemon socket (`/var/run/docker.sock:ro`).
   - Collects per-container memory/CPU/network metrics and host telemetry every 10s.
5. **`grafana` (`grafana/grafana:latest`)**:
   - Monitoring dashboard visualizer on port `3001:3000`.
   - Includes automatic provisioning (`./grafana/provisioning/datasources/influxdb.yaml`) that binds InfluxDB v2 via Flux query syntax without manual UI configuration.

#### Subsystem 3: AI Memory & Autonomous Agents
6. **`honcho-api` (`ghcr.io/plastic-labs/honcho:latest`)**:
   - State and dialectic memory engine for LLM agents.
   - Port: `8018:8000`.
   - Connects to Postgres via `postgresql+psycopg://postgres:postgres123@postgres:5432/honcho`.
7. **`honcho-deriver` (`ghcr.io/plastic-labs/honcho:latest`)**:
   - Background worker running `python -m src.deriver` to parse interactions, create user representations, and extract semantic context.
8. **`hermes-agent` (`nousresearch/hermes-agent:latest`)**:
   - Nous Research autonomous agent harness and Telegram gateway.
   - Ports: `8642:8642` (Gateway API), `9119:9119` (Agent Dashboard).
   - Volume: `hermes_data:/opt/data` for persistent skills, memories, and configuration.

#### Subsystem 4: Automation & Supabase Core
9. **`n8n` (`docker.n8n.io/n8nio/n8n:latest`)**:
   - Low-code workflow automation orchestrator on port `5678:5678`.
   - Persistent volume `n8n_data:/home/node/.n8n`, backed by the internal Postgres database.
10. **`supabase-rest` (`postgrest/postgrest:v12.0.1`)**:
    - Converts PostgreSQL schemas into OpenAPI/REST endpoints automatically.
11. **`supabase-auth` (`supabase/gotrue:v2.158.1`)**:
    - JWT-based authentication microservice.
12. **`supabase-kong` (`kong:2.8.1-alpine`)**:
    - Declarative API Gateway on port `8000:8000` (`./kong/kong.yml`) unifying REST (`/rest/v1/`), Auth (`/auth/v1/`), and Studio endpoints.
13. **`supabase-studio` (`supabase/studio:20240405-59b4333`)**:
    - Web management interface for table browsing, SQL execution, and schema inspection on port `3002:3000`.

---

## 5. Remote SSH Operations & Cross-Machine Deployment

You can manage the target laptop directly from this terminal session over SSH.

### 5.1 Deployment Topology

```
+------------------------------------+           SSH / SCP (Port 22)           +------------------------------------+
|        CURRENT WORKSTATION         | --------------------------------------> |           TARGET LAPTOP            |
|  - C:\Users\PC\Downloads\          |                                         |  - Linux / macOS / Windows         |
|    docker-stack/                   |                                         |  - Docker Engine & Compose         |
+------------------------------------+                                         +------------------------------------+
```

### 5.2 Step-by-Step Remote Execution Workflow

#### Step 1: Copy Stack to Target Laptop
```powershell
# Copy the entire directory over SCP
scp -r C:\Users\PC\Downloads\docker-stack user@TARGET_IP:~/docker-stack
```

#### Step 2: Launch Stack Remotely
```powershell
# Execute docker compose remotely via SSH
ssh user@TARGET_IP "cd ~/docker-stack && docker compose up -d"
```

#### Step 3: Verify Container Health Remotely
```powershell
# Check running status of all 13 services
ssh user@TARGET_IP "cd ~/docker-stack && docker compose ps"
```

#### Step 4: Stream Live Logs Remotely
```powershell
# Stream logs from a specific container (e.g. hermes-agent or n8n)
ssh user@TARGET_IP "cd ~/docker-stack && docker compose logs -f hermes-agent"
```

#### Step 5: Graceful Teardown / Restart
```powershell
# Restart stack remotely
ssh user@TARGET_IP "cd ~/docker-stack && docker compose restart"

# Stop stack preserving all persistent volumes
ssh user@TARGET_IP "cd ~/docker-stack && docker compose down"
```

---

## 6. LeeWu AI Maritime Architecture: Gemini to Nebius Token Factory

### 6.1 Architectural Upgrade Rationale

> **Executive Statement:**
> *"Initially, LeeWu AI relied on Google Gemini for AI-powered maritime cargo image processing and report generation. By integrating NVIDIA-powered models through Nebius Token Factory, we significantly upgraded our AI architecture, gaining a more cost-effective and performance-oriented approach to model selection and deployment. This transition enables us to optimize inference costs, improve processing workflows, and scale AI-assisted cargo inspections. Nebius has helped us move toward a more flexible, production-ready architecture, bringing us closer to our vision of combining drone imagery, real-time cargo damage detection, and automated maritime reporting in one intelligent platform."*

### 6.2 Technical Benchmark Comparison

```mermaid
graph LR
    subgraph Legacy_Pipeline["Legacy Pipeline (Google Gemini)"]
        DRONE_1["4K Drone Images"] --> GEMINI_PRO["Google Gemini 1.5 Pro API"]
        GEMINI_PRO -->|Latency: ~850ms\nCost: $0.92 / batch| LEGACY_REP["Static Markdown Report"]
    end

    subgraph Nebius_NVIDIA_Pipeline["Upgraded Pipeline (Nebius Token Factory)"]
        DRONE_2["4K Drone Video Stream"] --> NEBIUS_VISION["nvidia/nemotron-vision-4b\n(Nebius Token Factory)"]
        NEBIUS_VISION -->|Latency: ~240ms\nCost: $0.32 / batch\n(-65% cost)| DAMAGE_DETECT["Real-Time Damage Detection\n(Rust, ISO Corner Cracks)"]
        DAMAGE_DETECT --> DNV_CHECK{"IMO CSS Annex 13 &\nDNV-ST-N001 Rules Engine"}
        DNV_CHECK -->|Compliant Data| NEBIUS_LLM["nvidia/llama-3.1-nemotron-70b\n(Nebius Token Factory)"]
        NEBIUS_LLM --> FINAL_REPORT["Automated Maritime Survey Report\n(PDF / P&I Club Format)"]
    end
```

### 6.3 P&L Financial Integration (`SURVEY_CARGO`)
The transition is reflected in the active financial accounting database (`data/cabinet/cabinet.db`):

| P&L Metric | Value (RON) | Operational Context |
| :--- | :--- | :--- |
| **Gross Revenue** | **79,000.00 RON** | 4 Active Cargo Projects (Discharge survey, Sea-fastening audit, Drone inspection, AI report) |
| **Direct Costs** | **7,700.00 RON** | Authorized surveyor attendance, port terminal access, NDT welding inspections |
| **Indirect Costs**| **2,300.00 RON** | Calibration of laser distance meters, dynamometers, and PPE gear |
| **AI Token Cost (Nebius)** | **2.58 RON** | **469,504 Tokens processed** across drone imagery classification and report drafting |
| **Gross Margin** | **90.3%** | Revenue minus direct costs (71,300.00 RON) |
| **Operating EBITDA** | **68,997.42 RON** | **87.3% Net Operating Margin** |

#### Cost Center Structure
- `AI-NEBIUS-NVIDIA` (`cc-ai-01`): Cloud GPU cluster allocation and Token Factory inference expenses.
- `SRV-AI-INSP` (`cc-srv-03`): Revenue and expenditures for automated drone inspections and computerized visual defect verification.
- `SRV-MAR` (`cc-srv-01`): Statutory marine cargo discharge and condition inspection billing.
- `SRV-ENG` (`cc-srv-02`): Heavy transport sea-fastening calculations and DNV engineering audits.

---

## 7. Unified Port Allocations, Network Topologies & Volumes

### 7.1 Port Allocation Matrix

To prevent socket binding collisions across both machines, ports are strictly divided by service:

| Port | Protocol | Service | Bind Address | Container / Runtime |
| :--- | :--- | :--- | :--- | :--- |
| **`1880`** | HTTP | FlowForge Studio & Node-RED API | `127.0.0.1` | Local Node.js / Node-RED |
| **`3000`** | HTTP | Video Worker (Docker Veo/Flow bridge) | `127.0.0.1` | Docker (Local) |
| **`3001`** | HTTP | Grafana Monitoring Dashboard | `0.0.0.0` | `stack-grafana` |
| **`3002`** | HTTP | Supabase Studio Database UI | `0.0.0.0` | `stack-supabase-studio` |
| **`5432`** | TCP  | PostgreSQL 15 + pgvector | `0.0.0.0` | `stack-postgres` |
| **`5678`** | HTTP | n8n Automation Workspace | `0.0.0.0` | `stack-n8n` |
| **`6379`** | TCP  | Redis 7 Alpine Cache | `0.0.0.0` | `stack-redis` |
| **`8000`** | HTTP | Supabase Kong API Gateway | `0.0.0.0` | `stack-supabase-kong` |
| **`8018`** | HTTP | Plastic Labs Honcho AI Memory API | `0.0.0.0` | `stack-honcho-api` |
| **`8086`** | HTTP | InfluxDB v2 Time-Series Engine | `0.0.0.0` | `stack-influxdb` |
| **`8443`** | HTTPS| Supabase Kong SSL Gateway | `0.0.0.0` | `stack-supabase-kong` |
| **`8642`** | HTTP | Hermes Agent Gateway API | `0.0.0.0` | `stack-hermes-agent` |
| **`9119`** | HTTP | Hermes Agent Web Dashboard | `0.0.0.0` | `stack-hermes-agent` |

### 7.2 Named Volume Persistence

| Volume Name | Storage Mount Inside Container | Preserved Data |
| :--- | :--- | :--- |
| `postgres_data` | `/var/lib/postgresql/data` | Relational tables for Supabase, n8n, and Honcho |
| `redis_data` | `/data` | Redis AOF append-only log and session keys |
| `influxdb_data` | `/var/lib/influxdb2` | High-frequency telemetry and engine measurements |
| `influxdb_config`| `/etc/influxdb2` | InfluxDB authentication configs and org settings |
| `grafana_data` | `/var/lib/grafana` | Custom user dashboards, alert rules, and preferences |
| `n8n_data` | `/home/node/.n8n` | Workflow definitions, credentials, and execution logs |
| `hermes_data` | `/opt/data` | Hermes agent skills, long-term memory, and session states |

---

## 8. Production Maintenance, Diagnostics & Runbook

### 8.1 Health Check Commands

#### Node-RED & FlowForge Studio
```powershell
# Verify Node-RED service and API health
curl.exe -s http://127.0.0.1:1880/api/health

# Verify Ant Design index frontend serving
curl.exe -s -I http://127.0.0.1:1880/
```

#### Python Media Engine
```powershell
# Run self-test diagnostics for Python 3.11 and FFmpeg
uv run python scripts/media_tools.py health

# Test direct TTS generation in Romanian
uv run python scripts/media_tools.py tts --text "Test sistem generare voce" --lang ro
```

#### Docker Stack Services (Remote or Local)
```bash
# Check status of all containers
docker compose ps

# Check Postgres liveness
docker exec stack-postgres pg_isready -U postgres

# Check InfluxDB ping
docker exec stack-influxdb influx ping

# Check Redis ping
docker exec stack-redis redis-cli ping
```

### 8.2 Troubleshooting Matrix

| Issue | Root Cause | Solution |
| :--- | :--- | :--- |
| `Port 1880 in use` | Previous Node.js or Node-RED process hung | Execute `Get-NetTCPConnection -LocalPort 1880` in PowerShell and terminate PID via `Stop-Process -Id <PID> -Force`. |
| `Postgres Connection Refused` | Container still initializing schema migrations | Check healthcheck status with `docker compose ps`. Container is marked `healthy` once `01-init-databases.sql` finishes. |
| `Grafana No Data in Dashboards`| Telegraf host path unmapped or token mismatch | Confirm `INFLUX_TOKEN` in `.env` matches `admin-token-super-secret-2026` in `grafana/provisioning/datasources/influxdb.yaml`. |
| `Honcho API 500 DB Error` | Database `honcho` not provisioned in Postgres | Execute `docker exec -it stack-postgres psql -U postgres -c "CREATE DATABASE honcho;"`. |
| `FFmpeg spawn EINVAL on Windows`| Node child_process spawning without shell flag | Set `{ shell: true }` when spawning `.cmd` binaries on Windows Node.js v24. |

---

*FlowForge Studio & LeeWu AI Platform • Standard Operating Documentation (SOP)*
