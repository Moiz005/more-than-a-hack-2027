"""Aggregate E02 diagnostics stay non-reconstructive and distinguish evidence from output."""

import unittest

from starter_v5.features import E02Config
from starter_v5.inference import iter_infer_e02
from starter_v5.pipeline import E02SummaryAccumulator, TagAblationAccumulator
from starter_v5.possession import FrameEvidence, PlayerEvidence, PossessionConfig
from starter_v5.tag_features import TagEvidence


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

    def test_tag_ablation_reports_only_aggregate_effect_counts(self):
        frame = FrameEvidence(0, 1, (0.0, 0.0),
                              (PlayerEvidence("H", 0.25, 0.0), PlayerEvidence("A", 0.4, 0.0)))
        config = E02Config(quality_reference_players=2, low_player_count=1)
        possession_config = PossessionConfig(min_observation_confidence=0.15)
        tagged = list(iter_infer_e02([frame], possession_config, config,
                                     tag_evidence=[TagEvidence(active=True, team_prior="H", home_prior=1.0)]))[0]
        baseline = list(iter_infer_e02([frame], possession_config, config))[0]
        accumulator = TagAblationAccumulator()
        accumulator.add(tagged, baseline)
        report = accumulator.report()
        self.assertEqual(report["frame_count"], 1)
        self.assertEqual(report["frames_with_changed_team_evidence_confidence"], 1)
        self.assertEqual(report["frames_with_changed_team_evidence"], 1)
        self.assertFalse(report["ground_truth_used"])
        self.assertIn("restart context shared", report["comparison"])
        self.assertNotIn("frame_rows", report)

    def test_tag_ablation_rejects_misaligned_frames(self):
        frames = [FrameEvidence(i, 1, None, ()) for i in range(2)]
        config = E02Config()
        tagged = list(iter_infer_e02(frames, PossessionConfig(), config))
        baseline = list(iter_infer_e02(frames, PossessionConfig(), config))
        accumulator = TagAblationAccumulator()
        with self.assertRaises(ValueError):
            accumulator.add(tagged[0], baseline[1])


if __name__ == "__main__":
    unittest.main()
