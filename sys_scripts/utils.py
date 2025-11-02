#!/usr/bin/env python3
import os
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess


# -------------------------------------------------------------------
# CONSTANT PATHS
# -------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
PROCESS_DIR = PROJECT_ROOT / "processing"
BACKUP_DIR = PROJECT_ROOT / "backup"
SYS_DATA = PROCESS_DIR / "sys_data.json"
STATUS_FILE = PROCESS_DIR / "processing-status.json"

# DATABASE RELATED CONSTANTS
DB_NAME = os.getenv("POSTGRES_DB", "distributor_db")
DB_USER = os.getenv("POSTGRES_USER", "distributor")
BACKUP_DB_FILE = BACKUP_DIR / "database-backup.sql"
TEMP_DB_FILE = BACKUP_DIR / "database-backup.tmp"

VERSION_DIR = PROJECT_ROOT / "version"

# most updated latest.json will be available in this url
REPO_LATEST_FILE_URL = "https://raw.githubusercontent.com/xitoss/distributor-deployment/Main/version/latest.json"
APP_IMAGE_URL = 'ghcr.io/xitoss/distributor-app:latest'

# -------------------------------------------------------------------
# MAIN CONTEXT CLASS
# -------------------------------------------------------------------
class Context:
    """
    Runtime context for operations like backup, restore, update, ping, etc.
    Handles logging, maintenance flags, and environment setup.
    """

    def __init__(self, action_type: str):
        self.action_type = action_type.lower()
        self.timestamp = datetime.now(timezone.utc).strftime("[%Y-%m-%d %H:%M:%S UTC]")
        self.flag_path = PROCESS_DIR / ".maintaining"
        self.log_file = PROCESS_DIR / f"{self.action_type}-log.txt"

        PROCESS_DIR.mkdir(parents=True, exist_ok=True)
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------
    # LOGGING
    # ---------------------------------------------------------------
    def log(self, msg: str, append: bool = True):
        """Write timestamped log entries automatically."""
        line = f"{self.timestamp} {msg}\n"
        mode = "a" if append else "w"
        with open(self.log_file, mode, encoding="utf-8") as f:
            f.write(line)
        print(line, end="")

    # ---------------------------------------------------------------
    # ENVIRONMENT
    # ---------------------------------------------------------------
    def load_env(self):
        """Load .env file into environment variables."""
        if not ENV_FILE.exists():
            self.log(f"⚠️  No .env file found at {ENV_FILE}")
            return
        for line in ENV_FILE.read_text().splitlines():
            if line.strip() and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

    # ---------------------------------------------------------------
    # MAINTENANCE STATUS
    # ---------------------------------------------------------------
    def _set_status(self, is_maintaining: bool):
        STATUS_FILE.write_text(json.dumps({"maintaining": is_maintaining}, indent=2), encoding="utf-8")

    def start_processing(self):
        """Enter maintenance mode for this action."""
        self.flag_path.write_text(self.action_type, encoding="utf-8")
        self._set_status(True)
        self.log(f"🟡 Maintenance mode started ({self.action_type}).")

    def end_processing(self):
        """Exit maintenance mode."""
        if self.flag_path.exists():
            self.flag_path.unlink()
        self._set_status(False)
        self.log("🟢 Maintenance mode ended.")

    # ---------------------------------------------------------------
    # SYS DATA
    # ---------------------------------------------------------------
    def update_sys_data(self, key: str, value: str):
        data = {}
        if SYS_DATA.exists():
            try:
                data = json.loads(SYS_DATA.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        data[key] = value
        SYS_DATA.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self.log(f"🧾 Updated sys_data.json → {key}: {value}")

    # ---------------------------------------------------------------
    # DOCKER HELPERS
    # ---------------------------------------------------------------
    def get_db_container(self, default_name="xitoss-distributor-db-1"):
        """
        Find the primary database container for backup/restore operations.

        Notes:
        - Returns the first container matching service 'db' in this Compose project.
        - Intended for single-instance PostgreSQL deployments.
        - If database replication or scaling is used, only the primary node should
        be backed up or restored, and this function must be replaced accordingly.
        """
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", "label=com.docker.compose.service=db",
                 "--filter", "label=com.docker.compose.project=xitoss-distributor",
                 "--format", "{{.Names}}"],
                capture_output=True, text=True
            )
            name = result.stdout.strip().splitlines()[0] if result.stdout.strip() else None
            if name:
                return name
        except Exception:
            pass
        return default_name
