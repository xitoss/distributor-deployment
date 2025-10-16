#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
BACKUP_DIR = PROJECT_ROOT / "backup"
BACKUP_FILE = BACKUP_DIR / "database_backup.sql"

def load_env():
    if not ENV_FILE.exists():
        print(f"No .env file found at {ENV_FILE}")
        return
    for line in ENV_FILE.read_text().splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip()

load_env()

DB_NAME = os.getenv("DB_NAME", "distributor_db")
DB_USER = os.getenv("DB_USER", "distributor")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = os.getenv("DB_PORT", "5432")

os.makedirs(BACKUP_DIR, exist_ok=True)

def check_db_health():
    print("Checking database health...")
    cmd = ["pg_isready", "-h", DB_HOST, "-p", DB_PORT, "-U", DB_USER, "-d", DB_NAME]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode == 0:
        print("Database is healthy.")
        return True
    print("Database is not responding:")
    print(proc.stderr.strip() or proc.stdout.strip())
    return False

def backup_database():
    if not check_db_health():
        sys.exit(1)

    if BACKUP_FILE.exists():
        BACKUP_FILE.unlink()

    print(f"Creating database backup → {BACKUP_FILE}")
    env = os.environ.copy()
    env["PGPASSWORD"] = DB_PASSWORD
    cmd = [
        "pg_dump",
        "-h", DB_HOST,
        "-p", DB_PORT,
        "-U", DB_USER,
        "-d", DB_NAME
    ]
    with open(BACKUP_FILE, "w", encoding="utf-8") as f:
        proc = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True, env=env)
        if proc.returncode != 0:
            print("Backup failed:")
            print(proc.stderr.strip())
            sys.exit(proc.returncode)

    size_mb = BACKUP_FILE.stat().st_size / (1024 * 1024)
    print(f"Backup complete ({size_mb:.2f} MB)")
    print(f"Saved to: {BACKUP_FILE}")

if __name__ == "__main__":
    print("=== Distributor Database Backup ===")
    backup_database()
