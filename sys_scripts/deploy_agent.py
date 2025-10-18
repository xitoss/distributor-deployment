from flask import Flask, request, jsonify
import subprocess
import threading

app = Flask(__name__)

def run_script(script_name):
    cmd = ["python3", f"sys_scripts/{script_name}.py"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.stdout + proc.stderr

@app.route("/api/restore", methods=["POST"])
def restore():
    threading.Thread(target=run_script, args=("restore_database",)).start()
    return jsonify({"status": "ok", "message": "Restore process started"})

@app.route("/api/backup", methods=["POST"])
def backup():
    threading.Thread(target=run_script, args=("backup_database",)).start()
    return jsonify({"status": "ok", "message": "Backup process started"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=6001)
