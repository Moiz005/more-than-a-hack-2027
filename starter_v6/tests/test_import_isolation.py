"""Runtime import isolation and frozen synthetic parity checks."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from starter_v6.features import E02Config
from starter_v6.inference import iter_infer_e02
from starter_v6.possession import FrameEvidence, PlayerEvidence, PossessionConfig


ROOT = Path(__file__).resolve().parents[2]


def _synthetic_frames(frame_type):
    return [
        frame_type(0, 1, (0.0, 0.0), ()),
        frame_type(1, 1, (0.4, 0.0), (PlayerEvidence("H", 0.5, 0.0),)),
        frame_type(2, 1, (0.5, 0.0), (PlayerEvidence("H", 0.5, 0.0),)),
        frame_type(3, 1, None, ()),
        frame_type(4, 1, None, ()),
        frame_type(5, 1, (9.0, 0.0), (PlayerEvidence("A", 0.5, 0.0),)),
        frame_type(6, 1, (9.1, 0.0), (PlayerEvidence("A", 0.5, 0.0),)),
        frame_type(7, 1, (-1.0, 20.0), ()),
        frame_type(8, 1, (9.0, 0.0), (PlayerEvidence("A", 0.5, 0.0),)),
    ]


def _trace_current():
    results = iter_infer_e02(_synthetic_frames(FrameEvidence), PossessionConfig(), E02Config())
    return [
        {
            "label": result.inference.label,
            "frame": result.emission.frame,
            "half": result.emission.half,
            "emission": [result.emission.home, result.emission.away, result.emission.dead],
        }
        for result in results
    ]


class ImportIsolationTests(unittest.TestCase):
    def test_e04_runtime_resolves_only_local_v6_modules(self):
        script = """
import json
import sys
import starter_v6.run_e04 as runner
runner.synthetic_self_check()
old = sorted(name for name in sys.modules if name == 'starter_v4' or name == 'starter_v5' or name.startswith('starter_v4.') or name.startswith('starter_v5.'))
paths = sorted((name, getattr(module, '__file__', None)) for name, module in sys.modules.items() if name.startswith('starter_v6'))
print(json.dumps({'old': old, 'paths': paths}, sort_keys=True))
"""
        completed = subprocess.run(
            [sys.executable, "-B", "-c", script], cwd=str(ROOT),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        trace = json.loads(completed.stdout.splitlines()[-1])
        self.assertEqual(trace["old"], [])
        self.assertTrue(trace["paths"])
        self.assertTrue(all(path and "/starter_v6/" in path for _, path in trace["paths"]))

    def test_synthetic_intermediates_and_labels_match_frozen_tree(self):
        script = """
import json
from starter_v5.inference import iter_infer_e02
from starter_v5.possession import FrameEvidence, PlayerEvidence, PossessionConfig
from starter_v5.features import E02Config
frames = [
    FrameEvidence(0, 1, (0.0, 0.0), ()),
    FrameEvidence(1, 1, (0.4, 0.0), (PlayerEvidence('H', 0.5, 0.0),)),
    FrameEvidence(2, 1, (0.5, 0.0), (PlayerEvidence('H', 0.5, 0.0),)),
    FrameEvidence(3, 1, None, ()),
    FrameEvidence(4, 1, None, ()),
    FrameEvidence(5, 1, (9.0, 0.0), (PlayerEvidence('A', 0.5, 0.0),)),
    FrameEvidence(6, 1, (9.1, 0.0), (PlayerEvidence('A', 0.5, 0.0),)),
    FrameEvidence(7, 1, (-1.0, 20.0), ()),
    FrameEvidence(8, 1, (9.0, 0.0), (PlayerEvidence('A', 0.5, 0.0),)),
]
results = iter_infer_e02(frames, PossessionConfig(), E02Config())
print(json.dumps([{'label': r.inference.label, 'frame': r.emission.frame, 'half': r.emission.half, 'emission': [r.emission.home, r.emission.away, r.emission.dead]} for r in results], sort_keys=True))
"""
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "frozen.tar"
            extracted = Path(folder) / "tree"
            with archive.open("wb") as handle:
                subprocess.run(["git", "archive", "--format=tar", "e04-c7-frozen"], cwd=str(ROOT), stdout=handle, check=True)
            extracted.mkdir()
            subprocess.run(["tar", "-xf", str(archive), "-C", str(extracted)], check=True)
            env = dict(os.environ)
            env["PYTHONPATH"] = str(extracted)
            completed = subprocess.run(
                [sys.executable, "-B", "-c", script], cwd=str(extracted), env=env,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        frozen_trace = json.loads(completed.stdout.splitlines()[-1])
        self.assertEqual(_trace_current(), frozen_trace)


if __name__ == "__main__":
    unittest.main()
