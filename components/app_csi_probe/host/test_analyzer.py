#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Exercise exported real C fixture and reject broken or misleading captures."""
import json
import tempfile
import unittest
from pathlib import Path
import sys

from analyze_capture import analyze


class CaptureTests(unittest.TestCase):
    rows = None

    def write_capture(self, rows, folder):
        p = Path(folder) / "capture.jsonl"
        p.write_text("".join(json.dumps(x) + "\n" for x in rows), encoding="utf-8")
        return p

    def rejects(self, edit, pattern):
        rows = json.loads(json.dumps(self.rows))
        edit(rows)
        with tempfile.TemporaryDirectory() as folder:
            p = self.write_capture(rows, folder)
            with self.assertRaisesRegex(ValueError, pattern):
                analyze(p)

    def test_valid_fixture(self):
        with tempfile.TemporaryDirectory() as folder:
            p = self.write_capture(self.rows, folder)
            csv = Path(folder) / "frames.csv"
            report = analyze(p, csv)
            self.assertTrue(report["simulated"])
            self.assertEqual(report["frames"], 120)
            self.assertEqual(report["motion_eligible"], 80)
            self.assertEqual(report["labels"], {"1": 40, "2": 40, "3": 40})
            self.assertEqual(sum(x["hardware_wraps"] for x in report["groups"]), 1)
            self.assertTrue(all(x["mean_pps"] == 20 for x in report["groups"]))
            self.assertEqual(len(csv.read_text().splitlines()), 121)

    def test_incomplete(self):
        self.rejects(lambda rows: rows.pop(), "incomplete")

    def test_bad_hex_length(self):
        self.rejects(lambda rows: rows[1].update(length=127), "length mismatch")

    def test_reordered(self):
        self.rejects(lambda rows: rows[2].update(id=rows[1]["id"]), "backwards or duplicated")

    def test_mixed_provenance(self):
        self.rejects(lambda rows: rows[1].update(simulated=False), "mixed simulated")

    def test_premature_layout(self):
        self.rejects(lambda rows: rows[1].update(actual_layout_verified=True), "verified layout")

    def test_motion_evidence(self):
        self.rejects(lambda rows: rows[1].update(commanded_motion=True), "recorded evidence")

    def test_trailer_count(self):
        self.rejects(lambda rows: rows[-1].update(exported_frames=121), "export count")

    def test_unexplained_clock_regression(self):
        self.rejects(lambda rows: rows[9].update(hardware_rx_us=1), "regressed")

    def test_missing_counter_loss(self):
        self.rejects(lambda rows: rows[-1].update(accepted=121), "reconcile")

    def test_oversized_line(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "capture.jsonl"
            p.write_text("x" * 9000)
            with self.assertRaisesRegex(ValueError, "exceeds"):
                analyze(p)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: test_analyzer.py <C-generated simulated-capture.jsonl>")
    CaptureTests.rows = [json.loads(line) for line in Path(sys.argv.pop()).read_text(encoding="utf-8-sig").splitlines()]
    unittest.main()
