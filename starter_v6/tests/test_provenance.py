"""Provenance fingerprints are deterministic and reports are atomically replaced."""
import tempfile
import unittest
from pathlib import Path

from starter_v6.provenance import (
    atomic_write_text,
    config_sha256,
    effective_config,
    file_sha256,
    runtime_source_files,
    source_manifest,
    source_sha256,
)


class ProvenanceTests(unittest.TestCase):
    def test_effective_config_hash_is_stable_and_omits_data_directory(self):
        first = {"data_dir": "/private/one", "hmm": {"weight": 1.0}}
        second = {"data_dir": "/private/two", "hmm": {"weight": 1.0}}
        self.assertEqual(effective_config(first), {"hmm": {"weight": 1.0}})
        self.assertEqual(config_sha256(first), config_sha256(second))

    def test_model_hash_ignores_run_paths_but_changes_with_algorithm_config(self):
        first = {"output": "one.csv", "hmm": {"weight": 1.0}}
        second = {"output": "two.csv", "hmm": {"weight": 1.0}}
        changed = {"output": "two.csv", "hmm": {"weight": 0.5}}
        self.assertEqual(config_sha256(first), config_sha256(second))
        self.assertNotEqual(config_sha256(second), config_sha256(changed))

    def test_file_and_source_hashes_track_content(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "module.py"
            source.write_text("value = 1\n", encoding="utf-8")
            before = source_sha256([source])
            first = file_sha256(source)
            source.write_text("value = 2\n", encoding="utf-8")
            self.assertNotEqual(before, source_sha256([source]))
            self.assertNotEqual(first, file_sha256(source))

    def test_atomic_report_write_replaces_complete_file(self):
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / "report.json"
            report.write_text("old", encoding="utf-8")
            atomic_write_text(report, "new\n")
            self.assertEqual(report.read_text(encoding="utf-8"), "new\n")
            self.assertFalse(report.with_name("report.json.tmp").exists())

    def test_runtime_source_manifest_is_project_relative(self):
        root = Path(__file__).resolve().parents[2]
        files = runtime_source_files(root)
        manifest = source_manifest(files, root)
        self.assertIn("games.py", manifest)
        self.assertTrue(any(name.startswith("starter_v6/") for name in manifest))
        self.assertNotIn("starter_v4/possession.py", manifest)
        self.assertNotIn("starter_v5/possession.py", manifest)


if __name__ == "__main__":
    unittest.main()
