#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Validate file/replay boundaries against artifacts produced by the real C cores."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from csi import analyze as analyze_csi
from hotspot import analyze as analyze_hotspot
from review import build, render

HOTSPOT = CSI = None


class HotspotTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(HOTSPOT.read_text(encoding="utf-8-sig"))
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "capture.json"

    def save(self):
        self.path.write_text(json.dumps(self.data), encoding="utf-8")
        return self.path

    def test_real_c_replay_parity(self):
        r = analyze_hotspot(self.save())
        self.assertEqual(r["summary"]["records"], 160)
        self.assertEqual(r["summary"]["clock_wraps"], 1)
        self.assertEqual(r["summary"]["missed_reads"], 2)
        self.assertEqual(r["summary"]["valid"], 155)
        self.assertEqual(r["summary"]["unpaired"], 10)
        self.assertEqual(r["replay"]["mismatches"], 0)
        self.assertTrue(all(p["replayed_trend"] == p["recorded_trend"] for p in r["points"]))
        self.assertTrue(any(x["label"] == 2 and x["first_matching_trend_s"] is not None
                            for x in r["intervals"]))
        self.assertEqual(sum(x["count"] for x in r["intervals"]), 160)

    def test_reject_missing_ids(self):
        self.data["records"][2]["id"] += 1
        with self.assertRaisesRegex(ValueError, "incomplete or unordered"):
            analyze_hotspot(self.save())

    def test_reject_false_signal_validity(self):
        self.data["records"][0]["rssi_dbm"] = 0
        with self.assertRaisesRegex(ValueError, "valid observation"):
            analyze_hotspot(self.save())

    def test_unpaired_labels(self):
        self.data["records"][0]["paired"] = 0
        with self.assertRaisesRegex(ValueError, "unpaired samples"):
            analyze_hotspot(self.save())

    def test_unexplained_missed_read(self):
        self.data["meta"]["missed_reads"] = 0
        with self.assertRaisesRegex(ValueError, "missing reads"):
            analyze_hotspot(self.save())

    def test_backwards_time(self):
        self.data["records"][2]["read_ms"] = self.data["records"][1]["read_ms"] - 1
        with self.assertRaisesRegex(ValueError, "time moved backwards"):
            analyze_hotspot(self.save())

    def test_wrong_parameters_are_inspectable(self):
        self.data["meta"]["parameters"]["confirm_reads"] = 4
        self.data["trend_parameters"]["confirm_reads"] = 4
        r = analyze_hotspot(self.save())
        self.assertIsNone(r["replay"]["profile"])
        self.assertTrue(all(p["replayed_trend"] is None for p in r["points"]))

    def test_metadata_parameter_mismatch(self):
        self.data["trend_parameters"]["window"] = 9
        with self.assertRaisesRegex(ValueError, "parameters disagree"):
            analyze_hotspot(self.save())

    def test_ring_overwrite(self):
        self.data["records"] = self.data["records"][-20:]
        self.data["meta"].update(count=20, capacity=20, oldest=141, latest=160, overwritten=140)
        r = analyze_hotspot(self.save())
        self.assertEqual(r["summary"]["overwritten"], 140)
        self.assertTrue(r["warnings"])

    def test_freeze_required(self):
        self.data["meta"]["recording"] = True
        with self.assertRaisesRegex(ValueError, "stopped recording"):
            analyze_hotspot(self.save())

    def test_zero_records(self):
        self.data["records"] = []
        self.data["meta"].update(count=0, oldest=0, latest=0, overwritten=0, missed_reads=0)
        r = analyze_hotspot(self.save())
        self.assertEqual(r["summary"]["duration_s"], 0)
        self.assertEqual(r["intervals"], [])

    def test_boolean_not_integer(self):
        self.data["records"][0]["id"] = True
        with self.assertRaisesRegex(ValueError, "expected integer"):
            analyze_hotspot(self.save())

    def test_age_provenance(self):
        self.data["measurement_age_known"] = True
        with self.assertRaisesRegex(ValueError, "age is unknown"):
            analyze_hotspot(self.save())


class ReviewTests(unittest.TestCase):
    def test_capture_limit_before_opening_files(self):
        for captures in ([], [Path("missing.json")] * 17):
            with self.assertRaisesRegex(ValueError, "1..16"):
                build(captures)

    def test_csi_initial_blank_lines(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "spaced.jsonl"
            p.write_text("\n\n" + CSI.read_text(encoding="utf-8-sig"), encoding="utf-8")
            self.assertEqual(build([p])["reports"][0]["kind"], "csi")

    def test_csi_label_boundaries_cover_observed_time(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "labels.jsonl"
            rows = [json.loads(line) for line in CSI.read_text(encoding="utf-8-sig").splitlines() if line]
            rows[11]["label"] = 4
            p.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
            report = analyze_csi(p)
            interval = next(item for item in report["intervals"] if item["label"] == 4)
            self.assertAlmostEqual(interval["duration_s"], 0.05)
            self.assertEqual(sum(item["count"] for item in report["intervals"]), 120)

    def test_long_csi_bounds_curve_and_preserves_full_counts(self):
        rows = [json.loads(line) for line in CSI.read_text(encoding="utf-8-sig").splitlines() if line]
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "long.jsonl"
            with p.open("w", encoding="utf-8") as stream:
                stream.write(json.dumps(rows[0]) + "\n")
                for index in range(12000):
                    row = dict(rows[1])
                    row.update(id=index + 1, callback_us=1000000 + index * 50000,
                               motion_at_us=1000000 + index * 50000,
                               hardware_rx_us=(4294667295 + index * 50000) & 0xFFFFFFFF,
                               label=1 + index % 2)
                    stream.write(json.dumps(row) + "\n")
                end = dict(rows[-1], accepted=12000, exported_frames=12000)
                stream.write(json.dumps(end) + "\n")
            report = analyze_csi(p)
            self.assertEqual(len(report["points"]), 6001)
            self.assertEqual(report["points"][-1]["id"], 12000)
            self.assertEqual(sum(item["count"] for item in report["intervals"]), 12000)
            self.assertEqual(len(report["intervals"]), 12000)
            self.assertEqual(report["summary"]["labels"], {"1": 6000, "2": 6000})

    def test_csi_validated_timeline(self):
        r = analyze_csi(CSI)
        self.assertEqual(r["summary"]["records"], 120)
        self.assertEqual(r["summary"]["valid"], 80)
        self.assertEqual(sum(x["count"] for x in r["intervals"]), 120)
        self.assertEqual(r["summary"]["max_gap_ms"], 50)
        self.assertIsNone(r["points"][0]["gap_ms"])
        self.assertEqual(len(r["points"]), 120)
        self.assertTrue(r["simulated"])

    def test_reject_incomplete_csi(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "incomplete.jsonl"
            p.write_text("\n".join(CSI.read_text(encoding="utf-8-sig").splitlines()[:-1]) + "\n")
            with self.assertRaisesRegex(ValueError, "incomplete"):
                analyze_csi(p)

    def test_duplicate_identity(self):
        with self.assertRaisesRegex(ValueError, "duplicate capture"):
            build([HOTSPOT, HOTSPOT])

    def test_combined_identity_and_script_escaping(self):
        data = build([HOTSPOT, CSI])
        self.assertEqual(len(data["reports"]), 2)
        modified = copy.deepcopy(data)
        modified["reports"][0]["source"]["name"] = '</script><script>window.bad=1</script>'
        html = render(modified)
        self.assertNotIn('</script><script>window.bad', html)
        self.assertIn('\\u003c/script\\u003e', html)
        self.assertNotIn('__AIRBOAT_REVIEW_DATA__', html)

    def test_cli_failure_publishes_nothing(self):
        script = Path(__file__).resolve().parents[1] / "review.py"
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            bad = folder / "bad.json"
            bad.write_text('{}')
            output = folder / "result"
            result = subprocess.run([sys.executable, str(script), str(HOTSPOT), str(bad), '--out', str(output)],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())

    def test_cli_preserves_existing_folder(self):
        script = Path(__file__).resolve().parents[1] / "review.py"
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "result"
            output.mkdir()
            marker = output / "keep.txt"
            marker.write_text('keep')
            result = subprocess.run([sys.executable, str(script), str(HOTSPOT), '--out', str(output)],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(marker.read_text(), 'keep')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('Usage: test_review.py <C-generated-N1.json> <C-generated-CSI.jsonl>')
    HOTSPOT, CSI = map(Path, sys.argv[1:])
    sys.argv = sys.argv[:1]
    unittest.main()
