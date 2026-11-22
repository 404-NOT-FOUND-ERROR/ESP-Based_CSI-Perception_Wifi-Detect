# SPDX-License-Identifier: Apache-2.0
"""Validate N1 exports and replay the explicitly supported historical filter."""
import re
import statistics
from collections import Counter, deque

from common import flag, integer, load_json, transitions

LABELS = {0: "未标记", 1: "安静站定", 2: "走远", 3: "走近", 4: "原地转身",
          5: "手机放进口袋", 6: "身体遮挡", 7: "主机移动"}
PROFILE = {"interval_ms": 500, "window": 8, "median_points": 3,
           "delta_db": 6, "stable_db": 2, "confirm_reads": 3}
MASK = 0xFFFFFFFF


class Replay:
    def __init__(self):
        self.history = deque(maxlen=8)
        self.candidate = self.hits = 0

    def reset(self):
        self.history.clear()
        self.candidate = self.hits = 0

    def read(self, rssi):
        self.history.append(rssi)
        if len(self.history) < 8:
            return 0
        values = list(self.history)
        delta = statistics.median(values[5:8]) - statistics.median(values[:3])
        next_trend = 3 if delta >= 6 else 2 if delta <= -6 else 1 if abs(delta) <= 2 else 0
        if next_trend != self.candidate:
            self.candidate, self.hits = next_trend, 1
        else:
            self.hits = min(self.hits + 1, 3)
        return next_trend if self.hits >= 3 else 0


def analyze(source):
    data, info = load_json(source)
    if data.get("schema") != "airboat.hotspot-probe.v1":
        raise ValueError("expected airboat.hotspot-probe.v1")
    if not isinstance(data.get("boot"), str) or not re.fullmatch(r"[0-9a-f]{32}", data["boot"]):
        raise ValueError("boot: expected 32 lowercase hex characters")
    meta = data.get("meta")
    if not isinstance(meta, dict):
        raise ValueError("meta: expected object")
    simulated = flag(meta, "simulated")
    if flag(data, "measurement_age_known") or flag(meta, "measurement_age_known"):
        raise ValueError("N1 v1 records API read times; original measurement age is unknown")
    if flag(meta, "recording"):
        raise ValueError("export must contain a stopped recording")
    run = integer(meta, "run", 1)
    role = integer(meta, "role", 1, 2)
    count = integer(meta, "count", 0, 1200)
    capacity = integer(meta, "capacity", 1, 1200)
    oldest, latest = integer(meta, "oldest"), integer(meta, "latest")
    overwritten = integer(meta, "overwritten")
    missed = integer(meta, "missed_reads")
    rows = data.get("records")
    if not isinstance(rows, list) or len(rows) != count or count > capacity:
        raise ValueError("record count/capacity mismatch")
    if (count and (oldest != latest - count + 1 or overwritten != latest - count)) or (
            not count and (oldest or latest or overwritten)):
        raise ValueError("ring bounds/overwrite counters disagree")
    if overwritten and count != capacity:
        raise ValueError("overwritten ring must retain capacity records")
    params = data.get("trend_parameters")
    if not isinstance(params, dict) or params != meta.get("parameters"):
        raise ValueError("export and status parameters disagree")
    # Future profiles remain inspectable, with replay explicitly unavailable.
    replay_supported = params == PROFILE and all(type(v) is int for v in params.values())
    replay = Replay()
    points, previous = [], None
    segment = elapsed_ms = source_changes = read_gaps = observed_missed = wraps = 0
    valid_count = unpaired = mismatches = 0
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError("record must be an object")
        ident = integer(row, "id", 1)
        if ident != oldest + index:
            raise ValueError("record IDs are incomplete or unordered")
        seq = integer(row, "sample_seq", 1)
        read_ms = integer(row, "read_ms")
        generation = integer(row, "network_generation")
        valid, paired = flag(row, "valid", True), flag(row, "paired", True)
        flag(row, "ftm_responder", True)
        error = integer(row, "read_error", -(2**31), 2**31 - 1)
        rssi = integer(row, "rssi_dbm", -128, 127)
        channel = integer(row, "channel", 0, 255)
        label = integer(row, "label", 0, 7)
        distance = integer(row, "distance_mm", 0, 100000)
        recorded = integer(row, "trend", 0, 3)
        mac = row.get("bssid")
        if not isinstance(mac, str) or not re.fullmatch(r"[0-9a-f]{12}", mac):
            raise ValueError("bssid: expected lowercase MAC hex")
        if valid and (not generation or not channel or not -127 <= rssi <= -1 or error or
                      mac == "000000000000" or int(mac[:2], 16) & 1):
            raise ValueError("valid observation has invalid source, signal or driver error")
        if not paired and (label or distance):
            raise ValueError("unpaired samples must have unknown label and no distance")
        if not valid and recorded:
            raise ValueError("invalid observation cannot carry a confirmed trend")
        identity = (generation, mac, channel)
        reset = previous is None or not valid or not previous["valid"]
        if previous:
            step = (read_ms - previous["read_ms"]) & MASK
            if step >= 2**31:
                raise ValueError("read time moved backwards without a plausible uint32 wrap")
            if read_ms < previous["read_ms"]:
                wraps += 1
            elapsed_ms += step
            seq_step = (seq - previous["seq"]) & MASK
            if not seq_step or seq_step >= 2**31:
                raise ValueError("read sequence duplicated or moved backwards")
            observed_missed += max(0, seq_step - 1)
            changed = identity != previous["identity"]
            source_changes += changed
            gap = step > 1000 or seq_step != 1
            read_gaps += gap
            reset = reset or changed or gap
        if reset:
            segment += 1
            replay.reset()
        replayed = replay.read(rssi) if valid and replay_supported else 0
        # Ring truncation and unexported stale-duplicate ticks can change firmware history.
        compared = replay_supported and len(replay.history) == 8 and replay.hits >= 3
        mismatches += bool(compared and replayed != recorded)
        valid_count += valid
        unpaired += not paired
        points.append({"t": elapsed_ms / 1000, "value": rssi if valid else None,
                       "eligible": valid, "label": label, "distance_mm": distance,
                       "segment": segment, "recorded_trend": recorded,
                       "replayed_trend": replayed if replay_supported else None,
                       "id": ident, "paired": paired})
        previous = {"valid": valid, "read_ms": read_ms, "seq": seq, "identity": identity}
    if observed_missed > missed:
        raise ValueError("visible missing reads exceed declared missed_reads")
    intervals = transitions(points)
    label_counts = Counter(str(point["label"]) for point in points)
    labelled = []
    for interval in intervals:
        matching = points[interval["first_index"]:interval["last_index"] + 1]
        expected = {2: 2, 3: 3}.get(interval["label"])
        hits = [p for p in matching if p["eligible"] and p["recorded_trend"] == expected] if expected else []
        labelled.append({**interval, "expected_trend": expected,
                         "first_matching_trend_s": round(hits[0]["t"] - interval["start_s"], 3) if hits else None,
                         "weakening_samples": sum(p["recorded_trend"] == 2 for p in matching),
                         "label_name": LABELS[interval["label"]]})
    signals = [p["value"] for p in points if p["value"] is not None]
    warnings = []
    if overwritten:
        warnings.append(f"主机环存已覆盖 {overwritten} 条；报告展示保留区间。")
    if mismatches:
        warnings.append(f"{mismatches} 条已积累窗口的回放趋势与设备记录不同，需结合采样时序核对。")
    if not replay_supported:
        warnings.append("该文件的趋势参数尚无对应回放配置，保留设备原趋势供查看。")
    if role == 1:
        warnings.append("手机标为固定放置；信号趋势用于查看链路变化。")
    return {"kind": "hotspot", "source": info, "simulated": simulated,
            "identity": f"{data['boot']} / run {run}", "title": "热点信号 · N1",
            "labels": LABELS, "points": points, "intervals": labelled,
            "summary": {"records": count, "valid": valid_count, "unpaired": unpaired,
                        "duration_s": points[-1]["t"] if points else 0,
                        "mean_pps": round((count - 1) / points[-1]["t"], 3) if count > 1 and points[-1]["t"] else None,
                        "overwritten": overwritten, "missed_reads": missed,
                        "observed_missing_reads": observed_missed, "source_changes": source_changes,
                        "discontinuities": read_gaps, "clock_wraps": wraps,
                        "min_dbm": min(signals) if signals else None,
                        "max_dbm": max(signals) if signals else None,
                        "median_dbm": statistics.median(signals) if signals else None,
                        "labels": dict(label_counts), "role": role},
            "replay": {"profile": "n1-9f81a8c" if replay_supported else None,
                       "parameters": params, "mismatches": mismatches,
                       "scope": "exported observations; duplicate stale ticks and overwritten history unavailable"},
            "warnings": warnings,
            "interpretation": "距离为人工标签；信号曲线用于比较本轮链路变化。趋势出现时间是标注对照，非跟随效果验收。"}
