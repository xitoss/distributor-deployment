#!/usr/bin/env python3
import subprocess
from datetime import datetime, timezone
from sys_scripts.utils import (
        Context, 
        DB_NAME,
        DB_USER,
        BACKUP_DB_FILE,
        TEMP_DB_FILE,
    )

def backup_database():
    ctx = Context("backup")
    ctx.log("=== Distributor Database Backup ===", append=False)
    ctx.start_processing()
    ctx.load_env()

    db_container = ctx.get_db_container()

    try:
        ctx.log(f"Starting database backup from container '{db_container}'...")

        # Remove old temp file if exists
        if TEMP_DB_FILE.exists():
            TEMP_DB_FILE.unlink()

        cmd = ["docker", "exec", db_container, "pg_dump", "-U", DB_USER, DB_NAME]
        proc = subprocess.run(cmd, capture_output=True, text=True)

        if proc.returncode != 0:
            ctx.log("❌ Backup failed:")
            ctx.log(proc.stderr.strip())
            raise RuntimeError(proc.stderr.strip())

        TEMP_DB_FILE.write_text(proc.stdout, encoding="utf-8")

        if TEMP_DB_FILE.stat().st_size == 0:
            TEMP_DB_FILE.unlink()
            raise RuntimeError("Backup file is empty — aborting.")

        # Move temp file to final location
        if BACKUP_DB_FILE.exists():
            BACKUP_DB_FILE.unlink()
        TEMP_DB_FILE.rename(BACKUP_DB_FILE)

        size_mb = BACKUP_DB_FILE.stat().st_size / (1024 * 1024)
        ctx.log(f"✅ Backup complete — {size_mb:.2f} MB written to {BACKUP_DB_FILE}")
        ctx.update_sys_data("latest_backup", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))

    except Exception as e:
        ctx.log(f"⚠️  Backup failed: {e}")
        if TEMP_DB_FILE.exists():
            TEMP_DB_FILE.unlink()
        if BACKUP_DB_FILE.exists() and BACKUP_DB_FILE.stat().st_size == 0:
            BACKUP_DB_FILE.unlink()

    finally:
        ctx.end_processing()
        ctx.log("Backup process finished.\n" + "-" * 60)


if __name__ == "__main__":
    backup_database()
