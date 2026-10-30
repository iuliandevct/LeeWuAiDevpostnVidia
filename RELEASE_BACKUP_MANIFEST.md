# LeeWu AI — Release Backup Manifest (Phase 0)

**Date**: 2026-10-30  
**Phase Status**: **PASS**

---

## 1. Full Repository Mirror Backup

- **Backup Location**: `C:\Users\PC\Documents\ProiecteAutomatizareSincron\proiecte\LeeWuAiDevpostnVidia_FULL_BACKUP_20261030`
- **Total Files/Directories Archived**: `602 / 602` items (including full `.git` object store, configuration, scripts, and data directories).
- **Verification**: 100% file count parity verified prior to history rewrite and security hardening.

---

## 2. Dedicated SQLite Database Backups

| Backup Artifact | Path | Size (Bytes) | SHA-256 Checksum | Integrity Check |
| :--- | :--- | :---: | :--- | :---: |
| **Original Production/Demo DB** | `data/leewu_mvp.db` | `282624` | `3ffd6c05de47923d4d2db094877ae8c543e94ec1a415fb079a2d2724bea6e345` | `ok` |
| **Release Candidate v1.0.0-rc1 Backup** | `data_backups/leewu_mvp_v1.0.0_rc1_backup.db` | `282624` | `3ffd6c05de47923d4d2db094877ae8c543e94ec1a415fb079a2d2724bea6e345` | `ok` |
| **Isolated CRUD Test Backup** | `data_backups/leewu_mvp_isolated_crud_test.db` | `282624` | `3ffd6c05de47923d4d2db094877ae8c543e94ec1a415fb079a2d2724bea6e345` | `ok` |
| **Local Runtime Working Copy** | `data/leewu_mvp_runtime.db` | `282624` | Isolated runtime copy used by local daemon | `ok` |

---

## 3. Backup Verification Command

```powershell
C:\Users\PC\.local\bin\python3.11.exe -c "import hashlib, pathlib; p = pathlib.Path('data_backups/leewu_mvp_v1.0.0_rc1_backup.db'); print(p, hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_size)"
```
