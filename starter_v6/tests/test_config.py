import json
import tempfile
import unittest
from pathlib import Path

from starter_v6.config import load_e04_config


class E04ConfigTests(unittest.TestCase):
    def test_example_loads_hmm_parameters(self):
        cfg = load_e04_config(Path(__file__).parents[1] / "config.example.json")
        self.assertEqual(cfg["hmm"].initial, (0.45, 0.45, 0.1))
        self.assertEqual(cfg["hmm"].temperature, 1.0)

    def test_rejects_unknown_hmm_key(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            payload = json.loads((Path(__file__).parents[1] / "config.example.json").read_text())
            payload["hmm"]["secret_smoothing"] = 2
            path.write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                load_e04_config(path)

    def test_rejects_bad_probability_sum(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            payload = json.loads((Path(__file__).parents[1] / "config.example.json").read_text())
            payload["hmm"]["initial"] = [0.4, 0.4, 0.4]
            path.write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                load_e04_config(path)
