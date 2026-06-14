import json
import threading
import time
from pathlib import Path

from ..config import (
    APP_EVENTS_LOG_FILENAME,
    DELIVERY_HISTORY_LOG_FILENAME,
    PERSISTENT_LOG_DIR,
    TIMESTAMP_MS_MULTIPLIER,
)


_log_lock = threading.Lock()


def _timestamp_ms():
    return round(time.time() * TIMESTAMP_MS_MULTIPLIER)


def _log_path(filename, log_dir=PERSISTENT_LOG_DIR):
    return Path(log_dir) / filename


def append_jsonl(filename, payload, log_dir=PERSISTENT_LOG_DIR):
    entry = dict(payload)
    entry.setdefault("ts", _timestamp_ms())

    path = _log_path(filename, log_dir)
    line = json.dumps(entry, ensure_ascii=False, sort_keys=True)

    with _log_lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    return entry


def read_jsonl(filename, log_dir=PERSISTENT_LOG_DIR):
    path = _log_path(filename, log_dir)
    if not path.exists():
        return []

    entries = []
    with _log_lock:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def append_app_event(payload, log_dir=PERSISTENT_LOG_DIR):
    event = {"type": "app_event", **dict(payload)}
    return append_jsonl(APP_EVENTS_LOG_FILENAME, event, log_dir)


def append_delivery_history(payload, log_dir=PERSISTENT_LOG_DIR):
    event = {"type": "delivery_history", **dict(payload)}
    return append_jsonl(DELIVERY_HISTORY_LOG_FILENAME, event, log_dir)


def read_delivery_history(log_dir=PERSISTENT_LOG_DIR):
    return [
        entry
        for entry in read_jsonl(DELIVERY_HISTORY_LOG_FILENAME, log_dir)
        if entry.get("type") == "delivery_history"
    ]
