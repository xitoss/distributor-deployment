import json
import requests
from sys_scripts.utils import (
    VERSION_DIR, 
    REPO_LATEST_FILE_URL,
)

HOST_LATEST_VERSION_FILE = VERSION_DIR / "latest.json"
HOST_RUNNING_VERSION_FILE = VERSION_DIR / "running.json"


def check_update():
    """
    Fetch latest.json from the public GitHub repo,
    compare with local version/latest.json,
    and update if they differ.
    """
    try:
        # -------------------------------
        # 1. Fetch remote latest.json
        # -------------------------------
        response = requests.get(REPO_LATEST_FILE_URL, timeout=10)
        response.raise_for_status()
        remote_data = response.json()

        # -------------------------------
        # 2. Read local latest.json
        # -------------------------------
        if HOST_LATEST_VERSION_FILE.exists():
            with open(HOST_LATEST_VERSION_FILE, "r", encoding="utf-8") as f:
                local_data = json.load(f)
        else:
            local_data = {}

        # read local running.json
        if HOST_RUNNING_VERSION_FILE.exists():
            with open(HOST_RUNNING_VERSION_FILE, "r", encoding="utf-8") as f:
                local_running_data = json.load(f)
        else:
            local_running_data = {}

        # -------------------------------
        # 3. Compare
        # -------------------------------
        if remote_data != local_data:
            # Update local file
            with open(HOST_LATEST_VERSION_FILE, "w", encoding="utf-8") as f:
                json.dump(remote_data, f, indent=4)
            return {
                "success": True,
                "updated": True,
                "message": "A new version of found, updated /version/latest.json on host",
            }
        
        elif remote_data == local_running_data:
            return {
                "success": True,
                "updated": False,
                "message": "Application running version already up to date with latest available version"
            }

        return {
            "success": True,
            "updated": False,
            "message": "Application could be updated to a latest version as of /version/latest.json",
        }

    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"Network error: {str(e)}"}

    except json.JSONDecodeError:
        return {"success": False, "error": "Invalid JSON in remote or local file."}

    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    result = check_update()
    print(json.dumps(result, indent=2))
