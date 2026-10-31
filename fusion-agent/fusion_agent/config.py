"""User data folder, the small settings file and the session folders."""
import json
import os
import time
from pathlib import Path

from fusion_agent import term
from fusion_agent.agent import TUNED_MODEL

DEFAULTS = {
    "model": TUNED_MODEL,
    "think": False,
    "verbose": False,
    "screenshots": True,
}


def data_dir():
    """Windows %LOCALAPPDATA%\\fusion-agent, macOS ~/Library/Application Support/fusion-agent,
    Linux $XDG_DATA_HOME/fusion-agent (~/.local/share/fusion-agent)."""
    home = Path.home()
    if term.IS_WINDOWS:
        base = Path(os.environ.get("LOCALAPPDATA") or home / "AppData" / "Local")
    elif term.IS_MAC:
        base = home / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or home / ".local" / "share")
    return base / "fusion-agent"


def config_path():
    return data_dir() / "config.json"


def history_path():
    return data_dir() / "history.txt"


def load_settings():
    """The saved settings over the defaults; a broken or missing file gives the defaults."""
    settings = dict(DEFAULTS)
    try:
        with open(config_path(), encoding="utf-8") as file:
            saved = json.load(file)
    except (OSError, ValueError):
        return settings
    if not isinstance(saved, dict):
        return settings
    model = saved.get("model")
    if isinstance(model, str) and model.strip():
        settings["model"] = model.strip()
    for key in ("think", "verbose", "screenshots"):
        if isinstance(saved.get(key), bool):
            settings[key] = saved[key]
    return settings


def save_settings(settings):
    """Best effort: a settings file that cannot be written must not break the session."""
    try:
        data_dir().mkdir(parents=True, exist_ok=True)
        with open(config_path(), "w", encoding="utf-8") as file:
            json.dump({key: settings[key] for key in DEFAULTS}, file, indent=1)
        return True
    except OSError:
        return False


def new_session_dir():
    """<data dir>/sessions/<date-time>/ for the log and the pictures of one run."""
    stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    folder = data_dir() / "sessions" / stamp
    suffix = 2
    while folder.exists():
        folder = data_dir() / "sessions" / ("%s_%d" % (stamp, suffix))
        suffix += 1
    folder.mkdir(parents=True, exist_ok=True)
    return folder
