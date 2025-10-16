#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
BACKUP_FILE = PROJECT_ROOT / "backup" / "database_backup.sql"
DB_CONTAINER = "distributor-deployment-db-1"  # from docker ps

# ---------------------------------------------------------------------
# LOAD ENVIRONMENT VARIABLES
# ---------------------------------------------------------------------
def load_env():
    """Load environment variables from .env file."""
    if not ENV_FILE.exists():
        print(f"⚠️  No .env file found at {ENV_FILE}")
        return
    for line in ENV_FILE.read_text().splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip()

load_env()

DB_NAME = os.getenv("DB_NAME", "distributor_db")
DB_USER = os.getenv("DB_USER", "distributor")

# ---------------------------------------------------------------------
# UTILITIES
# ---------------------------------------------------------------------
def run_command(cmd):
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"Command failed: {' '.join(cmd)}")
        print(proc.stderr.strip())
        sys.exit(proc.returncode)
    return proc.stdout.strip()

def check_db_health():
    """Check if DB is reachable before restore."""
    print("Checking database health...")
    cmd = [
        "docker", "exec", DB_CONTAINER,
        "pg_isready", "-U", DB_USER, "-d", DB_NAME
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode == 0:
        print("Database is reachable.")
        return True
    print("Database is not responding:")
    print(proc.stderr.strip() or proc.stdout.strip())
    return False

# ---------------------------------------------------------------------
# RESTORE LOGIC
# ---------------------------------------------------------------------
def restore_database():
    if not BACKUP_FILE.exists():
        print(f"No backup file found at {BACKUP_FILE}")
        sys.exit(1)

    if not check_db_health():
        sys.exit(1)

    print(f"Restoring database '{DB_NAME}' from {BACKUP_FILE} ...")

    # Terminate all active connections before restore
    drop_sql = f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='{DB_NAME}';"
    cmd_drop = [
        "docker", "exec", "-i", DB_CONTAINER,
        "psql", "-U", DB_USER, "-d", "postgres", "-c", drop_sql
    ]
    subprocess.run(cmd_drop, capture_output=True, text=True)

    # Run restore
    cmd_restore = [
        "docker", "exec", "-i", DB_CONTAINER,
        "psql", "-U", DB_USER, "-d", DB_NAME
    ]
    with open(BACKUP_FILE, "r", encoding="utf-8") as f:
        proc = subprocess.run(cmd_restore, stdin=f, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            print("Restore failed:")
            print(proc.stderr.strip())
            sys.exit(proc.returncode)

    print("Restore complete.")
    print("Database successfully restored from backup.")

# ---------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------
if __name__ == "__main__":
    print("=== Distributor Database Restore ===")
    restore_database()
