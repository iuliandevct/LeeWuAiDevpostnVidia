# LeeWu AI — Local Backend Operations Runbook (Phase 5)

**Target Host**: Local Windows Server (`127.0.0.1:8080`)  
**Python Runtime**: `C:\Users\PC\.local\bin\python3.11.exe`  
**Phase Status**: **PASS**

---

## 1. Environment & Dependency Isolation

- **Core MVP Backend (`leewu_mvp_server.py`) & Telegram Daemon (`telegram_bot_daemon.py`)**: Engineered using Python 3.11 standard library (`http.server`, `sqlite3`, `urllib.request`, `hashlib`, `secrets`, `json`) for zero third-party supply-chain attack surface.
- **Optional Auxiliary Tools (`requirements.txt`)**: Pinned in `requirements.txt` for PDF/Telegram/FastAPI extensions inside `.venv`.

---

## 2. Required Environment Variables (`.env` — Untracked)

Store in `C:\Users\PC\Documents\ProiecteAutomatizareSincron\proiecte\youtube\.env` (never committed to Git):

```ini
PORT="8080"
HOST="127.0.0.1"
LEEWU_DB_PATH="C:\Users\PC\Documents\ProiecteAutomatizareSincron\proiecte\youtube\data\leewu_mvp_runtime.db"
REQUIRE_AUTH_FOR_WRITES="true"
ADMIN_API_KEY="<high-entropy-256-bit-bearer-secret>"
NEBIUS_API_KEY="<nebius-token-factory-api-key>"
NEBIUS_BASE_URL="https://api.tokenfactory.nebius.com/v1"
NEBIUS_MODEL="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
TELEGRAM_AI_MODEL="nvidia/Nemotron-3-Ultra-550b-a55b"
TELEGRAM_BOT_TOKEN="<telegram-bot-token>"
TELEGRAM_CHAT_ID="8143220589"
TELEGRAM_ALLOWED_USERS="8143220589"
```

---

## 3. Persistent Service Startup & Automatic Restart

### 3.1 Start Local Backend API Server (Isolated Runtime DB)
```powershell
$env:LEEWU_DB_PATH = "C:\Users\PC\Documents\ProiecteAutomatizareSincron\proiecte\youtube\data\leewu_mvp_runtime.db"
C:\Users\PC\.local\bin\python3.11.exe "C:\Users\PC\Documents\ProiecteAutomatizareSincron\proiecte\youtube\leewu_mvp_server.py"
```

### 3.2 Start Persistent Telegram Bot Daemon (`@Leewubot`)
```powershell
C:\Users\PC\.local\bin\python3.11.exe "C:\Users\PC\Documents\ProiecteAutomatizareSincron\proiecte\youtube\telegram_bot_daemon.py"
```

### 3.3 Windows Scheduled Task / Watchdog Registration (Auto-Start & Auto-Restart)
To register automatic startup on boot with restart-on-failure (every 1 minute, up to 999 retries):
```powershell
$ActionApi = New-ScheduledTaskAction -Execute "C:\Users\PC\.local\bin\python3.11.exe" -Argument "leewu_mvp_server.py" -WorkingDirectory "C:\Users\PC\Documents\ProiecteAutomatizareSincron\proiecte\youtube"
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "LeeWuAI_Local_API" -Action $ActionApi -Trigger $Trigger -Settings $Settings -Description "LeeWu AI Local MVP API Server"
```

---

## 4. Health Check & Log Rotation

- **Health Check Endpoint**:
  ```powershell
  Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/health"
  ```
  Expected response: `{"status": "ok", "database": "connected (SQLite)", "ai_available": true}`.
- **Log Hygiene**: Both `leewu_mvp_server.py` and `telegram_bot_daemon.py` sanitize all exceptions via `sanitize_text()` / `safe_log_err()` so `NEBIUS_API_KEY`, `TELEGRAM_BOT_TOKEN`, and `Bearer` tokens are never written to stdout/stderr logs.
