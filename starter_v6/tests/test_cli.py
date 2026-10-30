"""CLI configuration and no-data smoke tests."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from starter_v5.run_e01 import load_config


ROOT = Path(__file__).resolve().parents[2]


class CliTests(unittest.TestCase):
    def test_config_rejects_unknown_and_broadcast_source(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            for payload, expected in (
                ({"mystery": 1}, "unknown config keys"),
                ({"source": "broadcast"}, "tactical"),
                ({"possession": {"mystery": 1}}, "unknown possession config keys"),
            ):
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.subTest(payload=payload), self.assertRaisesRegex(ValueError, expected):
                    load_config(path)

    def test_config_loads_documented_thresholds(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text(json.dumps({"possession": {"acquire_frames": 4}}), encoding="utf-8")
            config = load_config(path)
        self.assertEqual(config["possession"].acquire_frames, 4)
        self.assertEqual(config["source"], "tactical")

    def test_evidence_modes_and_feature_thresholds_are_explicit(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text(json.dumps({"evidence_mode": "e02", "features": {"gap_support_frames": 4}}), encoding="utf-8")
            config = load_config(path)
        self.assertEqual(config["evidence_mode"], "e02")
        self.assertEqual(config["features"].gap_support_frames, 4)

    def test_config_rejects_invalid_evidence_mode_and_feature_key(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            for payload, expected in (
                ({"evidence_mode": "unknown"}, "evidence_mode must be"),
                ({"features": {"unknown": 1}}, "unknown feature config keys"),
            ):
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.subTest(payload=payload), self.assertRaisesRegex(ValueError, expected):
                    load_config(path)

    def test_e02_requires_matching_metric_pitch_dimensions(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text(json.dumps({"evidence_mode": "e02", "features": {"pitch_width_m": 70.0}}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "pitch dimensions must match"):
                load_config(path)

    def test_e04_self_check_runs_without_competition_data(self):
        completed = subprocess.run(
            [sys.executable, "-m", "starter_v6.run_e04", "--self-check"],
            cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("synthetic E04 self-check passed", completed.stdout)

    def test_missing_data_fails_clearly_and_writes_no_candidate(self):
        with tempfile.TemporaryDirectory() as folder:
            folder_path = Path(folder)
            config_path = folder_path / "config.json"
            candidate = folder_path / "out" / "candidate.csv"
            config_path.write_text(json.dumps({"data_dir": str(folder_path / "missing")}), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, "-m", "starter_v5.run_e03", "--config", str(config_path),
                 "--output", str(candidate)],
                cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
            )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("match data not found", completed.stderr)
        self.assertFalse(candidate.exists())


if __name__ == "__main__":
    unittest.main()
