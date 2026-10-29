"""Synthetic possession semantics. Coordinates/events here are generated, never match-derived."""

import math
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from starter_v2.possession import (
    FrameEvidence,
    PlayerEvidence,
    PossessionConfig,
    decode_probabilities,
    infer_possession,
    possession_spells,
    read_submission,
    validate_submission_rows,
)
from starter_v2.diagnostics import summarize


def controlled_frame(index, half, owner, ball_x=0.0, nearest_override=None):
    """Generate two synthetic players; optionally move the opponent closer for one frame."""
    other = "A" if owner == "H" else "H"
    owner_x = ball_x + (0.25 if nearest_override != owner else 1.0)
    other_x = ball_x + (0.2 if nearest_override == other else 4.0)
    return FrameEvidence(
        frame=index,
        half=half,
        ball_xy=(ball_x, 0.0),
        players=(PlayerEvidence(owner, owner_x, 0.0), PlayerEvidence(other, other_x, 0.0)),
    )


class PossessionSemanticsTests(unittest.TestCase):
    def setUp(self):
        self.config = PossessionConfig(
            control_radius_m=1.5,
            acquire_frames=2,
            max_missing_frames=2,
            max_uncertain_frames=2,
        )

    def test_controlled_h_pass_survives_one_brief_nearest_a_frame(self):
        frames = [controlled_frame(i, 1, "H", ball_x=i * 0.2) for i in range(2)]
        frames += [controlled_frame(2, 1, "H", ball_x=0.4, nearest_override="A")]
        frames += [controlled_frame(i, 1, "H", ball_x=i * 0.2) for i in range(3, 6)]
        self.assertEqual(infer_possession(frames, self.config), ["X", "H", "H", "H", "H", "H"])

    def test_turnover_requires_two_consecutive_controlled_a_observations(self):
        frames = [controlled_frame(i, 1, "H") for i in range(2)]
        frames.append(controlled_frame(2, 1, "A", nearest_override="A"))
        frames.append(controlled_frame(3, 1, "H"))
        frames.extend(controlled_frame(i, 1, "A", ball_x=0.2 * i) for i in range(4, 7))
        self.assertEqual(infer_possession(frames, self.config), ["X", "H", "H", "H", "H", "A", "A"])

    def test_stoppage_splits_same_team_into_two_spells(self):
        frames = [controlled_frame(i, 1, "H") for i in range(2)]
        frames.append(FrameEvidence(2, 1, None, (), dead_ball=True))
        frames.extend(controlled_frame(i, 1, "H") for i in range(3, 5))
        labels = infer_possession(frames, self.config)
        self.assertEqual(labels, ["X", "H", "D", "X", "H"])
        self.assertEqual(possession_spells(labels), [("H", 1, 1), ("H", 4, 4)])

    def test_missing_ball_gap_keeps_owner_then_expires_to_abstain(self):
        frames = [controlled_frame(i, 1, "H") for i in range(2)]
        frames.extend(FrameEvidence(i, 1, None, ()) for i in range(2, 4))
        frames.append(controlled_frame(4, 1, "H"))
        self.assertEqual(infer_possession(frames, self.config), ["X", "H", "H", "H", "H"])
        long_gap = frames[:2] + [FrameEvidence(i, 1, None, ()) for i in range(2, 6)]
        long_gap += [controlled_frame(6, 1, "A"), controlled_frame(7, 1, "A")]
        self.assertEqual(infer_possession(long_gap, self.config),
                         ["X", "H", "H", "H", "X", "X", "X", "A"])

    def test_half_boundary_resets_state_and_ungraded_gap_cannot_bridge(self):
        frames = [controlled_frame(0, 1, "H"), controlled_frame(1, 1, "H"),
                  controlled_frame(2, 2, "A"), controlled_frame(3, 2, "A")]
        self.assertEqual(infer_possession(frames, self.config), ["X", "H", "X", "A"])

    def test_restart_does_not_assign_owner_without_controlled_evidence(self):
        frames = [FrameEvidence(0, 1, None, (), dead_ball=True),
                  FrameEvidence(1, 1, (0.0, 0.0), (PlayerEvidence("A", 5.0, 5.0),), restart=True),
                  controlled_frame(2, 1, "A"), controlled_frame(3, 1, "A")]
        self.assertEqual(infer_possession(frames, self.config), ["D", "X", "X", "A"])


class DecoderAndInputValidationTests(unittest.TestCase):
    def test_valid_probabilities_decode_to_labels(self):
        values = [(0.8, 0.1, 0.1), (0.1, 0.8, 0.1), (0.1, 0.1, 0.8)]
        self.assertEqual(decode_probabilities(values), ["H", "A", "D"])

    def test_rejects_nonfinite_out_of_range_and_bad_probability_rows(self):
        bad_rows = [[0.5, 0.5], [math.nan, 0, 1], [1.1, -0.1, 0], [0.2, 0.2, 0.2]]
        for row in bad_rows:
            with self.subTest(row=row), self.assertRaises(ValueError):
                decode_probabilities([row])

    def test_submission_rows_reject_empty_duplicate_shifted_and_invalid_labels(self):
        invalid = (
            [(0, "H"), (1, "")],
            [(0, "H"), (0, "A")],
            [(1, "H"), (2, "A")],
            [(0, "H"), (1, "Q")],
        )
        for rows in invalid:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                validate_submission_rows(rows, expected_frames=2)
        with self.assertRaisesRegex(ValueError, "expected 2 rows, found 1"):
            validate_submission_rows([(0, "H")], expected_frames=2)

    def test_csv_reader_rejects_bad_header_duplicate_frames_and_empty_label(self):
        malformed = (
            ("frame,state\n0,H\n1,A\n", "header"),
            ("frame,label\n1,H\n2,A\n", "expected frame 0"),
            ("frame,label\n0,H\n0,A\n", "expected frame 1"),
            ("frame,label\n0,H\n1,\n", "empty or invalid label"),
        )
        for contents, expected in malformed:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "submission.csv"
                path.write_text(contents, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, expected):
                    read_submission(str(path), expected_frames=2)

    def test_diagnostics_aggregate_spells_missingness_transitions_and_contradictions(self):
        result = summarize(
            ["H", "H", "D", "A"], [True, False, True, True],
            [0.95, 0.95, 0.99, 0.97], ["H", "A", None, "H"], 0.25,
        )
        self.assertEqual(result["inferences"]["predicted_possession_count"], 2)
        self.assertEqual(result["inferences"]["predicted_transitions"], {"D->A": 1, "H->D": 1})
        self.assertEqual(
            result["observations"]["ball_missing_during_predicted_possession_frames"], 1
        )
        self.assertEqual(
            result["consistency_checks"]["high_confidence_prediction_evidence_contradictions"], 2
        )
        self.assertEqual(result["inferences"]["predicted_label_share"]["D"], 0.25)
        self.assertEqual(result["inferences"]["runtime_seconds"], 0.25)
        self.assertEqual(result["ground_truth"], {"used": False, "accuracy_or_score_computed": False})

    def test_diagnostics_cli_accepts_synthetic_json_without_match_data(self):
        payload = {
            "kind": "synthetic_only", "labels": ["H", "H", "D"],
            "ball_observed": [True, False, True], "confidence": [0.9, 0.8, 0.99],
            "evidence_team": ["H", "A", None], "runtime_seconds": 0.1,
        }
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic_diagnostics.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, "-m", "starter_v2.diagnostics", str(path)],
                cwd=str(Path(__file__).resolve().parents[2]),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(report["frame_count"], 3)
        self.assertFalse(report["ground_truth"]["used"])
        self.assertIn("predicted_possession_count", report["inferences"])

    def test_diagnostics_cli_rejects_ground_truth_fields(self):
        payload = {
            "labels": ["H"], "ball_observed": [True], "confidence": [0.9],
            "evidence_team": ["H"], "runtime_seconds": 0.1, "ground_truth": ["H"],
        }
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad_diagnostics.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, "-m", "starter_v2.diagnostics", str(path)],
                cwd=str(Path(__file__).resolve().parents[2]),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
            )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("ground truth is not accepted", completed.stderr)


if __name__ == "__main__":
    unittest.main()
