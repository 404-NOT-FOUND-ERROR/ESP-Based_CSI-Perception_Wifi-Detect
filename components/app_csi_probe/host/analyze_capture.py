#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Validate a CSI JSONL capture and summarize data quality, without activity inference."""
import argparse
import csv
import hashlib
import json
import re
import tempfile
from collections import Counter
from pathlib import Path

MAX_LINE = 8192
MAX_GROUPS = 256
COUNTERS = (
    "exported_frames", "accepted", "full_drops", "contended_drops", "source_drops",
    "invalid_drops", "old_run_drops", "discarded", "queued",
)


def integer(row, name, low=0, high=0xFFFFFFFF):
    value = row.get(name)
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name}: expected integer in {low}..{high}")
    return value


def boolean(row, name):
    value = row.get(name)
    if type(value) is not bool:
        raise ValueError(f"{name}: expected boolean")
    return value


def analyze(source, csv_path=None, visitor=None):
    header = end = None
    groups, labels, lengths = {}, Counter(), Counter()
    records = eligible = invalid_prefix = 0
    last_id = last_time = None
    id_gaps = 0
    csv_file = None
    if csv_path:
        csv_file = Path(csv_path).open("w", newline="", encoding="utf-8")
        writer = csv.writer(csv_file)
        writer.writerow(["id", "run", "callback_us", "hardware_rx_us", "network_generation",
                         "motion_epoch", "channel", "rx_format", "length", "label",
                         "motion_eligible", "payload_sha256"])
    try:
        with Path(source).open(encoding="utf-8-sig") as stream:
            line_number = 0
            while True:
                line = stream.readline(MAX_LINE + 1)
                if not line:
                    break
                line_number += 1
                if len(line) > MAX_LINE:
                    raise ValueError(f"line {line_number}: exceeds {MAX_LINE} characters")
                if not line.strip():
                    continue
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError(f"line {line_number}: expected object")
                schema = row.get("schema")
                if header is None:
                    if schema != "airboat.csi.session.v1":
                        raise ValueError("capture must begin with a session manifest")
                    capture_id = row.get("capture_id", "")
                    if not isinstance(capture_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", capture_id):
                        raise ValueError("capture_id: expected 8..64 ASCII identifier characters")
                    boolean(row, "simulated")
                    if row.get("target") != "esp32s31" or row.get("requested_iq_bits") != 8:
                        raise ValueError("unexpected target or requested IQ format")
                    if boolean(row, "layout_verified"):
                        raise ValueError("this schema version preserves unverified raw layout")
                    header = row
                    continue
                if end is not None:
                    raise ValueError("data after final counters")
                if schema == "airboat.csi.end.v1":
                    for field in COUNTERS:
                        integer(row, field)
                    end = row
                    continue
                if schema != "airboat.csi.raw.v1":
                    raise ValueError(f"unknown record schema: {schema}")
                if boolean(row, "simulated") != header["simulated"]:
                    raise ValueError("mixed simulated and device records")
                if boolean(row, "actual_layout_verified") or boolean(row, "carrier_mask_known"):
                    raise ValueError("raw schema cannot claim a verified layout/mask")
                if row.get("requested_iq_bits") != 8:
                    raise ValueError("inconsistent requested IQ format")
                ident = integer(row, "id", 1)
                run = integer(row, "run", 1)
                generation = integer(row, "network_generation", 1)
                motion_epoch = integer(row, "motion_epoch")
                at = integer(row, "callback_us", 0, 2**64 - 1)
                hardware = integer(row, "hardware_rx_us")
                integer(row, "rx_sequence", 0, 65535)
                channel = integer(row, "channel", 1, 255)
                rx_format = integer(row, "rx_format", 0, 255)
                integer(row, "rssi_dbm", -128, 127)
                integer(row, "noise_floor_dbm", -128, 127)
                length = integer(row, "length", 1, 512)
                label = integer(row, "label", 0, 4)
                motion_ok = boolean(row, "motion_eligible")
                motion_at = integer(row, "motion_at_us", 0, 2**64 - 1)
                head_locked = boolean(row, "head_locked")
                stationary = boolean(row, "stationary")
                commanded = boolean(row, "commanded_motion")
                expected_motion_ok = bool(motion_epoch and motion_at <= at and
                                          at - motion_at <= 250000 and
                                          head_locked and stationary and not commanded)
                if motion_ok != expected_motion_ok:
                    raise ValueError("motion eligibility disagrees with its recorded evidence")
                prefix = boolean(row, "first_word_invalid")
                mac = row.get("source", "")
                if not isinstance(mac, str) or not re.fullmatch(r"[0-9a-f]{12}", mac):
                    raise ValueError("source: expected MAC hex")
                raw_hex = row.get("payload_hex", "")
                if not isinstance(raw_hex, str) or not re.fullmatch(r"[0-9a-f]+", raw_hex):
                    raise ValueError("payload_hex: expected lowercase byte hex")
                payload = bytes.fromhex(raw_hex)
                if len(payload) != length:
                    raise ValueError("payload length mismatch")
                if last_id is not None:
                    if ident <= last_id or at < last_time:
                        raise ValueError("record ID/time moved backwards or duplicated")
                    id_gaps += ident - last_id - 1
                last_id, last_time = ident, at
                # Separate calibration backgrounds whenever any source/layout/motion epoch changes.
                key = (run, generation, mac, channel, rx_format, length, motion_epoch)
                if key not in groups:
                    if len(groups) >= MAX_GROUPS:
                        raise ValueError("too many source/layout groups; split the capture")
                    groups[key] = {"count": 0, "eligible": 0, "first_us": at, "last_us": at,
                                   "max_gap_us": 0, "hardware_wraps": 0, "previous_hw": None}
                group = groups[key]
                if group["count"]:
                    group["max_gap_us"] = max(group["max_gap_us"], at - group["last_us"])
                    # Only classify a backwards hardware stamp as wrap when local time agrees.
                    if hardware < group["previous_hw"]:
                        local_step = at - group["last_us"]
                        hw_step = (hardware - group["previous_hw"]) & 0xFFFFFFFF
                        if local_step < 2**31 and abs(hw_step - local_step) < 100000:
                            group["hardware_wraps"] += 1
                        else:
                            raise ValueError("hardware RX clock regressed without a plausible wrap")
                group["last_us"] = at
                group["previous_hw"] = hardware
                group["count"] += 1
                group["eligible"] += motion_ok
                records += 1
                eligible += motion_ok
                invalid_prefix += prefix
                labels[str(label)] += 1
                lengths[str(length)] += 1
                if visitor is not None:
                    visitor(row)
                if csv_file:
                    writer.writerow([ident, run, at, hardware, generation, motion_epoch, channel,
                                     rx_format, length, label, motion_ok, hashlib.sha256(payload).hexdigest()])
    finally:
        if csv_file:
            csv_file.close()
    if header is None or end is None:
        raise ValueError("incomplete capture: manifest/final counters missing")
    if end["exported_frames"] != records:
        raise ValueError("export count mismatch")
    if end["accepted"] != records + end["queued"] + end["discarded"]:
        raise ValueError("accepted frames do not reconcile with export/queue/discard counters")
    if id_gaps > end["full_drops"] + end["discarded"]:
        raise ValueError("record ID gaps exceed declared drop/discard counters")
    result_groups = []
    for key, group in groups.items():
        duration = (group["last_us"] - group["first_us"]) / 1000000
        result_groups.append({
            "run": key[0], "network_generation": key[1], "source": key[2],
            "channel": key[3], "rx_format": key[4], "length": key[5], "motion_epoch": key[6],
            "frames": group["count"], "motion_eligible": group["eligible"],
            "duration_s": round(duration, 6),
            "mean_pps": round((group["count"] - 1) / duration, 3) if duration else None,
            "max_gap_ms": group["max_gap_us"] / 1000,
            "hardware_wraps": group["hardware_wraps"],
        })
    return {"schema": "airboat.csi.quality.v1", "capture_id": header["capture_id"],
            "simulated": header["simulated"], "frames": records, "motion_eligible": eligible,
            "first_word_invalid_frames": invalid_prefix, "id_gaps": id_gaps,
            "labels": dict(labels), "payload_lengths": dict(lengths), "counters": end,
            "groups": result_groups, "layout_verified": False,
            "activity_inference": "not evaluated; raw transport and metadata quality only"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--csv", type=Path)
    args = parser.parse_args()
    destinations = [args.output.resolve()] + ([args.csv.resolve()] if args.csv else [])
    if args.capture.resolve() in destinations or len(set(destinations)) != len(destinations):
        parser.exit(1, "Capture and output paths must be distinct\n")
    try:
        with tempfile.TemporaryDirectory(prefix=".csi-analysis-", dir=args.output.parent) as folder:
            temporary = Path(folder)
            report = analyze(args.capture, temporary / "frames.csv" if args.csv else None)
            report_file = temporary / "report.json"
            report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            if args.csv:
                (temporary / "frames.csv").replace(args.csv)
            report_file.replace(args.output)
    except (ValueError, OSError) as error:
        parser.exit(1, f"Capture validation failed: {error}\n")
    print(f"Validated {report['frames']} frames; simulated={report['simulated']}; "
          f"motion eligible={report['motion_eligible']}")


if __name__ == "__main__":
    main()
