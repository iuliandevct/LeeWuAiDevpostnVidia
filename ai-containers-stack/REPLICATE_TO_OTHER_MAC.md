# Instrucțiuni pentru Codex: replicarea stack-ului pe al doilea Mac

## Obiectiv

Reproduce pe acest Mac stack-ul aflat pe Mac-ul sursă în:

`/Users/iulian/Downloads/ai-containers-stack`

Trebuie replicate toate componentele enumerate mai jos, cu o singură excepție:

**Nu instala, nu copia, nu construi și nu porni Vibe Trading.**

Nu copia credențiale Codex, tokenuri OAuth, chei API sau parole prin Git. Cere
utilizatorului transferul separat și sigur al fișierului `.env`, dacă este necesar.

## Componente care trebuie replicate

- Grafana
- InfluxDB
- Telegraf
- WordPress și MariaDB
- Supabase local: PostgreSQL, Postgres Meta și Studio
- Hermes Agent
- OpenClaw
- Conway Automaton and its Supabase heartbeat bridge
- Obsidian Graph
- Graph API pentru statusul live al serviciilor
- dashboardul Grafana `Local Stack Observability`
- dashboardul Grafana `Cloudflare — LeeWu Maritime Services`
- schema Supabase multi-companie
- conexiunea MCP Cloudflare, autentificată separat pe acest Mac

Exclude complet:

- serviciul `vibe-trading`
- serviciul `vibe-trading-ui`
- directoarele `vibe-trading/` și `vibe-trading-src/`
- volumul `vibe-trading-data`
- variabilele `VIBE_TRADING_*`

## Reguli de siguranță

1. Nu afișa în terminal conținutul `.env`, `auth.json`, tokenurile OAuth sau cheile API.
2. Nu copia directorul `~/.codex` de pe Mac-ul sursă.
3. Autentifică din nou MCP Cloudflare prin OAuth pe Mac-ul destinație.
4. Nu expune porturile stack-ului pe internet.
5. Pentru acces între rețele folosește Cloudflare Tunnel, Tailscale sau alt VPN.
6. Nu șterge volume sau date existente fără aprobarea explicită a utilizatorului.
7. Înainte de modificări, verifică dacă destinația conține deja un stack sau volume
   Docker cu aceleași nume.

## Etapa 1 — verificări pe Mac-ul destinație

Verifică:

```bash
uname -m
sw_vers
docker version
docker compose version
codex --version
git --version
```

Dacă Docker Desktop nu este instalat, oprește-te și cere aprobarea utilizatorului
pentru instalare. Pornește Docker Desktop și confirmă:

```bash
docker ps
```

## Etapa 2 — transferul fișierelor

Copiază de pe Mac-ul sursă directorul:

`/Users/iulian/Downloads/ai-containers-stack`

într-un director ales de utilizator pe Mac-ul destinație, de exemplu:

`~/Downloads/ai-containers-stack`

Nu copia:

```text
.env
vibe-trading/
vibe-trading-src/
**/__pycache__/
```

Poți folosi AirDrop, un SSD extern sau `rsync` printr-o conexiune privată. Nu publica
arhiva și nu o urca într-un repository public.

După transfer, verifică existența:

```text
docker-compose.yml
README.md
grafana/
telegraf/
supabase/
graph-api/
obsidian-graph/
```

## Etapa 3 — eliminarea Vibe Trading din copia destinație

Editează copia `docker-compose.yml` și elimină:

- serviciul `vibe-trading`
- serviciul `vibe-trading-ui`
- volumul `vibe-trading-data`

Elimină din README URL-urile și comenzile Vibe Trading. Nu modifica exemplarul de pe
Mac-ul sursă.

Validează rezultatul:

```bash
docker compose config --services
```

Lista nu trebuie să conțină `vibe-trading` sau `vibe-trading-ui`.

## Etapa 4 — configurarea secretelor

Creează `.env` pornind de la variabilele folosite în `docker-compose.yml`.

Preferabil, transferă `.env` existent prin AirDrop/SSD și păstrează permisiuni
restrictive:

```bash
chmod 600 .env
```

Alternativ, generează parole și tokenuri noi pentru destinație.

Categorii de variabile necesare:

- InfluxDB: utilizator, parolă, organizație, bucket și token
- Grafana: utilizator și parolă admin
- WordPress/MariaDB: baza, utilizatorii și parolele
- Supabase/Postgres: baza, utilizatorul și parola
- cheile locale Supabase anon/service-role existente
- Hermes: credentialele dashboardului și providerii AI folosiți
- OpenClaw: gateway token și providerii AI folosiți
- porturile locale, dacă valorile implicite sunt ocupate

Nu scrie valorile secretelor în acest document, în README sau în fișierele dashboard.

## Etapa 5 — corectarea căilor dependente de utilizator

Caută orice cale absolută rămasă:

```bash
rg -n '/Users/iulian|/Users/' .
```

În special, actualizează montarea socketului Docker din serviciul `graph-api`:

```yaml
volumes:
  - /Users/NUME_NOU/.docker/run/docker.sock:/var/run/docker.sock:ro
```

Folosește numele real al utilizatorului de pe Mac-ul destinație.

## Etapa 6 — pornirea stack-ului

Din directorul stack-ului:

```bash
docker compose config
docker compose pull
docker compose build graph-api
docker compose up -d
docker compose ps
```

Serviciile așteptate:

```text
grafana
influxdb
telegraf
wordpress
wordpress-db
supabase-db
supabase-meta
supabase-studio
hermes
openclaw
automaton
automaton-supabase-bridge
obsidian-graph
graph-api
```

Nu continua automat dacă un serviciu intră într-un restart loop. Citește întâi:

```bash
docker compose logs --tail=150 NUME_SERVICIU
```

## Etapa 7 — schema Supabase

Migrarea este:

`supabase/migrations/001_multitenant_foundation.sql`

Aplic-o idempotent:

```bash
docker compose exec -T supabase-db \
  psql -v ON_ERROR_STOP=1 -U postgres -d postgres -f /dev/stdin \
  < supabase/migrations/001_multitenant_foundation.sql
```

Verifică:

```bash
docker compose exec -T supabase-db \
  psql -U postgres -d postgres -P pager=off \
  -c "select slug, status from public.companies order by slug;"
```

Trebuie să existe:

- `biteight`
- `bitsense`
- `atdeco`
- `vice_engineering`
- `lp_mar`
- `gabinfy`
- `accounting`
- `lawyers`

Modelul permite:

- un utilizator în mai multe companii;
- proiecte comerciale în baza comună;
- proiecte cu instanță Supabase dedicată;
- izolare implicită între companii.

Auth și RLS nu sunt încă finalizate. Nu activa politici RLS improvizate înainte de
configurarea stack-ului Supabase complet.

Aplică și `supabase/migrations/002_automaton_activity.sql` pentru jurnalul separat
Automaton. Agentul trebuie să rămână `SETUP_PENDING` pe destinație până când
utilizatorul configurează explicit walletul, genesis promptul și limitele financiare.

## Etapa 8 — autentificarea Cloudflare MCP

Nu copia tokenul OAuth de pe primul Mac.

Rulează:

```bash
codex mcp add cloudflare-api --url https://mcp.cloudflare.com/mcp
codex mcp login cloudflare-api
codex mcp get cloudflare-api
```

Utilizatorul trebuie să aprobe OAuth în browser. Folosește doar operații read-only
dacă nu primești o cerere explicită pentru modificări Cloudflare.

Inventarul cunoscut la momentul redactării:

- 1 cont Cloudflare
- zona activă `leewuai.ro`
- 16 înregistrări DNS
- tunnel-ul `pnl-web`

Cele 38 de selecții OAuth sunt permisiuni, nu 38 de resurse sau metrici.

## Etapa 9 — verificări funcționale

Verifică local:

```text
Grafana:             http://localhost:3000
InfluxDB:            http://localhost:8086
WordPress:           http://localhost:8081
Supabase Studio:     http://localhost:54323
Hermes gateway:      http://localhost:8642
Hermes dashboard:    http://localhost:9119
OpenClaw:            http://localhost:18789
Obsidian Graph:      http://localhost:8090
Graph API status:    http://localhost:8091/status
```

În Grafana trebuie să existe folderul `Local Stack` și dashboardurile:

- `Local Stack Observability`
- `Cloudflare — LeeWu Maritime Services`

În Obsidian Graph:

- Cloudflare trebuie să apară doar în ramura `INFRA`;
- ramura INFRA trebuie să aibă pulsuri portocalii animate;
- nodul `LeeWu Maritime HP laptop (remote)` trebuie să apară în `CLIENTS`;
- nodul remote rămâne `offline` până există o conexiune VPN/Tunnel reală.

## Etapa 10 — copierea datelor persistente, numai dacă este cerută

Pornirea stack-ului recreează infrastructura și schema, dar nu transferă automat:

- date InfluxDB;
- dashboarduri create manual în Grafana;
- conținut WordPress și baza MariaDB;
- datele PostgreSQL/Supabase existente;
- starea Hermes;
- starea și workspace-ul OpenClaw.

Dacă utilizatorul cere și datele, pregătește un plan separat de backup/restore:

- `pg_dump`/`pg_restore` pentru PostgreSQL;
- `mariadb-dump` pentru WordPress;
- backupurile native InfluxDB;
- export Grafana sau copiere controlată a volumului;
- arhive ale volumelor Hermes/OpenClaw cât timp containerele sunt oprite.

Nu copia volume Docker în timp ce bazele scriu în ele. Nu folosi copiere brută între
arhitecturi diferite fără verificare. Preferă exporturile logice ale bazelor de date.

## Criterii de acceptare

Raportează sarcina ca terminată numai dacă:

1. Vibe Trading nu există pe destinație.
2. Toate celelalte servicii pornesc sau fiecare excepție este documentată.
3. Cele 8 companii există în PostgreSQL.
4. Cele două dashboarduri Grafana sunt provisionate.
5. Obsidian Graph afișează INFRA/Cloudflare animat.
6. MCP Cloudflare este configurat și autentificat separat.
7. Niciun secret nu a fost scris în Git, loguri sau documentație.

La final, oferă utilizatorului un tabel scurt cu serviciu, stare și URL local, plus
orice pas rămas pentru transferul datelor persistente.
