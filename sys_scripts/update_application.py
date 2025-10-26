#!/usr/bin/env python3
import subprocess
import re
import json
import time
from pathlib import Path

from sys_scripts.utils import Context, PROJECT_ROOT

VERSION_DIR = PROJECT_ROOT / "version"
VERSION_JSON_FILE = VERSION_DIR / "version.json"
VERSION_ENV_FILE = VERSION_DIR / ".env.version"

# env variable name in .env.version
RUNNING_VERSION = "RUNNING"
LATEST_VERSION = "LATEST"

VERSION_PATTERN = re.compile(r"^v\d+\.\d+\.\d+$")

# -------------------------
# Basic loaders / verifiers
# -------------------------
def load_version_env():
    """Return (True, dict) or (False, error_msg)"""
    if not VERSION_ENV_FILE.exists():
        return False, "Missing .env.version"
    env_data = {}
    for line in VERSION_ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env_data[k.strip()] = v.strip()
    return True, env_data


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


def varify_version(version: str) -> bool:
    if not version:
        return False
    return bool(VERSION_PATTERN.match(version))


def varify_update(running: str, to_update: str):
    if not running or not to_update:
        return False, "Missing version information"
    if not varify_version(running):
        return False, "Running version format invalid"
    if not varify_version(to_update):
        return False, "Target version format invalid"
    if running == to_update:
        return False, "Version is already installed"
    return True, None


# -------------------------
# File update helpers
# -------------------------
def update_env_version(to_update: str):
    """Update RUNNING= in .env.version (create if missing)."""
    if not VERSION_ENV_FILE.exists():
        return False, ".env.version missing"

    try:
        lines = VERSION_ENV_FILE.read_text(encoding="utf-8").splitlines()
    except Exception as e:
        return False, f"Failed to read .env.version: {e}"

    updated_lines = []
    found = False
    for line in lines:
        if line.strip().startswith(f"{RUNNING_VERSION}="):
            updated_lines.append(f"{RUNNING_VERSION}={to_update}")
            found = True
        else:
            updated_lines.append(line)
    if not found:
        # append at end
        updated_lines.append(f"{RUNNING_VERSION}={to_update}")

    try:
        VERSION_ENV_FILE.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
        return True, None
    except Exception as e:
        return False, f"Failed to write .env.version: {e}"


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
# High level step wrappers
# -------------------------
def step1_check_env_available():
    ok, data_or_err = load_version_env()
    if not ok:
        return False, data_or_err
    return True, data_or_err


def step2_check_json_available():
    ok, data_or_err = load_version_json()
    if not ok:
        return False, data_or_err
    return True, data_or_err


def step3_check_env_versions_valid(env_data: dict):
    running = env_data.get(RUNNING_VERSION)
    latest = env_data.get(LATEST_VERSION)
    if not running:
        return False, "RUNNING not defined in .env.version"
    if not latest:
        return False, "LATEST not defined in .env.version"
    if not varify_version(running):
        return False, f"RUNNING '{running}' is not a valid version string"
    if not varify_version(latest):
        return False, f"LATEST '{latest}' is not a valid version string"
    return True, (running, latest)


def step4_check_different(running: str, to_update: str):
    ok, msg = varify_update(running, to_update)
    if not ok:
        return False, msg
    return True, None


def step5_update_env(to_update: str):
    ok, err = update_env_version(to_update)
    if not ok:
        return False, err
    return True, None


def step6_compose_build(ctx: Context):
    ok, out_or_err = run_compose_up_build_web(ctx, PROJECT_ROOT)
    if not ok:
        return False, out_or_err
    return True, out_or_err


def step7_update_json(ctx: Context, to_update: str):
    ok, err = update_json_version(to_update)
    if not ok:
        return False, err
    return True, None


def step8_wait_ready(ctx: Context, timeout=180):
    ok, info = wait_for_container_running(ctx, timeout=timeout)
    if not ok:
        return False, info
    # Optionally: add further readiness checks like HTTP health endpoint here.
    # e.g., curl mapped port or check application specific endpoint.
    return True, info


# -------------------------
# Main update flow
# -------------------------
def update_application(version=None):
    ctx = Context("update")
    ctx.log("== Distributor Update Application ===", append=False)
    ctx.start_processing()

    try:
        # Step 1: load .env.version
        ok, env_or_err = step1_check_env_available(ctx)
        if not ok:
            ctx.log(f"STEP 1 FAILED: {env_or_err}")
            return False, env_or_err
        env_data = env_or_err
        ctx.log("STEP 1 OK: .env.version loaded")

        # Step 2: validate version.json exists and basic structure
        ok, json_or_err = step2_check_json_available(ctx)
        if not ok:
            ctx.log(f"STEP 2 FAILED: {json_or_err}")
            return False, json_or_err
        ctx.log("STEP 2 OK: version.json present and valid")

        # Step 3: ensure RUNNING & LATEST in env and valid format
        ok, running_latest = step3_check_env_versions_valid(ctx, env_data)
        if not ok:
            ctx.log(f"STEP 3 FAILED: {running_latest}")
            return False, running_latest
        running, latest = running_latest
        ctx.log(f"STEP 3 OK: running={running}, latest={latest}")

        # decide target
        to_update = version or latest

        # Step 4: ensure to_update is different & valid
        ok, msg = step4_check_different(ctx, running, to_update)
        if not ok:
            ctx.log(f"STEP 4 FAILED: {msg}")
            return False, msg
        ctx.log(f"STEP 4 OK: Will update from {running} -> {to_update}")

        # Step 5: update .env.version (RUNNING=)
        ok, msg = step5_update_env(ctx, to_update)
        if not ok:
            ctx.log(f"STEP 5 FAILED: {msg}")
            return False, msg
        ctx.log(f"STEP 5 OK: Updated .env.version RUNNING={to_update}")

        # Step 6: docker compose up -d --build web
        ok, out_or_err = step6_compose_build(ctx)
        if not ok:
            ctx.log(f"STEP 6 FAILED (compose): {out_or_err}")
            return False, out_or_err
        ctx.log("STEP 6 OK: Compose build/up succeeded")

        # Step 7: update version.json → set running = to_update
        ok, msg = step7_update_json(ctx, to_update)
        if not ok:
            ctx.log(f"STEP 7 FAILED: {msg}")
            # NOTE: At this stage .env.version already changed and container built.
            return False, msg
        ctx.log("STEP 7 OK: version.json running value updated")

        # Step 8: wait until web container is running / ready
        ok, info = step8_wait_ready(ctx, timeout=180)
        if not ok:
            ctx.log(f"STEP 8 FAILED: {info}")
            return False, info
        ctx.log(f"STEP 8 OK: {info}")

        ctx.log("Update completed successfully.")
        return True, None

    finally:
        ctx.end_processing()
