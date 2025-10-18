#!/usr/bin/env python3
"""
Database Backup Script (Agent)
------------------------------
Performs pg_dump inside the Postgres container.
Writes to a single rotating file (database-backup.sql).
Logs actions and updates sys_data.json metadata.

Workflow:
1. Create .maintaining flag
2. Run pg_dump via docker exec
3. Save output only if successful
4. Update sys_data.json with timestamp
5. Remove .maintaining flag
"""

import os
import subprocess
import sys
import json
from pathlib import Path
from datetime import datetime


# ---------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
BACKUP_DIR = PROJECT_ROOT / "backup"
PROCESS_DIR = PROJECT_ROOT / "processing"
LOG_FILE = PROCESS_DIR / "backup-log.txt"
MAINTAIN_FLAG = PROCESS_DIR / ".maintaining"
SYS_DATA_FILE = PROCESS_DIR / "sys_data.json"

BACKUP_FILE = BACKUP_DIR / "database-backup.sql"
TEMP_FILE = BACKUP_DIR / "database-backup.tmp"

os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(PROCESS_DIR, exist_ok=True)


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------
def log(msg: str, append: bool = True):
    """Write log line, optionally overwrite file on first call."""
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    line = f"{timestamp} {msg}\n"
    mode = "a" if append else "w"
    with open(LOG_FILE, mode, encoding="utf-8") as f:
        f.write(line)
    print(line, end="")

def load_env():
    if not ENV_FILE.exists():
        log(f"⚠️  No .env file found at {ENV_FILE}")
        return
    for line in ENV_FILE.read_text().splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

def start_processing():
    MAINTAIN_FLAG.write_text("processing", encoding="utf-8")
    log("🟡 Maintenance mode started.")

def end_processing():
    if MAINTAIN_FLAG.exists():
        MAINTAIN_FLAG.unlink()
        log("🟢 Maintenance mode ended.")

def update_sys_data():
    """Record latest backup time in sys_data.json."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = {}
    if SYS_DATA_FILE.exists():
        try:
            data = json.loads(SYS_DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data["latest_backup"] = now
    SYS_DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    log(f"🧾 Updated sys_data.json → latest_backup: {now}")


# ---------------------------------------------------------------------
# BACKUP PROCESS
# ---------------------------------------------------------------------
def backup_database():
    log("=== Distributor Database Backup ===", append=False)
    start_processing()
    load_env()

    DB_CONTAINER = os.getenv("DB_CONTAINER", "distributor-deployment-db-1")
    DB_NAME = os.getenv("POSTGRES_DB", "distributor_db")
    DB_USER = os.getenv("POSTGRES_USER", "distributor")

    try:
        log(f"Starting database backup from container '{DB_CONTAINER}'...")

        # Remove any old temp file
        if TEMP_FILE.exists():
            TEMP_FILE.unlink()

        cmd = [
            "docker", "exec", DB_CONTAINER,
            "pg_dump", "-U", DB_USER, DB_NAME
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)

        if proc.returncode != 0:
            log("❌ Backup failed:")
            log(proc.stderr.strip())
            raise RuntimeError(proc.stderr.strip())

        # Write to temp file first
        TEMP_FILE.write_text(proc.stdout, encoding="utf-8")

        # Validate file not empty
        if TEMP_FILE.stat().st_size == 0:
            TEMP_FILE.unlink()
            raise RuntimeError("Backup file is empty — aborting.")

        # Replace old backup
        if BACKUP_FILE.exists():
            BACKUP_FILE.unlink()
        TEMP_FILE.rename(BACKUP_FILE)

        size_mb = BACKUP_FILE.stat().st_size / (1024 * 1024)
        log(f"✅ Backup complete — {size_mb:.2f} MB written to {BACKUP_FILE}")

        # Update sys_data.json
        update_sys_data()

    except Exception as e:
        log(f"⚠️  Backup failed: {e}")
        # Cleanup any temp or empty files
        if TEMP_FILE.exists():
            TEMP_FILE.unlink()
        if BACKUP_FILE.exists() and BACKUP_FILE.stat().st_size == 0:
            BACKUP_FILE.unlink()

    finally:
        end_processing()
        log("Backup process finished.\n" + "-" * 60)


# ---------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------
if __name__ == "__main__":
    log("=== Distributor Database Backup ===")
    backup_database()
