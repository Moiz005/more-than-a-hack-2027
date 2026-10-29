"""Aggregate E02 diagnostics stay non-reconstructive and distinguish evidence from output."""

import unittest

from starter_v4.features import E02Config
from starter_v4.inference import iter_infer_e02
from starter_v4.pipeline import E02SummaryAccumulator
from starter_v4.possession import FrameEvidence, PlayerEvidence, PossessionConfig


class E02DiagnosticsTests(unittest.TestCase):
    def test_report_contains_aggregate_features_and_no_frame_coordinates(self):
        frames = [
            FrameEvidence(0, 1, (1.0, 1.0),
                          (PlayerEvidence("H", 1.2, 1.0, track_id=0), PlayerEvidence("A", 5.0, 1.0, track_id=1))),
            FrameEvidence(1, 1, None,
                          (PlayerEvidence("H", 1.3, 1.0, track_id=0), PlayerEvidence("A", 4.9, 1.0, track_id=1))),
        ]
        feature_config = E02Config(quality_reference_players=2, low_player_count=1)
        accumulator = E02SummaryAccumulator()
        for result in iter_infer_e02(frames, PossessionConfig(), feature_config):
            accumulator.add(result)

        report = accumulator.report(runtime_seconds=0.1, peak_memory_mb=12.0)
        self.assertEqual(report["observations"]["ball_missing_frames"], 1)
        self.assertIn("ball_displacement_available", report["e02_features"]["availability_counts"])
        self.assertIn("team_evidence_confidence_histogram", report["e02_features"])
        self.assertIn("missing_gap_count_by_length", report["gap_analysis"])
        self.assertIn("decision_reasons", report["gap_analysis"])
        self.assertEqual(report["ground_truth"], {"used": False, "accuracy_or_score_computed": False})
        self.assertNotIn("coordinates", str(report).casefold())
        self.assertNotIn("frame_rows", report)
        self.assertEqual(report["resources"]["peak_memory_mb"], 12.0)


if __name__ == "__main__":
    unittest.main()
