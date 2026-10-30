# LeeWu AI — SQLite Backup & Restore Runbook (Phase 5)

**Baseline Golden Checksum**: `3ffd6c05de47923d4d2db094877ae8c543e94ec1a415fb079a2d2724bea6e345` (`282624` bytes)  
**Phase Status**: **PASS**

---

## 1. Safe Online SQLite Backup Procedure

Always use SQLite's native `.backup` API (or immutable read-only copy when WAL is quiescent) to create consistent point-in-time snapshots in `data_backups/`:

```powershell
C:\Users\PC\.local\bin\python3.11.exe -c "
import sqlite3, hashlib, time
from pathlib import Path
src = Path('data/leewu_mvp.db')
dst = Path(f'data_backups/leewu_mvp_backup_{time.strftime("%Y%m%d_%H%M%S")}.db')
dst.parent.mkdir(parents=True, exist_ok=True)
s_conn = sqlite3.connect(f'file:{src.as_posix()}?mode=ro', uri=True)
d_conn = sqlite3.connect(str(dst))
with d_conn:
    s_conn.backup(d_conn)
d_conn.close()
s_conn.close()
print('Backup created:', dst, 'SHA-256:', hashlib.sha256(dst.read_bytes()).hexdigest())
"
```

---

## 2. Controlled Restore Verification Procedure

> **CRITICAL RULE**: Never automatically overwrite a newer database containing active survey records with an older backup without first inspecting row diffs (`surveys`, `evidence`, `ai_assessments`).

1. **Stop Write Services**:
   Stop `leewu_mvp_server.py` before replacing the SQLite file.
2. **Verify Backup Integrity Before Restore**:
   ```powershell
   C:\Users\PC\.local\bin\python3.11.exe -c "import sqlite3; c=sqlite3.connect('data_backups/leewu_mvp_v1.0.0_rc1_backup.db'); print(c.execute('PRAGMA integrity_check').fetchone()[0]); print(c.execute('PRAGMA foreign_key_check').fetchall())"
   ```
3. **Preserve Pre-Restore State & Restore**:
   ```powershell
   Copy-Item "data/leewu_mvp_runtime.db" "data_backups/pre_restore_snapshot_$(Get-Date -Format 'yyyyMMdd_HHmmss').db" -ErrorAction SilentlyContinue
   Copy-Item "data_backups/leewu_mvp_v1.0.0_rc1_backup.db" "data/leewu_mvp_runtime.db" -Force
   Remove-Item "data/leewu_mvp_runtime.db-wal","data/leewu_mvp_runtime.db-shm" -ErrorAction SilentlyContinue
   ```
