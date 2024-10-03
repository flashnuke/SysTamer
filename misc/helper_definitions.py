import json

from .output_manager import *
from typing import Any, Dict, List
from pathlib import Path

COMMANDS_DICT = {
    "start": "Get the list of all commands",
    "login": "Authenticate the session",
    "browse": "Navigate file system",
    "upload": "Upload a file to the server",
    "list_uploads": "Uploads directory contents",
    "system": "Get system resource usage",
    "processes": "Active processes <F=FILTER>",
    "kill": "Kill a process by its PID",
    "screenshot": "Take & send a screenshot",
    "logout": "De-authenticate the session",
    "help": "Refers to /start"
}

PARAMS_DICT = {
    "login": ["PASS"],
    "processes": ["F"],
    "kill": ["PID"]
}


def generate_cmd_dict_msg(description, commands: dict) -> str:
    header = f"{description}:\n| Command        | Description                    |\n"
    separator = "|----------------|--------------------------------|\n"

    # Create the table with the header and separator
    table = header + separator

    # Loop through the dictionary to create each row
    for command, description in commands.items():
        # Formatting each row to have aligned columns
        if command in PARAMS_DICT:
            command += "\t" + ','.join([f"<{arg}>" for arg in PARAMS_DICT[command]])
        command = "/" + command
        table += f"| {command:<14} | {description:<30} |\n"

    return f"```{table}```"


def generate_proc_dict_msg(description, processes: list) -> List[str]:
    table_header = f"{description}\n| PID   | Name                 | CPU (%) | Memory (%)  |\n"
    separator = "|-------|----------------------|---------|-------------|\n"
    table = table_header + separator
    chunks = list()

    for proc in processes:
        pid = str(proc['pid']).ljust(5)
        name = (proc['name'] or "N/A")[:20].ljust(20)  # truncate if longer than 20 characters, handle None
        cpu = f"{proc['cpu_percent']:.1f}".ljust(7)
        mem = f"{round(proc['memory_percent'], 1):.1f}".ljust(11)

        table += f"| {pid} | {name} | {cpu} | {mem} |\n"
        if len(table) > 3500:  # Telegram's max message size is about 4096 bytes
            chunks.append(table)
            table = table_header + separator

    chunks.append(table)
    return chunks


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


