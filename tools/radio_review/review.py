#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Create a self-contained offline review from N1 JSON and R1 CSI JSONL exports."""
import argparse
import json
import tempfile
from pathlib import Path

from csi import analyze as analyze_csi
from hotspot import analyze as analyze_hotspot


def build(captures):
    captures = list(captures)
    if not 1 <= len(captures) <= 16:
        raise ValueError("provide 1..16 capture files")
    reports = []
    seen = set()
    for capture in captures:
        path = Path(capture)
        with path.open(encoding="utf-8-sig") as stream:
            prefix = stream.read(8192)
        # N1 is a single JSON object; CSI begins with one-line session manifest.
        first_line = next((line for line in prefix.splitlines() if line.strip()), "")
        if '"airboat.csi.session.v1"' in first_line:
            report = analyze_csi(path)
        else:
            report = analyze_hotspot(path)
        key = (report["kind"], report["identity"])
        if key in seen:
            raise ValueError("duplicate capture identity; provide one immutable export per capture")
        seen.add(key)
        reports.append(report)
    return {"schema": "airboat.radio.review.v1", "reports": reports,
            "comparison_scope": "independent capture timelines; no cross-device clock alignment",
            "experience_targets": {"hotspot": "走远求等、走近重逢的辅助线索",
                                   "csi": "停靠时察觉活动，随后用视觉确认"}}


def render(review):
    template = Path(__file__).with_name("report.html").read_text(encoding="utf-8")
    payload = json.dumps(review, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    # JSON in a script element is still parsed by HTML before JS; neutralize closing tags.
    payload = payload.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    return template.replace("__AIRBOAT_REVIEW_DATA__", payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("captures", nargs="+", type=Path)
    parser.add_argument("--out", required=True, type=Path, help="New output folder; inputs are read only")
    args = parser.parse_args()
    try:
        if args.out.exists():
            raise ValueError("output folder already exists; choose a new folder")
        if not args.out.parent.is_dir():
            raise ValueError("output parent folder must exist")
        data = build(args.captures)
        html = render(data)
        with tempfile.TemporaryDirectory(prefix=".radio-review-", dir=args.out.parent) as temp:
            work = Path(temp) / "result"
            work.mkdir()
            (work / "report.html").write_text(html, encoding="utf-8")
            (work / "review.json").write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                                               encoding="utf-8")
            work.rename(args.out)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Review generation failed: {error}\n")
    print(f"Created {args.out / 'report.html'} ({len(data['reports'])} captures)")


if __name__ == "__main__":
    main()
