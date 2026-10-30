# LeeWu AI — Release Rollback Plan (Phase 8)

**Baseline Tag / Commit**: `v1.0.0-rc1` / `feb0c31cbc726ac8e99ada4a07c3b5fbcf57dd30`  
**Golden SQLite Backup**: `data_backups/leewu_mvp_v1.0.0_rc1_backup.db` (`sha256: 3ffd6c05de47923d4d2db094877ae8c543e94ec1a415fb079a2d2724bea6e345`)  
**Phase Status**: **PASS**

---

## Step-by-Step Rollback Procedure

If a post-release defect or operational incident occurs:

### Step 1 — Stop Public API Access (If Cloudflare Tunnel Was Activated)
```powershell
Stop-Process -Name "cloudflared" -Force -ErrorAction SilentlyContinue
```
This immediately severs any external edge ingress while keeping local services intact for inspection.

### Step 2 — Revert Frontend to Last Stable Commit
If a frontend change causes rendering regressions:
```powershell
git -C "C:\Users\PC\Documents\ProiecteAutomatizareSincron\proiecte\LeeWuAiDevpostnVidia" checkout v1.0.0-rc1 -- index.html landing.html login.html web/login.html demo.html survey-console.html survey.html ai-ops.html
```

### Step 3 — Stop Local Write-Capable Services
```powershell
Get-CimInstance Win32_Process -Filter "Name LIKE 'python%' AND CommandLine LIKE '%leewu_mvp_server.py%'" | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

### Step 4 — Inspect Database Differences Before Any Restore
> **MANDATORY SAFETY GATE**: Never overwrite a database containing newer inspection records with an older backup without comparing row counts and timestamps first.

```powershell
C:\Users\PC\.local\bin\python3.11.exe -c "
import sqlite3
for label, path in [('Runtime DB', 'data/leewu_mvp_runtime.db'), ('Golden Backup', 'data_backups/leewu_mvp_v1.0.0_rc1_backup.db')]:
    c = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    print(label, 'integrity:', c.execute('PRAGMA integrity_check').fetchone()[0], 'surveys:', c.execute('SELECT COUNT(*) FROM surveys').fetchone()[0])
    c.close()
"
```

### Step 5 — Restore SQLite Backup (Only If Database Integrity Requires It)
```powershell
Copy-Item "data/leewu_mvp_runtime.db" "data_backups/corrupt_or_pre_rollback_$(Get-Date -Format 'yyyyMMdd_HHmmss').db" -ErrorAction SilentlyContinue
Copy-Item "data_backups/leewu_mvp_v1.0.0_rc1_backup.db" "data/leewu_mvp_runtime.db" -Force
Remove-Item "data/leewu_mvp_runtime.db-wal","data/leewu_mvp_runtime.db-shm" -ErrorAction SilentlyContinue
```

### Step 6 — Reopen Demo in Strict Read-Only Mode
Restart `leewu_mvp_server.py` with `REQUIRE_AUTH_FOR_WRITES="true"` and verify `GET /api/health` returns `200 OK` while unauthenticated `POST /api/surveys/LW-DEMO-001/upload` returns `401`.
