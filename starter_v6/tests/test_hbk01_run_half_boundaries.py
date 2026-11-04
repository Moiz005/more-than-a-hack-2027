"""Synthetic contracts for the HBK-01 isolated runner configuration."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from starter_v6.timeline import TacticalTimeline
from starter_v6 import run_half_boundaries as runner
from starter_v6.kickoff_atd import INSUFFICIENT_EVIDENCE, KickoffDetectionResult
from starter_v6.run_half_boundaries import (
    MODES,
    _resolve_run_targets,
    load_hbk_config,
    synthetic_self_check,
)


class RunHalfBoundariesTests(unittest.TestCase):
    def synthetic_timeline(self):
        mask = bytearray(8)
        mask[1:3] = bytes([1]) * 2
        mask[5:7] = bytes([2]) * 2
        return TacticalTimeline("tactical", 25, 8, bytes(mask), ((1, 1, 2), (2, 5, 6)))

    def test_example_config_is_strict_and_uses_tactical_parent(self):
        config = load_hbk_config(
            Path(__file__).parents[1] / "config.hbk01.example.json"
        )
        self.assertEqual(config["mode"], "audit")
        self.assertEqual(config["parent_config"], "starter_v6/config.example.json")
        self.assertEqual(config["source"], "tactical")
        self.assertEqual(set(MODES), {"off", "audit", "overlay"})

    def test_unknown_keys_and_invalid_modes_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"mode": "guess"}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_hbk_config(path)
            path.write_text(json.dumps({"unexpected": True}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_hbk_config(path)

    def test_detector_config_is_strict_and_parent_source_is_tactical(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"detector": {"not_a_threshold": 1}}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_hbk_config(path)
            path.write_text(json.dumps({"source": "broadcast"}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_hbk_config(path)

    def test_run_targets_are_distinct_under_run_root_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            config = load_hbk_config()
            targets = _resolve_run_targets(
                project_root, config, checkpoint_root=".local-checkpoints/hbk01",
            )
            self.assertEqual(len(set(targets)), 3)
            run_root = (project_root / ".local-checkpoints" / "hbk01" / config["run_id"]).resolve()
            self.assertTrue(all(run_root in target.parents for target in targets))
            targets[0].parent.mkdir(parents=True)
            targets[0].write_text("existing", encoding="utf-8")
            with self.assertRaises(ValueError):
                _resolve_run_targets(
                    project_root, config, checkpoint_root=".local-checkpoints/hbk01",
                )

    def test_synthetic_self_check_proves_runner_policy_without_assets(self):
        self.assertEqual(synthetic_self_check(), "passed")

    def test_off_mode_copies_parent_bytes_exactly_and_overlay_rejects_without_output(self):
        parent_bytes = b"frame,label\n0,X\n1,H\n2,D\n3,X\n4,X\n5,A\n6,H\n7,X\n"
        labels = ("X", "H", "D", "X", "X", "A", "H", "X")
        parent_metadata = {"output_sha256": "synthetic", "git_revision": "synthetic", "config_sha256": "synthetic"}
        paths = {}
        parent_config = {"source": "tactical", "data_dir": None}
        project_root = Path(__file__).parents[2].resolve()
        checkpoint_parent = project_root / ".local-checkpoints" / "hbk01"
        checkpoint_parent.mkdir(parents=True, exist_ok=True)
        directory = Path(tempfile.mkdtemp(prefix="test-runner-", dir=str(checkpoint_parent)))
        try:
            config = load_hbk_config()
            config.update({"mode": "off", "run_id": "synthetic-off"})
            config_path = project_root / "starter_v6/config.hbk01.example.json"
            with patch.object(runner.run_e04, "load_e04_config", return_value=parent_config), \
                    patch.object(runner, "_run_parent", return_value=(
                        parent_bytes, labels, parent_metadata, paths,
                    )), \
                    patch.object(runner, "build_tactical_timeline", return_value=self.synthetic_timeline()), \
                    patch.object(runner, "validate_tactical_reference"):
                self.assertEqual(
                    runner._run(config, config_path, directory, False, project_root), 0,
                )
            output = directory / "synthetic-off" / "submission.csv"
            self.assertEqual(output.read_bytes(), parent_bytes)

            config.update({"mode": "overlay", "run_id": "synthetic-overlay"})
            failed_detection = KickoffDetectionResult(
                status=INSUFFICIENT_EVIDENCE, execution_frame=None,
                video_timestamp_seconds=None, reasons=("synthetic_missing",),
                candidates=(), evaluated_frames=0,
            )
            with patch.object(runner.run_e04, "load_e04_config", return_value=parent_config), \
                    patch.object(runner, "_run_parent", return_value=(
                        parent_bytes, labels, parent_metadata, paths,
                    )), \
                    patch.object(runner, "build_tactical_timeline", return_value=self.synthetic_timeline()), \
                    patch.object(runner, "validate_tactical_reference"), \
                    patch.object(runner, "_detect_opening_kickoffs", return_value=(
                        {1: failed_detection, 2: failed_detection}, SimpleNamespace(records=()),
                    )):
                self.assertEqual(
                    runner._run(config, config_path, directory, False, project_root), 2,
                )
            self.assertFalse((directory / "synthetic-overlay" / "submission.csv").exists())
        finally:
            shutil.rmtree(directory)


if __name__ == "__main__":
    unittest.main()
