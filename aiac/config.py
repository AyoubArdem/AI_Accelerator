from pathlib import Path
import json
import os
import stat

def get_config():
    api_base_url = "http://127.0.0.1:8000"
    return type("Config", (object,), {"api_base_url": api_base_url})()


def save_config(data: dict, api_base_url: str):
    folder = Path.home() / ".aiac"
    folder.mkdir(parents=True, exist_ok=True)
    config_file = folder / "config.json"

    with open(config_file, "w") as f:
        json.dump({"API_BASE_URL": api_base_url, **data}, f, indent=4)
    # Best-effort permissions hardening for non-Windows platforms.
    if os.name != "nt":
        try:
            os.chmod(config_file, stat.S_IRUSR | stat.S_IWUSR)
        except Exception:
            pass
    return folder

def load_config():
    folder = Path.home() / ".aiac"
    config_file = folder / "config.json"
    if config_file.exists():
        with open(config_file, "r") as f:
            data = json.load(f)
        return data
    else:
        return {}

def delete_config():
    folder = Path.home() / ".aiac"
    config_file = folder / "config.json"
    try:
        if config_file.exists():
            config_file.unlink()
    except Exception:
        pass
