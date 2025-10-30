#!/usr/bin/env python3
import subprocess
import sys
import re
import json
import time
from pathlib import Path

from sys_scripts.utils import (
    Context,
    ENV_FILE,
    PROJECT_ROOT,
    RUNNING_APP_VERSION,
    LATEST_APP_VERSION,
)

VERSION_JSON_FILE = PROJECT_ROOT / "version/version.json"


VERSION_PATTERN = re.compile(r"^v\d+\.\d+\.\d+$")

# -------------------------
# Basic loaders / verifiers
# -------------------------
def validate_version_from_env():
    if not RUNNING_APP_VERSION:
        return False, "RUNNING_APP_VERSION in .env is not available"
    if not LATEST_APP_VERSION:
        return False, "LATEST_APP_VERSION in .env is not available"

    if not VERSION_PATTERN.match(RUNNING_APP_VERSION):
        return False, "RUNNING_APP_VERSION in .env is not valid or corrupted!"
    
    if not VERSION_PATTERN.match(LATEST_APP_VERSION):
        return False, "LATEST_APP_VERSION in .env is not valid or corrupted!"
    
    return True, None

def load_version_json():
    """Return (True, data_dict) or (False, error_msg)"""
    if not VERSION_JSON_FILE.exists():
        return False, "Missing version.json (risky to continue)"
    try:
        data = json.loads(VERSION_JSON_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False, "version.json is invalid JSON"
    if not isinstance(data, dict) or "running" not in data or "latest" not in data:
        return False, "version.json missing required keys (running/latest)"
    return True, data

def varify_update(to_update):
    if not VERSION_PATTERN.match(to_update):
        return False, f"{to_update} is not a valid version of this application."
    
    if RUNNING_APP_VERSION == to_update:
        return False, f"RUNNING_APP_VERSION is already installed ({to_update})"
    
    return True, None

def update_env(to_update: str):
    """Safely update RUNNING_APP_VERSION in .env file."""

    if not ENV_FILE.exists():
        return False, f".env file not found at {ENV_FILE}"

    try:
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
        new_lines = []
        updated = False

        for line in lines:
            if line.strip().startswith("RUNNING_APP_VERSION="):
                new_lines.append(f"RUNNING_APP_VERSION={to_update}")
                updated = True
            else:
                new_lines.append(line)

        # If key didn’t exist, append at the end
        if not updated:
            new_lines.append(f"RUNNING_APP_VERSION={to_update}")

        # Backup current .env
        backup_file = ENV_FILE.with_suffix(".bak")
        backup_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        # Write new version
        ENV_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

        return True, None

    except Exception as e:
        return False, f"Failed to update .env file: {e}"


# -------------------------
# File update helpers
# -------------------------
def update_json_version(to_update: str):
    """Update 'running' in version.json"""
    ok, data_or_err = load_version_json()
    if not ok:
        return False, data_or_err
    data = data_or_err
    data["running"] = to_update
    try:
        VERSION_JSON_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")
        return True, None
    except Exception as e:
        return False, f"Failed to write version.json: {e}"


# -------------------------
# Docker / Compose helpers
# -------------------------
def run_compose_up_build_web(ctx: Context, project_dir: Path):
    """
    Bring up web service with build. Tries `docker compose` then `docker-compose`.
    Returns (True, out) or (False, err)
    """
    cmds = [
        ["docker", "compose", "up", "-d", "--build", "web"],
        ["docker-compose", "up", "-d", "--build", "web"],
    ]
    for cmd in cmds:
        ctx.log(f"Running: {' '.join(cmd)} (cwd={project_dir})")
        try:
            proc = subprocess.run(cmd, cwd=str(project_dir), capture_output=True, text=True, timeout=900)
            if proc.returncode == 0:
                ctx.log("Compose returned success.")
                return True, proc.stdout
            else:
                # keep trying next cmd; but log the error
                ctx.log(f"Compose command failed (rc={proc.returncode}). stdout: {proc.stdout} stderr: {proc.stderr}")
        except FileNotFoundError:
            ctx.log(f"Command not found: {cmd[0]}")
        except subprocess.TimeoutExpired:
            ctx.log("Compose command timed out.")
    return False, "Both compose commands failed"


def get_compose_container_name(service_name="web", compose_project_label="xitoss-distributor"):
    """
    Return the name of the first container for the compose service.
    Uses docker ps filters to find the container name.
    """
    try:
        result = subprocess.run(
            [
                "docker", "ps",
                "--filter", f"label=com.docker.compose.service={service_name}",
                "--filter", f"label=com.docker.compose.project={compose_project_label}",
                "--format", "{{.Names}}"
            ],
            capture_output=True, text=True, timeout=10
        )
        names = result.stdout.strip().splitlines()
        if names:
            return names[0]
    except Exception:
        pass
    return None


def is_container_running(container_name: str):
    """Return True if container exists and its .State.Status == 'running'"""
    if not container_name:
        return False
    try:
        proc = subprocess.run(["docker", "inspect", container_name, "--format", "{{.State.Status}}"],
                              capture_output=True, text=True, timeout=5)
        status = proc.stdout.strip()
        return status == "running"
    except Exception:
        return False


def wait_for_container_running(ctx: Context, service_name="web", timeout=120, poll_interval=5):
    """Poll Docker until the container is in 'running' state or timeout"""
    start = time.time()
    while True:
        container_name = get_compose_container_name(service_name=service_name)
        if container_name:
            ctx.log(f"Found container: {container_name}. Checking status...")
            if is_container_running(container_name):
                ctx.log(f"Container {container_name} is running.")
                return True, container_name
            else:
                ctx.log(f"Container {container_name} not running yet.")
        else:
            ctx.log("No container found for service yet.")

        if time.time() - start > timeout:
            return False, f"Timeout waiting for {service_name} container to run"
        time.sleep(poll_interval)


# -------------------------
# Main update flow
# -------------------------

def update_application(version=None):
    ctx = Context("update")
    ctx.log("== Distributor Update Application ===", append=False)
    ctx.start_processing()
    ctx.load_env()

    try:
        valid_env, valid_env_err = validate_version_from_env()
        if not valid_env:
            ctx.log(valid_env_err)
            return
        ctx.log("Validation of versions in .env succeeded")

        valid_json, data_or_err = load_version_json()
        if not valid_json:
            ctx.log(data_or_err)
            return
        ctx.log("Version.json present and valid")

        to_update = version or LATEST_APP_VERSION

        valid_version, valid_version_err = varify_update(to_update)
        if not valid_version:
            ctx.log(valid_version_err)
            return
        ctx.log(f"Target version {to_update} selected for update")

        ok, err = update_env(to_update)
        if not ok:
            ctx.log(err)
            return
        ctx.log(f"Updated .env with RUNNING_APP_VERSION={to_update}")

        # ok, err = run_compose_up_build_web(ctx, PROJECT_ROOT)
        # if not ok:
        #     ctx.log(err)
        #     return
        # ctx.log("Docker rebuild successful")

        # ok, err = update_json_version(to_update)
        # if not ok:
        #     ctx.log(err)
        #     return
        # ctx.log("version.json updated successfully")

        # ok, container = wait_for_container_running(ctx)
        # if not ok:
        #     ctx.log(container)
        #     return
        # ctx.log(f"✅ Update completed successfully → {to_update}")

    finally:
        ctx.end_processing()


if __name__ == "__main__":
    version_arg = sys.argv[1] if len(sys.argv) > 1 else None
    update_application(version=version_arg)