# Harta liniară a sistemelor

Actualizat: 26 iulie 2026

## 1. Mac-ul principal

Mac-ul rulează Docker Desktop și proiectul:

`/Users/iulian/Downloads/ai-containers-stack`

Docker Compose pornește toate serviciile descrise mai jos. Vibe Trading există în
stack, dar nu face parte din replica planificată pentru al doilea Mac.

## 2. Fluxul de observabilitate locală

```text
Mac / containere
       |
       v
Telegraf ----> InfluxDB ----> Grafana
                                  |
                                  +--> Local Stack Observability
                                  +--> Cloudflare — LeeWu Maritime Services
                                  +--> Conway Automaton Observability
```

- Telegraf colectează CPU, memorie, disc, rețea și procese.
- InfluxDB păstrează seriile temporale locale.
- Grafana rulează la `http://localhost:3000`.
- Dashboardul Conway citește direct tabelul Supabase `automaton_activity`.

## 3. Fluxul Supabase

```text
Supabase Studio ---> Postgres Meta ---> Supabase PostgreSQL
                                            |
                                            +--> companies
                                            +--> projects
                                            +--> supabase_instances
                                            +--> project_instances
                                            +--> company_members
                                            +--> automaton_activity
```

Adrese:

- PostgreSQL: `localhost:54322`
- Studio: `http://localhost:54323`

Companii configurate:

1. `biteight`
2. `bitsense`
3. `atdeco`
4. `vice_engineering`
5. `lp_mar`
6. `gabinfy`
7. `accounting`
8. `lawyers`

Modelul acceptă proiecte comerciale comune și instanțe Supabase dedicate.

## 4. Conway Automaton

```text
Conway container (izolat, SETUP_PENDING)
       |
       | container heartbeat
       v
Automaton Supabase Bridge
       |
       v
public.automaton_activity
       |
       +--> Grafana Automaton Observability
       +--> Conway local webpage
       +--> Obsidian Trading / Conway metrics layer
```

Componente:

- `stack-automaton`: runtime Node.js Conway, non-root, read-only root filesystem.
- `stack-automaton-supabase-bridge`: scrie heartbeat la 30 secunde.
- `public.automaton_activity`: jurnal separat, append-only.
- pagină locală: `http://localhost:8090/automaton.html`
- dashboard: `http://localhost:3000/d/automaton-observability`

Conway nu are încă wallet finanțat, genesis prompt sau buclă autonomă activă.
Auto-replicarea este oprită.

## 5. Agenții locali

```text
Hermes --------> gateway + dashboard + rutare AI
OpenClaw ------> gateway local + workspace
Codex --------> dezvoltare, administrare și MCP Cloudflare
Conway --------> agent autonom izolat, încă în setup
```

Adrese:

- Hermes gateway: `http://localhost:8642`
- Hermes dashboard: `http://localhost:9119`
- OpenClaw: `http://localhost:18789`

Hermes și Jay Social Media sunt vizibile în ramura `AUTOMATION` din Obsidian.

## 6. Cloudflare

```text
Codex MCP OAuth ---> Cloudflare API
                         |
                         +--> leewuai.ro
                         +--> 16 DNS records
                         +--> tunnel pnl-web
```

Cloudflare este reprezentat numai în ramura `INFRA`.

Inventarul Cloudflare este vizibil în Grafana. Pentru metrici Cloudflare continue
este necesar un user API token read-only separat de OAuth-ul Codex.

## 7. Obsidian Graph și Graph API

```text
Docker socket (read-only) ---> Graph API :8091
                                      |
                                      v
Obsidian Graph :8090
```

Obsidian afișează:

- `TRADING`: Ethereum, Conway/Autobot și layer-ul de metrici Conway;
- `AUTOMATION`: Hermes și Jay Social Media;
- `INFRA`: Cloudflare;
- `CLIENTS`: laptopul HP LeeWu Maritime ca nod remote;
- restul instrumentelor și sistemelor locale.

Pulsurile animate:

- auriu: Trading/Conway;
- roz: Automation/Hermes/Jay;
- portocaliu: Cloudflare/INFRA.

## 8. WordPress

```text
Browser ---> WordPress :8081 ---> MariaDB
```

Datele WordPress sunt persistate în volume Docker separate.

## 9. Accesul de pe alt calculator

Serviciile sunt în prezent locale. Nu trebuie publicate direct prin port forwarding.

Pentru accesul laptopului HP LeeWu Maritime sau al celui de-al doilea Mac:

```text
Calculator remote ---> VPN / Cloudflare Tunnel ---> serviciu local autorizat
```

OAuth-ul Codex și secretele `.env` trebuie configurate separat pe fiecare Mac.

## 10. Fișierele importante

```text
docker-compose.yml
.env
README.md
SYSTEM_MAP.md
STATUS.md
REPLICATE_TO_OTHER_MAC.md
supabase/migrations/
grafana/dashboards/
grafana/provisioning/
obsidian-graph/
graph-api/
automaton-src/
automaton-bridge/
```
