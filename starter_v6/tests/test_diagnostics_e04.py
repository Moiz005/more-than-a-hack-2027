"""E04 diagnostics report aggregate behavior, never frame-level records."""
import unittest

from starter_v6.diagnostics import build_diagnostics


class E04DiagnosticsTests(unittest.TestCase):
    def test_reports_counts_missingness_agreement_and_parent_changes(self):
        report = build_diagnostics(
            labels=["H", "H", "D", "A", "X"],
            halves=[1, 1, 1, 2, 0],
            parent_labels=["H", "A", "D", "A", "X"],
            emission_argmax=["H", "A", "D", "A", "H"],
            missing_ball=[False, True, True, False, True],
            runtime_seconds=1.5,
        )
        self.assertEqual(report["graded_frame_count"], 4)
        self.assertEqual(report["ungraded_frame_count"], 1)
        self.assertEqual(report["graded_counts"], {"A": 1, "D": 1, "H": 2})
        self.assertEqual(report["missing_ball_overlap"]["graded_missing_ball_frames"], 2)
        self.assertEqual(report["missing_ball_overlap"]["missing_ball_during_H_or_A_frames"], 1)
        self.assertEqual(report["emission_agreement"]["decoded_matches_emission_argmax"], 3)
        self.assertEqual(report["e03_comparison"]["labels_changed"], 1)
        self.assertEqual(report["duration_frames"]["H"]["histogram_frames"]["1-24"], 1)
        self.assertEqual(report["ground_truth"], {"used": False, "scores_computed": False})
        self.assertNotIn("frame_rows", report)
        self.assertNotIn("coordinates", str(report).casefold())

    def test_requires_x_only_on_ungraded_frames(self):
        with self.assertRaisesRegex(ValueError, "graded output cannot contain X"):
            build_diagnostics(["H", "X"], [1, 1], ["H", "H"], ["H", "H"], [False, False], 0.0)


if __name__ == "__main__":
    unittest.main()
