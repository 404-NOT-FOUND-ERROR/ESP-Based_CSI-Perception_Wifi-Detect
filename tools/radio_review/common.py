# SPDX-License-Identifier: Apache-2.0
"""Shared, bounded input validation for offline radio review."""
import hashlib
import json
from pathlib import Path

MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_POINTS = 6000


def integer(row, name, low=0, high=0xFFFFFFFF):
    value = row.get(name)
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name}: expected integer in {low}..{high}")
    return value


def flag(row, name, wire=False):
    value = row.get(name)
    if type(value) is bool:
        return value
    if wire and type(value) is int and value in (0, 1):
        return bool(value)
    raise ValueError(f"{name}: expected {'0/1 or ' if wire else ''}boolean")


def source_info(source):
    path = Path(source)
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("capture exceeds 64 MiB; split the recording first")
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            if size > MAX_INPUT_BYTES:
                raise ValueError("capture exceeds 64 MiB; split the recording first")
            digest.update(chunk)
    return {"name": path.name, "bytes": size, "sha256": digest.hexdigest()}


def load_json(source):
    path = Path(source)
    with path.open("rb") as stream:
        raw = stream.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("capture exceeds 64 MiB; split the recording first")
    info = {"name": path.name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    data = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("expected JSON object")
    return data, info


def transitions(points):
    """Label intervals end at the next sample; the final point adds no invented time."""
    result = []
    for index, point in enumerate(points):
        key = (point["segment"], point["label"], point.get("distance_mm", 0), point["eligible"])
        if not result or result[-1]["key"] != key:
            result.append({"key": key, "start_s": point["t"], "end_s": point["t"],
                           "label": point["label"], "eligible": point["eligible"],
                           "distance_mm": point.get("distance_mm", 0), "count": 0,
                           "first_index": index, "last_index": index})
        result[-1]["count"] += 1
        result[-1]["last_index"] = index
        if index + 1 < len(points) and points[index + 1]["segment"] == point["segment"]:
            result[-1]["end_s"] = points[index + 1]["t"]
    for item in result:
        del item["key"]
        item["duration_s"] = round(item["end_s"] - item["start_s"], 6)
    return result
