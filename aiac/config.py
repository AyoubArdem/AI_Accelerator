from pathlib import Path
import json

def get_config():
    api_base_url = "http://localhost:8000/api"
    
    return type("Config", (object,), {"api_base_url": api_base_url})()

def save_config(data: dict, api_base_url: str):
    folder = Path.home() / ".aiac"
    folder.parent.mkdir(exist_ok=True)
    config_file = folder / "config.json"

    with open(config_file, "w") as f:
        json.dump({"API_BASE_URL": api_base_url, **data}, f, indent=4)
    return folder

def load_config():
    folder = Path.home() / ".aiac"
    config_file = folder / "config.json"
    if config_file.exists():
        with open(config_file, "r") as f:
            data = json.load(f)
        return data
    else:
        return f"Config file not found at {config_file}"