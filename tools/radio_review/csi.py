# SPDX-License-Identifier: Apache-2.0
"""Build a bounded timeline using the CSI component's validated public file contract."""
import importlib.util
from pathlib import Path

from common import MAX_POINTS, source_info

LABELS = {0: "未标记", 1: "房间安静", 2: "人在走动", 3: "主机移动", 4: "遮挡对照"}


def load_analyzer():
    path = Path(__file__).resolve().parents[2] / "components/app_csi_probe/host/analyze_capture.py"
    spec = importlib.util.spec_from_file_location("airboat_csi_quality", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.analyze


def analyze(source):
    info = source_info(source)
    # Validate first, then retain a bounded curve while counting all frames and transitions.
    quality = load_analyzer()(source)
    stride = max(1, (quality["frames"] + MAX_POINTS - 1) // MAX_POINTS)
    points, intervals = [], []
    origin = last = previous_time = None
    segment = frame_index = 0
    global_gap_us = 0
    histogram = [0] * 17
    previous_key = None

    def visit(row):
        nonlocal origin, last, previous_time, segment, frame_index, global_gap_us, previous_key
        at = row["callback_us"]
        if origin is None:
            origin = at
        key = (row["run"], row["network_generation"], row["source"], row["channel"],
               row["rx_format"], row["length"], row["motion_epoch"])
        gap = at - previous_time if previous_time is not None else 0
        global_gap_us = max(global_gap_us, gap)
        if previous_key == key and previous_time is not None:
            histogram[min(16, gap // 50000)] += 1
        if previous_key != key or gap > 1000000:
            segment += 1
        point = {"t": (at - origin) / 1000000, "value": row["rssi_dbm"],
                 "eligible": row["motion_eligible"], "label": row["label"],
                 "segment": segment, "id": row["id"],
                 "gap_ms": gap / 1000 if previous_time is not None else None,
                 "invalid_prefix": row["first_word_invalid"]}
        label_key = (segment, row["label"], row["motion_eligible"])
        if intervals and intervals[-1]["key"][0] == segment:
            intervals[-1]["end_s"] = point["t"]
        if intervals and intervals[-1]["key"] == label_key:
            intervals[-1]["count"] += 1
        else:
            intervals.append({"key": label_key, "start_s": point["t"], "end_s": point["t"],
                              "label": row["label"], "eligible": row["motion_eligible"], "count": 1})
        if frame_index % stride == 0:
            points.append(point)
        last = point
        previous_time, previous_key = at, key
        frame_index += 1

    second_quality = load_analyzer()(source, visitor=visit)
    if quality != second_quality or source_info(source) != info:
        raise ValueError("capture changed during analysis; use a completed immutable export")
    if last and (not points or last["id"] != points[-1]["id"]):
        points.append(last)
    for interval in intervals:
        del interval["key"]
        interval["label_name"] = LABELS[interval["label"]]
        interval["duration_s"] = round(interval["end_s"] - interval["start_s"], 6)
    counters = quality["counters"]
    warnings = []
    loss = counters["full_drops"] + counters["contended_drops"]
    if loss:
        warnings.append(f"入口队满／竞争合计丢弃 {loss} 次；原始计数保留在质量记录。")
    if counters["queued"] or counters["discarded"]:
        warnings.append("部分接受帧仍在队列或已被丢弃，详见计数；本文件包含已导出的帧。")
    return {"kind": "csi", "source": info, "simulated": quality["simulated"],
            "identity": quality["capture_id"], "title": "CSI 收样 · R1",
            "labels": LABELS, "points": points, "intervals": intervals,
            "summary": {"records": quality["frames"], "valid": quality["motion_eligible"],
                        "duration_s": last["t"] if last else 0, "stride": stride,
                        "max_gap_ms": global_gap_us / 1000, "gap_bins_50ms": histogram,
                        "labels": quality["labels"], "first_word_invalid": quality["first_word_invalid_frames"]},
            "quality": quality, "warnings": warnings,
            "interpretation": "曲线显示接收信号和收样间隔。载荷保留原始布局，活动检测将在真实格式确认后评估。"}
