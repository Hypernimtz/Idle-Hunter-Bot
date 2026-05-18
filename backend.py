import asyncio
import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

state_lock = asyncio.Lock()
DEGRADED_MODE = False


def atomic_json_save(path: str, payload: dict) -> None:
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4)
    os.replace(tmp_path, path)


def save_with_retries(path: str, payload: dict, retries: int = 1) -> None:
    global DEGRADED_MODE
    last_err = None
    for _ in range(retries + 1):
        try:
            atomic_json_save(path, payload)
            return
        except OSError as e:
            last_err = e
            logger.exception("Save failed for %s", path)
    DEGRADED_MODE = True
    raise OSError(f"Failed to save {path} after retries") from last_err


def load_json_file(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def ensure_backup_dir(backup_dir: str) -> None:
    os.makedirs(backup_dir, exist_ok=True)


def backup_json_file(path: str, backup_dir: str) -> None:
    if not os.path.exists(path):
        return
    ensure_backup_dir(backup_dir)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    base_name = os.path.basename(path)
    backup_path = os.path.join(backup_dir, f"{base_name}.{timestamp}.bak")
    try:
        with open(path, "r", encoding="utf-8") as src:
            payload = src.read()
        with open(backup_path, "w", encoding="utf-8") as dst:
            dst.write(payload)
    except OSError:
        logger.exception("Backup failed for %s", path)


def prune_backups(path: str, backup_dir: str, max_backups: int) -> None:
    if not os.path.isdir(backup_dir):
        return
    base_name = os.path.basename(path)
    prefix = f"{base_name}."
    backups = [
        os.path.join(backup_dir, name)
        for name in os.listdir(backup_dir)
        if name.startswith(prefix) and name.endswith(".bak")
    ]
    backups.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    for old_backup in backups[max_backups:]:
        try:
            os.remove(old_backup)
        except OSError:
            logger.exception("Could not remove old backup %s", old_backup)

USERS_FILE = "users_info.json"
TRIBE_FILE = "tribe_info.json"
CONFIG_FILE = "config.json"
LOTTERY_FILE = "lottery.json"

BACKUP_DIR = "backups"
BACKUP_INTERVAL_SECONDS = 60 * 60 * 24
MAX_BACKUPS_PER_FILE = 7