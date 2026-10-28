"""No-data tests for the Solution 01 foundation."""

import hashlib
import json
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
STARTER_V2 = HERE.parent
REPO = STARTER_V2.parent
sys.path.insert(0, str(REPO))

from starter_v2.provenance import set_random_seed, sha256_file  # noqa: E402
from starter_v2.solution01 import validate_synthetic_labels  # noqa: E402


class FoundationTests(unittest.TestCase):
    def test_seed_repeats_python_random_sequence(self):
        set_random_seed(19)
        first = [random.random() for _ in range(4)]
        set_random_seed(19)
        self.assertEqual(first, [random.random() for _ in range(4)])

    def test_sha256_streaming_helper(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.bin"
            path.write_bytes(b"synthetic fixture")
            self.assertEqual(sha256_file(path), hashlib.sha256(b"synthetic fixture").hexdigest())

    def test_label_contract_rejects_invalid_values_and_counts(self):
        validate_synthetic_labels(["H", "D", "X"], 3)
        with self.assertRaises(ValueError):
            validate_synthetic_labels(["HOME"], 1)
        with self.assertRaises(ValueError):
            validate_synthetic_labels(["H"], 2)

    def test_cli_self_check_writes_synthetic_metadata_without_match_data(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            metadata_path = Path(temp_dir) / "experiment.json"
            completed = subprocess.run(
                [sys.executable, str(STARTER_V2 / "solution01.py"), "--self-check",
                 "--metadata-out", str(metadata_path)],
                cwd=str(REPO),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                env={**os.environ, "MTAH_DATA_DIR": temp_dir},
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stdout)["status"], "ok")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["input_ids"], ["synthetic.smoke_fixture"])
            self.assertEqual(len(metadata["input_sha256"]["synthetic.smoke_fixture"]), 64)

    def test_json_config_loads_seed_for_synthetic_cli(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            metadata_path = Path(temp_dir) / "experiment.json"
            config_path.write_text(json.dumps({"seed": 23}), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(STARTER_V2 / "solution01.py"), "--self-check",
                 "--config", str(config_path), "--metadata-out", str(metadata_path)],
                cwd=str(REPO), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["random_seed"], 23)

    def test_json_config_selects_data_root_and_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            configured_root = Path(temp_dir) / "configured-data"
            config_path.write_text(json.dumps({
                "source": "broadcast", "data_dir": str(configured_root),
            }), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(STARTER_V2 / "solution01.py"), "--check-inputs",
                 "--config", str(config_path)],
                cwd=str(REPO), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, check=False, env={key: value for key, value in os.environ.items()
                                             if key != "MTAH_DATA_DIR"},
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn(str(configured_root / "broadcast" / "BAR-ATH_broadcast.mp4"),
                          completed.stderr)

    def test_json_config_rejects_unknown_keys(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text(json.dumps({"unexpected": True}), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(STARTER_V2 / "solution01.py"), "--self-check",
                 "--config", str(config_path)],
                cwd=str(REPO), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, check=False,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn("unknown config key", completed.stderr)

    def test_missing_assets_fail_clearly_without_fallback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            completed = subprocess.run(
                [sys.executable, str(STARTER_V2 / "solution01.py"), "--check-inputs"],
                cwd=str(REPO),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                env={**os.environ, "MTAH_DATA_DIR": temp_dir},
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn("match data not found", completed.stderr)
            self.assertIn("BAR-ATH_tactical.mp4", completed.stderr)


if __name__ == "__main__":
    unittest.main()
