import json

from .output_manager import *
from typing import Any, Dict
from pathlib import Path

COMMANDS_DICT = {
    "start": "Get the list of all commands",
    "login": "Authenticate the session",
    "browse": "Navigate file system",
    "upload": "Upload a file to the server",
    "list_uploads": "Uploads directory contents",
    "system": "Get system resource usage",
    "processes": "List running processes",
    "kill": "Kill a process by its PID",
    "screenshot": "Take & send a screenshot",
    "logout": "De-authenticate the session",
    "help": "Refers to /start"
}

PARAMS_DICT = {
    "login": ["PASS"],
    "kill": ["PID"]
}


def generate_cmd_dict_msg(description, commands: dict) -> str:
    # todo  make this generic and output other stats like this as well
    header = f"{description}:\n| Command       | Description                    |\n"
    separator = "|---------------|--------------------------------|\n"

    # Create the table with the header and separator
    table = header + separator

    # Loop through the dictionary to create each row
    for command, description in commands.items():
        # Formatting each row to have aligned columns
        if command in PARAMS_DICT:
            command += "\t" + ','.join([f"<{arg}>" for arg in PARAMS_DICT[command]])
        command = "/" + command
        table += f"| {command:<13} | {description:<30} |\n"

    return f"```{table}```"


def load_config(conf_path: Path) -> Dict[str, Any]:
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


