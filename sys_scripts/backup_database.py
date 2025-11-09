#!/usr/bin/env python3
import subprocess
import shutil
from datetime import datetime, timezone
from sys_scripts.utils import (
    Context,
    DB_NAME,
    DB_USER,
    DB_PASSWORD,
    BACKUP_DB_FILE,
    TEMP_DB_FILE,
)

def backup_database():
    ctx = Context("backup")
    ctx.log("=== Distributor Database Backup ===", append=False)
    entered_maintenance = False

    if ctx.is_maintaining():
        ctx.log("Aborting: maintenance already in progress (found .maintaining).")
        raise RuntimeError("Another maintenance process is active. Could not start the process.")
    
    ctx.start_processing()
    entered_maintenance = True

    ctx.load_env()

    db_container = ctx.get_db_container()

    try:
        ctx.log(f"Starting database backup from container '{db_container}'...")

        # Remove old temp file if exists
        if TEMP_DB_FILE.exists():
            TEMP_DB_FILE.unlink()

        # Stream pg_dump output to a temp file to avoid loading entire DB into memory.
        # Pass PGPASSWORD into the exec environment so pg_dump runs non-interactively.
        cmd = [
            "docker",
            "exec",
            "-e",
            f"PGPASSWORD={DB_PASSWORD}",
            "-i",
            db_container,
            "pg_dump",
            "-U",
            DB_USER,
            DB_NAME,
        ]

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Stream stdout to TEMP_DB_FILE in binary mode
        with open(TEMP_DB_FILE, "wb") as out_f:
            # copyfileobj will read until EOF and write in chunks
            shutil.copyfileobj(proc.stdout, out_f)

        # Close stdout to allow process to terminate properly and read stderr
        if proc.stdout:
            proc.stdout.close()
        stderr = proc.stderr.read().decode("utf-8") if proc.stderr is not None else ""
        ret = proc.wait()

        if ret != 0:
            ctx.log("Backup failed:")
            ctx.log(stderr.strip())
            if TEMP_DB_FILE.exists():
                TEMP_DB_FILE.unlink()
            raise RuntimeError(stderr.strip() or f"pg_dump exited with code {ret}")

        if TEMP_DB_FILE.stat().st_size == 0:
            TEMP_DB_FILE.unlink()
            raise RuntimeError("Backup file is empty — aborting.")

        # Move temp file to final location
        if BACKUP_DB_FILE.exists():
            BACKUP_DB_FILE.unlink()
        TEMP_DB_FILE.rename(BACKUP_DB_FILE)

        size_mb = BACKUP_DB_FILE.stat().st_size / (1024 * 1024)
        ctx.log(f"Backup complete — {size_mb:.2f} MB written to {BACKUP_DB_FILE}")
        ctx.update_sys_data("latest_backup", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))

    except Exception as e:
        ctx.log(f"Backup failed: {e}")
        if TEMP_DB_FILE.exists():
            TEMP_DB_FILE.unlink()
        if BACKUP_DB_FILE.exists() and BACKUP_DB_FILE.stat().st_size == 0:
            BACKUP_DB_FILE.unlink()

    finally:
        # Only end processing if we successfully started maintenance.
        try:
            if entered_maintenance:
                ctx.end_processing()
        except Exception as e:
            # Log any cleanup issues but don't mask the original exception.
            ctx.log(f"Error during end_processing(): {e}")
        ctx.log("-" * 60)


if __name__ == "__main__":
    backup_database()
