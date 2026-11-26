"""Append-only structured event JSONL storage."""

import json
import os
from datetime import datetime, timezone
from typing import Iterable


def append_event(event: dict, data_dir: str = "data", filename: str = "anomaly_events.jsonl") -> str:
    if not isinstance(event, dict):
        raise TypeError("event must be a dictionary")
    events_dir = os.path.join(data_dir, "events")
    os.makedirs(events_dir, exist_ok=True)
    path = os.path.join(events_dir, filename)
    record = dict(event)
    record.setdefault("timestamp", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")
    return os.path.abspath(path)


def read_events(path: str) -> list:
    records = []
    if not os.path.isfile(path):
        return records
    with open(path, "r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                raise ValueError(f"Malformed JSONL record at line {line_number}")
    return records
