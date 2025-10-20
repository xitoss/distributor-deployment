#!/usr/bin/env python3
import os
import subprocess
import json
from datetime import datetime, timezone
from pathlib import Path

# -------------------------------------------------------------------
# PATHS & CONSTANTS
# -------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

PROCESS_DIR = PROJECT_ROOT / "processing"
BACKUP_DIR = PROJECT_ROOT / "backup"
LOG_FILE = PROCESS_DIR / "restore-log.txt"
SYS_DATA = PROCESS_DIR / "sys_data.json"
MAINTAINING_FLAG = PROCESS_DIR / ".maintaining"
STATUS_FILE = PROCESS_DIR / "processing-status.json"

BACKUP_FILE = BACKUP_DIR / "database-backup.sql"

# -------------------------------------------------------------------
# UTILITIES
# -------------------------------------------------------------------
def log(msg: str, append: bool = True):
    """Write log line and print to stdout."""
    PROCESS_DIR.mkdir(parents=True, exist_ok=True)
    if not LOG_FILE.exists():
        LOG_FILE.touch()

    timestamp = datetime.now(timezone.utc).strftime("[%Y-%m-%d %H:%M:%S UTC]")
    line = f"{timestamp} {msg}\n"
    mode = "a" if append else "w"
    with open(LOG_FILE, mode, encoding="utf-8") as f:
        f.write(line)
    print(line, end="")

def set_status(is_maintaining: bool):
    """Create or update processing-status.json."""
    STATUS_FILE.write_text(json.dumps({"maintaining": is_maintaining}, indent=2), encoding="utf-8")

def load_env():
    """Load environment variables from .env file."""
    if not ENV_FILE.exists():
        log(f"⚠️  No .env file found at {ENV_FILE}")
        return
    for line in ENV_FILE.read_text().splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip()

def start_processing():
    PROCESS_DIR.mkdir(parents=True, exist_ok=True)
    set_status(True)
    MAINTAINING_FLAG.write_text("restoring", encoding="utf-8")
    log("🟡 Maintenance mode started.")

def end_processing():
    if MAINTAINING_FLAG.exists():
        MAINTAINING_FLAG.unlink()
    set_status(False)
    log("🟢 Maintenance mode ended.")

def update_sys_data(key: str, value: str):
    """Update sys_data.json with latest timestamp."""
    PROCESS_DIR.mkdir(parents=True, exist_ok=True)
    data = {}
    if SYS_DATA.exists():
        try:
            data = json.loads(SYS_DATA.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    data[key] = value
    SYS_DATA.write_text(json.dumps(data, indent=2), encoding="utf-8")
    log(f"🧾 Updated sys_data.json → {key}: {value}")

def run(cmd: list[str], stdin=None, input=None, allow_error=False, quiet=False) -> subprocess.CompletedProcess:
    """Wrapper for subprocess.run with logging and optional quiet mode."""
    proc = subprocess.run(cmd, stdin=stdin, input=input, capture_output=True, text=True)

    if not quiet and proc.stdout.strip():
        log(proc.stdout.strip())
    if proc.returncode != 0:
        if allow_error:
            log(proc.stderr.strip() or "❌ Command failed (ignored).")
        else:
            log(proc.stderr.strip() or "❌ Command failed.")
            raise RuntimeError(proc.stderr or "Command failed.")
    return proc

# -------------------------------------------------------------------
# RESTORE LOGIC
# -------------------------------------------------------------------
def restore_database():
    log("=== Distributor Database Restore (CLEAN) ===", append=False)

    load_env()
    start_processing()

    DB_CONTAINER = os.getenv("DB_CONTAINER", "distributor-deployment-db-1")
    DB_NAME = os.getenv("DB_NAME") or os.getenv("POSTGRES_DB") or "distributor_db"
    DB_USER = os.getenv("DB_USER") or os.getenv("POSTGRES_USER") or "distributor"

    try:
        # Validate backup file
        if not BACKUP_FILE.exists():
            raise FileNotFoundError(f"No backup file found at {BACKUP_FILE}")
        if BACKUP_FILE.stat().st_size == 0:
            raise RuntimeError(f"Backup file is empty: {BACKUP_FILE}")

        log(f"Restoring database '{DB_NAME}' from {BACKUP_FILE} using container '{DB_CONTAINER}'...")

        # 1) Terminate active connections
        terminate_sql = (
            "SELECT pg_terminate_backend(pid) "
            f"FROM pg_stat_activity WHERE datname='{DB_NAME}' AND pid <> pg_backend_pid();"
        )
        run([
            "docker", "exec", "-i", DB_CONTAINER,
            "psql", "-q", "-U", DB_USER, "-d", "postgres", "-v", "ON_ERROR_STOP=1",
            "-c", terminate_sql
        ], allow_error=True, quiet=True)

        # 2) DROP DATABASE
        drop_db_sql = f"DROP DATABASE IF EXISTS {DB_NAME} WITH (FORCE);"
        run([
            "docker", "exec", "-i", DB_CONTAINER,
            "psql", "-q", "-U", DB_USER, "-d", "postgres", "-v", "ON_ERROR_STOP=1",
            "-c", drop_db_sql
        ], quiet=True)

        # 3) CREATE DATABASE
        create_db_sql = f"CREATE DATABASE {DB_NAME} OWNER {DB_USER};"
        run([
            "docker", "exec", "-i", DB_CONTAINER,
            "psql", "-q", "-U", DB_USER, "-d", "postgres", "-v", "ON_ERROR_STOP=1",
            "-c", create_db_sql
        ], quiet=True)

        # 4) Restore SQL dump (quiet)
        log("⏳ Restoring SQL dump into fresh database...")
        with open(BACKUP_FILE, "r", encoding="utf-8") as f:
            run([
                "docker", "exec", "-i", DB_CONTAINER,
                "psql", "-q", "-U", DB_USER, "-d", DB_NAME, "-v", "ON_ERROR_STOP=1"
            ], stdin=f, quiet=True)

        log("✅ SQL restore completed. Running sequence auto-fix...")

        # 5) Fix sequences
        seq_fix_sql = r"""
DO $$
DECLARE
    r RECORD;
    max_id BIGINT;
    full_seq_name text;
BEGIN
  FOR r IN
    SELECT
      n.nspname   AS seq_schema,
      s.relname   AS seq_name,
      t.relname   AS table_name,
      a.attname   AS column_name
    FROM pg_class s
    JOIN pg_namespace n ON n.oid = s.relnamespace
    JOIN pg_depend d ON d.objid = s.oid AND d.deptype = 'a'
    JOIN pg_class t ON t.oid = d.refobjid
    JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = d.refobjsubid
    WHERE s.relkind = 'S'
      AND n.nspname = 'public'
  LOOP
    EXECUTE format('SELECT COALESCE(MAX(%I), 0) FROM %I.%I',
                   r.column_name, r.seq_schema, r.table_name)
      INTO max_id;

    full_seq_name := quote_ident(r.seq_schema) || '.' || quote_ident(r.seq_name);

    IF max_id = 0 THEN
      EXECUTE format('SELECT setval(%s, 1, false)', quote_literal(full_seq_name));
    ELSE
      EXECUTE format('SELECT setval(%s, %s, true)', quote_literal(full_seq_name), max_id + 1);
    END IF;
  END LOOP;
END$$;
"""
        run([
            "docker", "exec", "-i", DB_CONTAINER,
            "psql", "-q", "-U", DB_USER, "-d", DB_NAME, "-v", "ON_ERROR_STOP=1"
        ], input=seq_fix_sql, quiet=True)

        log("✅ Sequences synchronized successfully.")
        update_sys_data("last_restore", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))
        log("🎉 Database restore completed successfully.")

    except Exception as e:
        log(f"❌ Restore failed: {e}")

    finally:
        end_processing()
        log("Restore process finished.")
        log("-" * 60)


# -------------------------------------------------------------------
# ENTRY POINT
# -------------------------------------------------------------------
if __name__ == "__main__":
    restore_database()
