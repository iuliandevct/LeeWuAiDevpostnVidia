import http.client
import json
import os
import shutil
import socket
import subprocess
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


STACK_SERVICES = {
    "grafana": {"label": "Grafana", "container": "stack-grafana", "http": "http://grafana:3000/api/health"},
    "influxdb": {"label": "InfluxDB", "container": "stack-influxdb", "http": "http://influxdb:8086/health"},
    "telegraf": {"label": "Telegraf", "container": "stack-telegraf"},
    "supabase-db": {"label": "Supabase DB", "container": "stack-supabase-db", "tcp": ("supabase-db", 5432)},
    "supabase-meta": {"label": "Supabase Meta", "container": "stack-supabase-meta", "http": "http://supabase-meta:8080/health"},
    "supabase-studio": {"label": "Supabase Studio", "container": "stack-supabase-studio", "http": "http://supabase-studio:3000"},
    "wordpress": {"label": "WordPress", "container": "stack-wordpress", "http": "http://wordpress:80"},
    "wordpress-db": {"label": "WordPress DB", "container": "stack-wordpress-db", "tcp": ("wordpress-db", 3306)},
    "vibe-trading": {"label": "Vibe Trading API", "container": "stack-vibe-trading", "http": "http://vibe-trading:8899/docs"},
    "vibe-trading-ui": {"label": "Vibe Trading UI", "container": "stack-vibe-trading-ui", "http": "http://vibe-trading-ui:5899"},
    "hermes": {"label": "Hermes", "container": "stack-hermes", "tcp": ("hermes", 8642)},
    "openclaw": {"label": "OpenClaw", "container": "stack-openclaw", "tcp": ("openclaw", 18789)},
    "automaton": {"label": "Conway Automaton", "container": "stack-automaton"},
    "obsidian-graph": {"label": "Obsidian Graph", "container": "stack-obsidian-graph", "http": "http://obsidian-graph:80"},
}

MARKET_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
MOCK_MARKETS = {
    "BTCUSDT": {"symbol": "BTCUSDT", "base": "BTC", "price": 67240.0, "change_24h": 1.84},
    "ETHUSDT": {"symbol": "ETHUSDT", "base": "ETH", "price": 3520.0, "change_24h": 2.31},
    "SOLUSDT": {"symbol": "SOLUSDT", "base": "SOL", "price": 184.0, "change_24h": -0.42},
}

STACK_ROOT = Path(__file__).resolve().parents[1]
ENV_FILES = (
    STACK_ROOT / ".env",
    Path.home() / "Downloads" / "ai-containers-stack" / ".env",
    Path.home() / "Documents" / "ai-containers-stack" / ".env",
)


def local_db_settings():
    values = dict(os.environ)
    for filename in ENV_FILES:
        try:
            with open(filename, encoding="utf-8") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        values.setdefault(key.strip(), value.strip())
            break
        except OSError:
            continue
    return {
        "host": values.get("SUPABASE_DB_HOST", "127.0.0.1"),
        "port": values.get("SUPABASE_DB_PORT", "54322"),
        "database": values.get("SUPABASE_DB_NAME", "postgres"),
        "user": values.get("SUPABASE_DB_USER", "postgres"),
        "password": values.get("SUPABASE_DB_PASSWORD", ""),
    }


class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, socket_path, timeout=5):
        super().__init__("localhost", timeout=timeout)
        self.socket_path = socket_path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.socket_path)


def docker_request(path):
    socket_path = os.environ.get("DOCKER_SOCKET", "/var/run/docker.sock")
    try:
        conn = UnixHTTPConnection(socket_path)
        conn.request("GET", path)
        response = conn.getresponse()
        body = response.read()
        conn.close()
        if response.status >= 400:
            return None, f"docker http {response.status}"
        return json.loads(body.decode("utf-8")), None
    except Exception as exc:
        return None, str(exc)


def docker_containers():
    data, error = docker_request("/containers/json?all=true")
    if error:
        return {}, error
    containers = {}
    for item in data:
        names = [name.lstrip("/") for name in item.get("Names", [])]
        for name in names:
            containers[name] = item
    return containers, None


def check_http(url, timeout=2):
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "obsidian-graph-live/1.0"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status < 500, f"HTTP {response.status}"
    except urllib.error.HTTPError as exc:
        return exc.code < 500, f"HTTP {exc.code}"
    except Exception as exc:
        return False, type(exc).__name__


def check_tcp(host, port, timeout=2):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, "TCP open"
    except Exception as exc:
        return False, type(exc).__name__


def check_process(pattern):
    try:
        result = subprocess.run(
            ["/usr/bin/pgrep", "-f", pattern],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
        return result.returncode == 0, "process running" if result.returncode == 0 else "process missing"
    except Exception as exc:
        return False, type(exc).__name__


def check_path(path):
    resolved = Path(path).expanduser()
    return resolved.exists(), str(resolved) if resolved.exists() else "source missing"


def collect_native_status():
    checks = [
        {
            "id": "jay-grafana",
            "label": "Jay Mac Pro · Grafana",
            "check": lambda: check_http("http://127.0.0.1:3000/api/health"),
            "url": "http://192.168.0.31:3000",
        },
        {
            "id": "jay-hermes",
            "label": "Jay Mac Pro · Hermes",
            "check": lambda: check_process("hermes.*gateway"),
            "url": "http://192.168.0.31:8091/status",
        },
        {
            "id": "social-media-agency",
            "label": "Social Media Agency · workflows",
            "check": lambda: check_path(
                os.environ.get(
                    "SOCIAL_MEDIA_AGENCY_PATH",
                    Path.home() / "Documents" / "social_media_agency" / ".git",
                )
            ),
            "url": "https://github.com/iuliandevct/social_media_agency",
        },
    ]
    services = []
    online = 0
    for item in checks:
        ok, detail = item["check"]()
        state = "online" if ok else "offline"
        online += int(ok)
        services.append({
            "id": item["id"],
            "label": item["label"],
            "state": state,
            "container": "native",
            "docker_state": "native",
            "docker_status": detail,
            "health": "healthy" if ok else "unhealthy",
            "endpoint": detail,
            "url": item["url"],
            "checked_at": int(time.time()),
        })
    return {
        "ok": True,
        "mode": "native",
        "summary": {
            "online": online,
            "degraded": 0,
            "offline": len(services) - online,
            "total": len(services),
        },
        "services": services,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def collect_markets():
    markets = []
    source = "binance"
    for symbol in MARKET_SYMBOLS:
      try:
          url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
          request = urllib.request.Request(url, headers={"User-Agent": "obsidian-graph-live/1.0"})
          with urllib.request.urlopen(request, timeout=4) as response:
              payload = json.loads(response.read().decode("utf-8"))
          markets.append({
              "symbol": symbol,
              "base": symbol.replace("USDT", ""),
              "price": float(payload["lastPrice"]),
              "change_24h": float(payload["priceChangePercent"]),
          })
      except Exception:
          source = "mock"
          markets.append(MOCK_MARKETS[symbol])
    return {
        "source": source,
        "markets": markets,
        "positions": [
            {"base": "ETH", "side": "long", "size": 1.25, "entry": 3350.0, "pnl": 212.5},
            {"base": "SOL", "side": "watch", "size": 0, "entry": 0, "pnl": 0},
        ],
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def collect_trading_research():
    root = Path.home() / "cryptoG"
    summary_path = root / "artifacts" / "top50-v8" / "summary.json"
    universe_path = root / "artifacts" / "top50-spot-depth" / "universe.json"
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        summary = {"suite": "top50_spot_v8", "aggregate": {}, "results": []}
    try:
        universe = json.loads(universe_path.read_text(encoding="utf-8"))
    except Exception:
        universe = {"symbols": []}
    data_root = root / "artifacts" / "top50-spot-depth"
    monitored = 0
    trade_rows = 0
    for symbol in universe.get("symbols", []):
        name = symbol.replace("/", "").lower()
        depth_path = data_root / f"{name}.jsonl"
        trades_path = data_root / f"{name}-aggtrades.jsonl"
        monitored += int(depth_path.exists() and depth_path.stat().st_size > 0)
        if trades_path.exists():
            try:
                with trades_path.open(encoding="utf-8") as handle:
                    trade_rows += sum(1 for _ in handle)
            except OSError:
                pass
    return {
        "ok": True, "mode": "analysis-only", "suite": summary.get("suite", "top50_spot_v8"),
        "allocation": summary.get("allocation", {"pairs": 50, "per_pair_usdc": 10, "total_usdc": 500}),
        "execution": summary.get("execution", {}), "aggregate": summary.get("aggregate", {}),
        "tested_pairs": summary.get("tested_pairs", 0), "universe_size": len(universe.get("symbols", [])),
        "monitored_pairs": monitored, "captured_trade_rows": trade_rows,
        "guardrails": summary.get("guardrails", {"may_place_orders": False}),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def collect_knowledge():
    settings = local_db_settings()
    psql = shutil.which("psql") or "/usr/local/opt/postgresql@15/bin/psql"
    sql = """
select json_build_object(
  'ok', true,
  'summary', json_build_object(
    'documents', (select count(*) from public.knowledge_documents),
    'chunks', (select count(*) from public.knowledge_chunks),
    'dimensions', (select coalesce(max(cardinality(embedding)), 0) from public.knowledge_chunks),
    'model', (select embedding_model from public.knowledge_chunks limit 1)
  ),
  'recent', coalesce((
    select json_agg(row_to_json(recent_docs))
    from (
      select filename, page_count, metadata->>'document_type' as document_type,
             ingested_at
      from public.knowledge_documents
      order by ingested_at desc, filename
      limit 5
    ) recent_docs
  ), '[]'::json),
  'updated_at', to_char(clock_timestamp() at time zone 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"')
)::text;
"""
    process_env = os.environ.copy()
    process_env["PGPASSWORD"] = settings["password"]
    try:
        result = subprocess.run(
            [
                psql, "-X", "-tA",
                "-h", settings["host"], "-p", settings["port"],
                "-U", settings["user"], "-d", settings["database"],
                "-c", sql,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
            env=process_env,
        )
        return json.loads(result.stdout.strip())
    except Exception as exc:
        return {
            "ok": False,
            "error": type(exc).__name__,
            "summary": {"documents": 0, "chunks": 0, "dimensions": 0, "model": None},
            "recent": [],
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }


def collect_status():
    containers, docker_error = docker_containers()
    if docker_error:
        return collect_native_status()
    services = []
    online = degraded = offline = 0

    for service_id, cfg in STACK_SERVICES.items():
        container = containers.get(cfg["container"])
        docker_state = "unknown"
        docker_status = "not found"
        health = None
        if container:
            state = container.get("State", "unknown")
            docker_status = container.get("Status", "")
            docker_state = state
            health = "healthy" if "healthy" in docker_status else None
            if "unhealthy" in docker_status:
                health = "unhealthy"

        endpoint_ok = None
        endpoint_detail = None
        if "http" in cfg:
            endpoint_ok, endpoint_detail = check_http(cfg["http"])
        elif "tcp" in cfg:
            endpoint_ok, endpoint_detail = check_tcp(*cfg["tcp"])

        running = docker_state == "running"
        if running and endpoint_ok is not False and health != "unhealthy":
            state = "online"
            online += 1
        elif running:
            state = "degraded"
            degraded += 1
        else:
            state = "offline"
            offline += 1

        services.append({
            "id": service_id,
            "label": cfg["label"],
            "state": state,
            "container": cfg["container"],
            "docker_state": docker_state,
            "docker_status": docker_status,
            "health": health,
            "endpoint": endpoint_detail or "container only",
            "checked_at": int(time.time()),
        })

    return {
        "ok": docker_error is None,
        "docker_error": docker_error,
        "summary": {
            "online": online,
            "degraded": degraded,
            "offline": offline,
            "total": len(services),
        },
        "services": services,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self._headers()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/live":
            self._json({"ok": True})
            return
        if parsed.path == "/status":
            self._json(collect_status())
            return
        if parsed.path == "/markets":
            self._json(collect_markets())
            return
        if parsed.path == "/trading":
            self._json(collect_trading_research())
            return
        if parsed.path == "/knowledge":
            self._json(collect_knowledge())
            return
        self.send_response(404)
        self._headers()
        self.end_headers()

    def log_message(self, fmt, *args):
        return

    def _headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, payload):
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(200)
        self._headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8091"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"graph-api listening on 0.0.0.0:{port}", flush=True)
    server.serve_forever()
