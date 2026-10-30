# Status pentru ședința de luni

Data ședinței: luni, 27 iulie 2026

Actualizat: 26 iulie 2026

## Rezumat executiv

Stack-ul local rulează în Docker și include observabilitate, Supabase multi-companie,
agenți AI, WordPress, Cloudflare inventory și graful vizual. Conway Automaton este
instalat și izolat, dar nu este activat autonom. Are deja heartbeat în Supabase,
dashboard Grafana și pagină locală.

## Finalizat

- [x] Docker stack local creat.
- [x] Grafana, InfluxDB și Telegraf instalate.
- [x] Dashboard `Local Stack Observability`.
- [x] Dashboard `Cloudflare — LeeWu Maritime Services`.
- [x] Dashboard `Conway Automaton Observability`.
- [x] Supabase PostgreSQL, Meta și Studio instalate.
- [x] Schema multi-companie creată.
- [x] Cele 8 companii introduse.
- [x] Suport pentru proiecte shared și instanțe Supabase dedicated.
- [x] Hermes instalat.
- [x] OpenClaw instalat.
- [x] Conway Automaton construit într-un container izolat.
- [x] Tabelul `public.automaton_activity`.
- [x] Bridge Automaton → Supabase cu heartbeat la 30 secunde.
- [x] Conway integrat în Trading cu simbol Autobot.
- [x] Layer Conway pentru Grafana, Supabase, Heartbeat și Health.
- [x] Hermes integrat în nodul principal Automation.
- [x] Jay Social Media adăugat sub Hermes cu animație.
- [x] Cloudflare mutat exclusiv în INFRA.
- [x] Laptopul HP LeeWu Maritime reprezentat ca nod remote.
- [x] Instrucțiuni pentru replicarea stack-ului pe al doilea Mac.
- [x] Pagina Conway: `http://localhost:8090/automaton.html`.

## Starea Conway

```text
Container:          online
Mod:                SETUP_PENDING
Supabase heartbeat: activ, la 30 secunde
Wallet finanțat:    nu
Genesis prompt:     neconfigurat
Buclă autonomă:     oprită
Auto-replicare:     oprită
Docker socket:      fără acces
```

Pentru activarea Conway mai trebuie decise:

1. numele agentului;
2. genesis promptul;
3. adresa walletului creator;
4. bugetul maxim;
5. modelele AI permise;
6. acțiunile și domeniile de rețea permise.

## Supabase — următorii pași

- [ ] Repararea indicatorului `unhealthy` pentru Supabase Studio.
- [ ] Configurarea stack-ului Supabase complet: Auth, REST, Realtime și Storage,
      dacă sunt necesare.
- [ ] Definirea primelor proiecte pentru cele 8 companii.
- [ ] Definirea tabelelor operaționale.
- [ ] Configurarea utilizatorilor și rolurilor.
- [ ] Activarea RLS după ce Auth este funcțional.
- [ ] Politici pentru utilizatori care aparțin mai multor companii.

## Cloudflare — următorii pași

- [ ] Crearea unui user API token read-only pentru metrici live în Grafana.
- [ ] Verificarea și documentarea tunnel-ului `pnl-web`.
- [ ] Alegerea metodei sigure pentru laptopul HP din cealaltă rețea.
- [ ] Fără expunerea directă a porturilor locale.

## Observabilitate — următorii pași

- [x] Dashboardul Conway și datasource-ul Supabase au fost provisionate.
- [ ] Confirmarea manuală, în browser, a valorilor tuturor panourilor Conway.
- [ ] Alerte pentru lipsa heartbeat-ului peste 120 secunde.
- [ ] Alerte pentru status `offline`, `degraded` sau `error`.
- [ ] Trimiterea statusului Hermes și Jay Social Media în metrici reale.
- [ ] Înlocuirea animațiilor mock cu evenimente reale unde există surse.

## Replicarea pe al doilea Mac

- [x] Ghidul `REPLICATE_TO_OTHER_MAC.md` este pregătit.
- [ ] Transferul fișierelor pe al doilea Mac.
- [ ] Transferul sigur sau regenerarea `.env`.
- [ ] Autentificarea Cloudflare MCP separată.
- [ ] Export/restore pentru volumele și bazele care trebuie copiate.
- [ ] Vibe Trading trebuie exclus pe al doilea Mac.

## Probleme cunoscute

1. Supabase Studio este raportat `unhealthy`, deși PostgreSQL și Meta sunt funcționale.
2. Grafana OSS nu poate reutiliza OAuth-ul MCP Codex pentru Cloudflare.
3. Conway nu oferă implicit o interfață web; pagina locală creată este o consolă
   read-only a stack-ului nostru.
4. Playwright Chromium nu este compatibil cu versiunea curentă macOS; QA vizual se
   face momentan cu Chromium-ul headless din Hermes.

Graph API a fost reparat și verificat: 12 servicii online, 2 degradate, 0 offline.

## Ordinea recomandată după ședință

1. Reparăm Supabase Studio și completăm Auth.
2. Alegem primul proiect și primele tabele.
3. Configurăm utilizatori, roluri și RLS.
4. Stabilim limitele Conway și decidem dacă îl activăm.
5. Configurăm metricile Cloudflare live.
6. Configurăm accesul sigur de pe laptopul HP.
7. Replicăm stack-ul pe al doilea Mac, fără Vibe Trading.
