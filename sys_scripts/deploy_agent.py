#!/usr/bin/env python3
import os
import json
import subprocess
from flask import Flask, request, jsonify

app = Flask(__name__)

AGENT_KEY = os.getenv("AGENT_KEY")
BACKUP_SCRIPT = "/workspace/sys_scripts/backup_database.py"
RESTORE_SCRIPT = "/workspace/sys_scripts/restore_database.py"
CHECK_UPDATE = "/workspace/sys_scripts/check_update.py"
APP_UPDATE = "/workspace/sys_scripts/update_application.py"

def run_script(script_path):
    try:
        result = subprocess.run(
            ["python3", script_path],
            capture_output=True,
            text=True,
            cwd="/workspace"  # Run inside distributor-deployment
        )
        return {
            "success": result.returncode == 0,
            "output": (result.stdout or "") + (result.stderr or "")
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

# -------------------------------
# AUTH DECORATOR
# -------------------------------
def require_agent_key(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        key = request.headers.get("X-AGENT-KEY")
        if key != AGENT_KEY:
            return jsonify({"error": "Unauthorized"}), 401
        return func(*args, **kwargs)
    return wrapper

# -------------------------------
# ROUTES
# -------------------------------
@app.route("/api/backup", methods=["POST"])
@require_agent_key
def api_backup():
    result = run_script(BACKUP_SCRIPT)
    return jsonify(result)

@app.route("/api/restore", methods=["POST"])
@require_agent_key
def api_restore():
    result = run_script(RESTORE_SCRIPT)
    return jsonify(result)

@app.route("/api/ping", methods=["GET"])
def ping():
    return jsonify({"status": "ok"})

# @app.route("/api/check-update", methods=["GET"])
# @require_agent_key
# def api_check_update():
#     result = run_script(CHECK_UPDATE)
#     return jsonify(result)

@app.route("/api/check-update", methods=["GET"])
@require_agent_key
def api_check_update():
    result = run_script(CHECK_UPDATE)

    if isinstance(result, dict) and "output" in result:
        try:
            # Parse the script’s printed JSON string
            parsed_output = json.loads(result["output"])
            return jsonify(parsed_output)
        except json.JSONDecodeError:
            return jsonify({
                "success": False,
                "error": "Invalid JSON output to display"
            })
    else:
        return jsonify({
            "success": False,
            "error": "Unexpected result from api"
        })

@app.route("/api/update-app", methods=["POST"])
@require_agent_key
def update_application():
    result = run_script(APP_UPDATE)
    return jsonify(result)



# -------------------------------
if __name__ == "__main__":
    host = os.getenv("AGENT_HOST", "0.0.0.0")
    port = int(os.getenv("AGENT_PORT", "6001"))
    app.run(host=host, port=port)

