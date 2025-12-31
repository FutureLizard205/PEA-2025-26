import os
from pathlib import Path
from datetime import datetime

from ..config import DEBUG_PRINTS

# TODO: Improve performance with python's logging library?

# Log file path (created automatically if needed)
LOG_FILE = Path("latest.log")

def log(*args, **kwargs):
    """
    Logs a message to a file, and optionally to stdout, depending on DEBUG_PRINTS.
    Accepts same arguments as print().
    """
    message = " ".join(str(a) for a in args)
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S] ")
    full_message = timestamp + message + "\n"

    if DEBUG_PRINTS:
        print(full_message, end="", **kwargs)

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(full_message)

def init_log_file():
    """
    Inits the log file.
    Deletes the log file if one exists.
    """
    if LOG_FILE.exists():
        os.remove(LOG_FILE)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S] ")
        f.write(timestamp + "Logger initialized started.\n")