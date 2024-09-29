import json
from .output_manager import *
from typing import Any, Dict

COMMANDS_DICT = {
    "/browse": "Start navigating your file system.",
    "/upload": "Upload a file to the server.",
    "/list_uploads": "Uploads directory contents.",
    "/system": "Get system resource usage.",
    "/processes": "List running processes.",
    "/kill <PID>": "Kill a process by its PID.",
    "/screenshot": "Take a screenshot and send it.",
    "/login <PASSWORD>": "Authenticate the session.",
    "/logout": "De-authenticate the session."
}


def load_config(conf_path: str) -> Dict[str, Any]:
    try:
        with open(conf_path, 'r') as file:
            data = json.load(file)
        return data
    except FileNotFoundError as e:
        print_error(f"Config path not found -> {conf_path}")
        raise e
    except json.JSONDecodeError as e:
        print_error(f"Error decoding config -> {conf_path}.")
        raise e


