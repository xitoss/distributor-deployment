#!/usr/bin/env python3
import subprocess
import json
import time
import requests
import os
import docker
from datetime import datetime, timezone
from sys_scripts.utils import (
    Context, 
    VERSION_DIR, 
    BACKUP_DB_FILE, 
    REPO_LATEST_FILE_URL,
    APP_IMAGE_URL,
)

RUNNING_JSON = VERSION_DIR / "running.json"
LATEST_JSON = VERSION_DIR / "latest.json"


def convert_windows_path_to_docker(path):
    """
    Convert Windows path to Docker-compatible path if needed.
    D:\\path -> /d/path (on Windows)
    /path/to/dir -> /path/to/dir (on Linux, no change)
    """
    # If path already starts with /, it's Unix-style (Linux/Mac)
    if path.startswith('/'):
        return path
    
    # Windows path detected (has drive letter with colon)
    if len(path) > 1 and path[1] == ':':
        drive = path[0].lower()
        rest = path[2:].replace('\\', '/')
        return f'/{drive}{rest}'
    
    # Fallback: return as-is
    return path


def get_host_project_path(ctx):
    """
    Get the actual host path where the project is located.
    This is needed to run docker compose from host context.
    """
    try:
        client = docker.from_env()
        hostname = os.getenv('HOSTNAME')
        agent_container = client.containers.get(hostname)
        
        for mount in agent_container.attrs['Mounts']:
            if mount['Destination'] == '/workspace':
                host_path = mount['Source']
                ctx.log(f"Detected host project path: {host_path}")
                return host_path
        
        raise Exception("Could not find /workspace mount")
    except Exception as e:
        ctx.log(f"Error detecting host path: {e}")
        raise


def fetch_latest_json_from_repo(ctx):
    """
    although we running this because running.json and latest.json is not same and udpate is necessary.
    in a edge case: 
     - user check application, but did not update at that time
     - then after a long time click on update [but another new version is available]
     - although latest.json will show a specific version, but this process will install another latest version
     - this will create confusion in running.json as that will display older version.
     - so it is safe to get latest.json from "distributor-deployment" repo, rather than /version/latest.json on host.
     - additionally /version/latest.json also need to use the latest.json from repo now
    In case failed to it is fully bad luck [should never happen actually] then can fallback to /version/latest.json
    """
    try:
        response = requests.get(REPO_LATEST_FILE_URL, timeout=10)
        response.raise_for_status()
        remote_data = response.json()

        # Try to read local
        local_data = {}
        if LATEST_JSON.exists():
            with open(LATEST_JSON, "r", encoding="utf-8") as f:
                local_data = json.load(f)

        if remote_data != local_data:
            with open(LATEST_JSON, "w", encoding="utf-8") as f:
                json.dump(remote_data, f, indent=4)
            ctx.log("Fetched and updated latest.json from repository.")
        else:
            ctx.log("Local latest.json already matches repository.")

        return remote_data

    except Exception as e:
        ctx.log(f"Failed to fetch latest.json from repo ({e}), using local fallback.")
        if LATEST_JSON.exists():
            with open(LATEST_JSON, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            raise RuntimeError("Cannot fetch or load any latest.json file.")


def run_compose_on_host(ctx, command_list, host_path):
    """
    Execute docker compose commands from HOST context (not agent container).
    
    This spawns a temporary container that:
    - Mounts the actual host project directory
    - Has access to Docker socket
    - Runs docker compose from the host's perspective
    
    Args:
        ctx: Context object for logging
        command_list: List of docker compose arguments, e.g., ['up', '-d', 'web']
        host_path: The actual host path to the project
    
    Returns:
        subprocess.CompletedProcess
    """
    docker_path = convert_windows_path_to_docker(host_path)
    
    cmd = [
        'docker', 'run', '--rm',
        '-v', f'{host_path}:{docker_path}',
        '-v', '/var/run/docker.sock:/var/run/docker.sock',
        '-w', docker_path,
        'docker:cli',
        'docker', 'compose'
    ] + command_list
    
    ctx.log(f"Running: docker compose {' '.join(command_list)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        ctx.log(f"✅ docker compose {' '.join(command_list)} succeeded")
        if result.stdout.strip():
            ctx.log(f"Output: {result.stdout}")
    else:
        ctx.log(f"❌ docker compose {' '.join(command_list)} failed")
        ctx.log(f"Error: {result.stderr}")
    
    return result


def validate_files_available(ctx):
    if not RUNNING_JSON.exists():
        raise Exception("/version/running.json missing, aborting update!")
    if not LATEST_JSON.exists():
        raise Exception("/version/latest.json missing, aborting update!")
    ctx.log("/version/running.json and /version/latest.json found.")


def open_files_data(ctx):
    running, latest = None, None
    try:
        with open(RUNNING_JSON, "r", encoding="utf-8") as f:
            running = json.load(f)
    except Exception:
        ctx.log("Error opening /version/running.json.")
    try:
        with open(LATEST_JSON, "r", encoding="utf-8") as f:
            latest = json.load(f)
    except Exception:
        ctx.log("Error opening /version/latest.json.")
    return running, latest


def validate_update(ctx, running, latest):
    if running == latest:
        raise Exception("Already up to date. Abort update.")
    ctx.log(f"Validated — updating to version {latest}")


def delete_db_backup(ctx):
    if BACKUP_DB_FILE.exists():
        BACKUP_DB_FILE.unlink()
        ctx.log("Deleted stale DB backup file.")
    else:
        ctx.log("No DB backup file to delete.")


def check_containers_running(ctx, timeout=120):
    """Wait for containers to report 'Up'."""
    start = time.time()
    while True:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}:{{.Status}}"],
            capture_output=True,
            text=True
        )
        lines = result.stdout.strip().splitlines()
        all_up = all("Up" in line or "healthy" in line.lower() for line in lines)
        if all_up:
            ctx.log("✅ All containers running normally.")
            return True
        if time.time() - start > timeout:
            ctx.log("⚠️ Containers did not reach running state in time.")
            return False
        time.sleep(5)


def update_application():
    ctx = Context("update-application")
    ctx.log("=== Distributor Update Application ===", append=False)
    ctx.start_processing()

    try:
        # Get host path for docker compose operations
        host_path = get_host_project_path(ctx)

        # get latest.json from remote or fallback to host
        fetch_latest_json_from_repo(ctx)
        
        # Validate version files
        validate_files_available(ctx)
        running_data, latest_data = open_files_data(ctx)

        if not running_data or not latest_data:
            raise Exception("Version file(s) corrupted or unreadable.")

        running_ver = running_data.get("version")
        latest_ver = latest_data.get("version")
        validate_update(ctx, running_ver, latest_ver)

        is_db_migrate = latest_data.get("db-migrate", True)
        if is_db_migrate:
            delete_db_backup(ctx)

        # Pull latest image
        ctx.log("Pulling latest web image...")
        pull_result = subprocess.run(
            ['docker', 'pull', APP_IMAGE_URL],
            capture_output=True,
            text=True
        )
        
        if pull_result.returncode != 0:
            raise Exception(f"Failed to pull image: {pull_result.stderr}")
        
        ctx.log("✅ Image pulled successfully")

        # Update web service using host context
        ctx.log("Updating web service...")
        result = run_compose_on_host(ctx, ['up', '-d', '--no-deps', 'web'], host_path)
        
        if result.returncode != 0:
            raise Exception(f"Failed to update web service: {result.stderr}")

        # Restart nginx to reload and reconnect to new web container
        ctx.log("Restarting nginx to reload new static content...")
        nginx_result = run_compose_on_host(ctx, ['restart', 'nginx'], host_path)
        
        if nginx_result.returncode != 0:
            ctx.log("⚠️ Warning: nginx restart failed, but continuing...")

        # Monitor container health
        ctx.log("Checking container health...")
        check_containers_running(ctx)

        # Update local version record
        with open(RUNNING_JSON, "w", encoding="utf-8") as f:
            json.dump(latest_data, f, indent=4)
        ctx.log("✅ Updated running.json successfully.")

        # Log timestamp
        ctx.update_sys_data(
            "last_app_update",
            datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        )
        
        ctx.log("=== Update completed successfully ===")

    except Exception as e:
        ctx.log(f"❌ Update Failed: {e}")
        raise

    finally:
        ctx.end_processing()
        ctx.log("-" * 60)


if __name__ == "__main__":
    update_application()