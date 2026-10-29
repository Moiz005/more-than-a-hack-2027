"""Synthetic geometry, motion, and observation-quality feature tests."""

import unittest

from starter_v5.features import E02Config, iter_frame_features
from starter_v5.possession import FrameEvidence, PlayerEvidence


def player(team, x, y, slot, speed=1.0):
    return PlayerEvidence(team, x, y, speed, track_id=slot)


class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.config = E02Config()

    def test_geometry_uses_metric_coordinates_and_observed_players(self):
        frame = FrameEvidence(
            0, 1, (10.0, 0.0),
            (player("H", 10.0, 68.0, 0), player("A", 10.0, 34.0, 1)),
        )
        features = list(iter_frame_features([frame], self.config))[0]
        self.assertEqual(features.spatial.nearest_home_m, 68.0)
        self.assertEqual(features.spatial.nearest_away_m, 34.0)
        self.assertTrue(features.quality.ball_observed)

    def test_missing_ball_has_no_current_ball_distance_or_fabricated_coordinate(self):
        frame = FrameEvidence(0, 1, None, (player("H", 3.0, 4.0, 0),))
        features = list(iter_frame_features([frame], self.config))[0]
        self.assertFalse(features.quality.ball_observed)
        self.assertIsNone(features.spatial.nearest_home_m)
        self.assertIsNone(features.frame.ball_xy)

    def test_duplicate_tracklets_do_not_inflate_top_k_or_team_density(self):
        frame = FrameEvidence(
            0, 1, (10.0, 10.0),
            (player("H", 10.1, 10.0, 0), player("H", 10.15, 10.0, 1),
             player("A", 15.0, 10.0, 2)),
        )
        features = list(iter_frame_features([frame], self.config))[0]
        self.assertEqual(features.spatial.unique_player_count_home, 1)
        self.assertEqual(features.quality.duplicate_observations, 1)
        self.assertEqual(features.spatial.topk_home_mean_m, features.spatial.nearest_home_m)

    def test_zero_ball_one_team_and_low_coverage_produce_finite_quality(self):
        frame = FrameEvidence(0, 1, (0.0, 0.0), (player("A", 0.2, 0.0, 0),))
        features = list(iter_frame_features([frame], self.config))[0]
        self.assertTrue(features.quality.one_team_visible)
        self.assertTrue(features.quality.low_player_coverage)
        self.assertGreaterEqual(features.quality.confidence_weight, 0.0)
        self.assertLessEqual(features.quality.confidence_weight, 1.0)

    def test_implausible_ball_jump_is_flagged_without_overwriting_raw_positions(self):
        frames = [
            FrameEvidence(0, 1, (0.0, 0.0), (player("H", 0.1, 0.0, 0),)),
            FrameEvidence(1, 1, (20.0, 0.0), (player("H", 0.1, 0.0, 0),)),
        ]
        result = list(iter_frame_features(frames, self.config))[1]
        self.assertTrue(result.quality.implausible_ball_jump)
        self.assertEqual(result.frame.ball_xy, (20.0, 0.0))
        self.assertTrue(0.0 <= result.quality.confidence_weight <= 1.0)

    def test_slot_population_change_is_a_quality_flag_not_an_identity_claim(self):
        frames = [
            FrameEvidence(0, 1, (0.0, 0.0), (player("H", 0.2, 0.0, 0), player("A", 3.0, 0.0, 1))),
            FrameEvidence(1, 1, (0.0, 0.0), (player("H", 0.2, 0.0, 2), player("A", 3.0, 0.0, 3))),
        ]
        result = list(iter_frame_features(frames, self.config))[1]
        self.assertTrue(result.quality.track_population_change)
        self.assertIn("observation_population_change", result.quality.flags)
        self.assertLess(result.quality.confidence_weight, 1.0)

    def test_gap_motion_uses_last_observed_ball_as_context_only(self):
        frames = [
            FrameEvidence(0, 1, (50.0, 30.0),
                          (player("H", 50.5, 30.0, 0), player("A", 53.0, 30.0, 1))),
            FrameEvidence(1, 1, None,
                          (player("H", 51.0, 30.0, 0), player("A", 52.6, 30.0, 1))),
            FrameEvidence(2, 1, None,
                          (player("H", 51.5, 30.0, 0), player("A", 52.2, 30.0, 1))),
            FrameEvidence(3, 1, None,
                          (player("H", 52.0, 30.0, 0), player("A", 51.8, 30.0, 1))),
        ]
        features = list(iter_frame_features(frames, self.config))
        gap = features[-1]
        self.assertIsNone(gap.frame.ball_xy)
        self.assertTrue(gap.quality.ball_missing)
        self.assertIsNotNone(gap.motion.last_ball_anchor_xy)
        self.assertEqual(gap.motion.gap_candidate_team, "A")

    def test_half_boundary_resets_ball_anchor_and_temporal_motion(self):
        frames = [
            FrameEvidence(0, 1, (10.0, 10.0), (player("H", 11.0, 10.0, 0),)),
            FrameEvidence(1, 2, None, (player("H", 11.0, 10.0, 0),)),
        ]
        result = list(iter_frame_features(frames, self.config))[1]
        self.assertIsNone(result.motion.last_ball_anchor_xy)
        self.assertIsNone(result.motion.derived_ball_speed_mps)
        self.assertFalse(result.quality.implausible_ball_jump)


if __name__ == "__main__":
    unittest.main()
