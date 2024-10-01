import os
import sys

_DEVNULL = open(os.devnull, "w")
_ORIG_STDOUT = sys.stdout
_CLEAR_LINE = "\x1b[1A\x1b[2K"
DELIM = 89 * "="

RESET = '\033[0m'
BOLD = '\033[1m'
RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = "\033[1;33m"
BLUE = '\033[34m'


def invalidate_print():
    global _DEVNULL
    sys.stdout = _DEVNULL


def restore_print():
    global _ORIG_STDOUT
    sys.stdout = _ORIG_STDOUT


def printf(text, end="\n"):
    global _ORIG_STDOUT, _DEVNULL
    sys.stdout = _ORIG_STDOUT
    print(text, end=end)
    sys.stdout = _DEVNULL


def clear_line(lines=1):
    printf(lines * _CLEAR_LINE)


def print_error(text):
    printf(f"[{BOLD}{RED}!{RESET}] {text}")


def print_info(text, end="\n"):
    printf(f"[{BOLD}{BLUE}*{RESET}] {text}", end=end)


def print_cmd(text):
    printf(f"[{BOLD}{GREEN}>{RESET}] {text}")


BANNER = f"""
{GREEN}     _______.{RESET}____    ____  _______.{GREEN}___________.{RESET}    ___      .___  ___.  _______ .______      
{GREEN}    /       |{RESET}\   \  /   / /       {GREEN}|           |{RESET}   /   \     |   \/   | |   ____||   _  \     
{GREEN}   |   (----`{RESET} \   \/   / |   (----`{GREEN}---|  |----`{RESET}  /  ^  \    |  \  /  | |  |__   |  |_)  |    
{GREEN}    \   \    {RESET}  \_    _/   \   \    {GREEN}   |  |     {RESET} /  /_\  \   |  |\/|  | |   __|  |      /     
{GREEN}.----)   |   {RESET}    |  | .----)   |   {GREEN}   |  |     {RESET}/  _____  \  |  |  |  | |  |____ |  |\  \\
{GREEN}|_______/    {RESET}    |__| |_______/    {GREEN}   |__|    {RESET}/__/     \__\ |__|  |__| |_______|| _| \._\\
"""