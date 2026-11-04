"""Adversarial tactical-only tests for non-labeling ATD proposals."""

import unittest

from starter_v6.atd_signals import AtdSignalConfig, iter_atd_signals
from starter_v6.features import iter_frame_features
from starter_v6.possession import FrameEvidence, PlayerEvidence


def players(home_x, away_x, shift=0.0, slot_offset=0):
    rows = []
    for index in range(5):
        y = 30.0 if index == 0 else 12.0 + index * 8.0
        offset = 0.0 if index == 0 else index * 3.0
        rows.append(PlayerEvidence("H", home_x + shift + offset, y, 2.0, index + slot_offset))
        rows.append(PlayerEvidence("A", away_x + offset, y, 2.0, index + 10 + slot_offset))
    return tuple(rows)


def signals(frames):
    return list(iter_atd_signals(iter_frame_features(frames)))


class AtdSignalTests(unittest.TestCase):
    def test_persistent_control_requires_proximity_comotion_and_uncontested_support(self):
        frames = [
            FrameEvidence(i, 1, (10.0 + i * 0.1, 30.0), players(10.5 + i * 0.1, 18.0, i * 0.1))
            for i in range(4)
        ]
        result = signals(frames)
        self.assertIsNone(result[0].control.candidate_team)
        self.assertEqual(result[-1].control.candidate_team, "H")
        self.assertTrue(result[-1].control.comotion_supported)
        self.assertGreaterEqual(result[-1].control.persistent_frames, 3)

    def test_contested_proximity_does_not_claim_control(self):
        frames = [
            FrameEvidence(i, 1, (10.0 + i * 0.1, 30.0), players(10.6 + i * 0.1, 9.6 + i * 0.1, i * 0.1))
            for i in range(4)
        ]
        result = signals(frames)
        self.assertTrue(result[-1].control.contradictory_opponent_control)
        self.assertIsNone(result[-1].control.candidate_team)

    def test_missing_ball_and_long_gap_reset_temporal_control(self):
        frames = [
            FrameEvidence(0, 1, (10.0, 30.0), players(10.5, 18.0)),
            FrameEvidence(1, 1, (10.1, 30.0), players(10.6, 18.0, 0.1)),
            FrameEvidence(2, 1, None, players(10.7, 18.0, 0.2)),
            FrameEvidence(3, 1, (10.3, 30.0), players(10.8, 18.0, 0.3)),
        ]
        result = signals(frames)
        self.assertEqual(result[2].ball_position_provenance, "ATD_missing")
        self.assertEqual(result[2].stationary_state, "unknown_missing_ball")
        self.assertIsNone(result[-1].control.candidate_team)
        self.assertEqual(result[-1].control.persistent_frames, 1)

    def test_aerial_flight_and_speed_spike_are_not_control_or_restart(self):
        frames = [
            FrameEvidence(0, 1, (20.0, 20.0), players(40.0, 60.0), restart_context=True),
            FrameEvidence(1, 1, (20.5, 20.0), players(40.0, 60.0), restart_context=True),
            FrameEvidence(2, 1, (50.0, 40.0), players(40.0, 60.0), restart_context=True),
        ]
        result = signals(frames)
        self.assertIsNone(result[-1].control.candidate_team)
        self.assertTrue(result[1].ball_motion.rapid_uncontrolled_motion)
        self.assertFalse(result[-1].ball_motion.rapid_uncontrolled_motion)
        self.assertFalse(result[-1].restart_motion.candidate)
        self.assertEqual(result[-1].restart_motion.supported_motion_frames, 0)

    def test_loose_and_deflected_ball_do_not_gain_control_from_proximity_alone(self):
        frames = [
            FrameEvidence(0, 1, (20.0, 30.0), players(18.4, 21.5)),
            FrameEvidence(1, 1, (20.5, 30.0), players(18.4, 21.5)),
            FrameEvidence(2, 1, (22.5, 30.0), players(18.4, 21.5)),
            FrameEvidence(3, 1, (22.6, 30.0), players(18.4, 21.5)),
        ]
        result = signals(frames)
        self.assertIsNone(result[1].control.candidate_team)
        self.assertIsNone(result[2].control.candidate_team)
        self.assertIsNone(result[3].control.candidate_team)

    def test_long_gap_then_return_starts_new_temporal_support(self):
        frames = [FrameEvidence(0, 1, (10.0, 30.0), players(10.5, 18.0))]
        frames.extend(FrameEvidence(i, 1, None, players(10.5, 18.0)) for i in range(1, 31))
        frames.extend([
            FrameEvidence(31, 1, (10.1, 30.0), players(10.6, 18.0)),
            FrameEvidence(32, 1, (10.2, 30.0), players(10.7, 18.0, 0.1)),
        ])
        result = signals(frames)
        self.assertEqual(result[30].stationary_state, "unknown_missing_ball")
        self.assertEqual(result[31].control.persistent_frames, 1)
        self.assertIsNone(result[32].control.candidate_team)

    def test_return_from_confirmed_dead_context_does_not_copy_dead_state(self):
        frames = [
            FrameEvidence(0, 1, (45.0, 30.0), players(46.0, 60.0), 0.0, True),
            FrameEvidence(1, 1, None, players(46.0, 60.0), None, True),
            FrameEvidence(2, 1, (45.1, 30.0), players(45.6, 60.0), 2.5, True),
        ]
        result = signals(frames)
        self.assertEqual(result[1].stationary_state, "unknown_missing_ball")
        self.assertFalse(result[1].restart_motion.candidate)
        self.assertEqual(result[2].ball_position_provenance, "ATD_observed")
        self.assertFalse(result[2].restart_motion.candidate)

    def test_consecutive_clean_boundary_observations_produce_only_a_hypothesis(self):
        frames = [
            FrameEvidence(0, 1, (105.0, 25.0), players(103.0, 95.0)),
            FrameEvidence(1, 1, (105.5, 25.0), players(103.0, 95.0)),
        ]
        result = signals(frames)[-1]
        self.assertTrue(result.boundary.candidate)
        self.assertEqual(result.boundary.boundary, "goal_line_hypothesis")
        self.assertLess(result.boundary.confidence, 0.5)

    def test_touchline_and_goal_line_are_distinct_hypotheses(self):
        frames = [
            FrameEvidence(0, 1, (52.0, 67.7), players(54.0, 65.0)),
            FrameEvidence(1, 1, (52.0, 68.2), players(54.0, 65.0)),
        ]
        result = signals(frames)[-1]
        self.assertTrue(result.boundary.candidate)
        self.assertEqual(result.boundary.boundary, "touchline_hypothesis")

    def test_jump_and_missing_observation_abstain_from_boundary_hypothesis(self):
        for pair in (
            [FrameEvidence(0, 1, (70.0, 25.0), ()), FrameEvidence(1, 1, (-0.2, 25.0), ())],
            [FrameEvidence(0, 1, (105.0, 25.0), ()), FrameEvidence(1, 1, None, ())],
        ):
            self.assertFalse(signals(pair)[-1].boundary.candidate)

    def test_restart_proposal_needs_setup_then_persistent_clean_motion(self):
        frames = [
            FrameEvidence(0, 1, (50.0, 34.0), players(52.0, 60.0), 0.0, True),
            FrameEvidence(1, 1, (51.0, 34.0), players(52.0, 60.0), 25.0, True),
            FrameEvidence(2, 1, (52.0, 34.0), players(52.0, 60.0), 25.0, True),
        ]
        result = signals(frames)
        self.assertEqual(result[0].stationary_state, "stationary_setup_candidate")
        self.assertFalse(result[1].restart_motion.candidate)
        self.assertTrue(result[2].restart_motion.candidate)
        self.assertEqual(result[2].restart_motion.reason, "setup_then_persistent_motion_proposal")

    def test_restart_setup_support_expires_after_bounded_interval(self):
        frames = [FrameEvidence(0, 1, (50.0, 34.0), players(52.0, 60.0), 0.0, True)]
        frames.extend(FrameEvidence(i, 1, (50.0 + i * 0.1, 34.0), players(52.0, 60.0), 2.5, True) for i in range(1, 5))
        result = list(iter_atd_signals(
            iter_frame_features(frames), AtdSignalConfig(restart_setup_max_age_frames=2)
        ))
        self.assertTrue(result[2].restart_motion.candidate)
        self.assertFalse(result[3].restart_motion.candidate)

    def test_stationary_ball_without_restart_context_is_not_dead_or_restart(self):
        result = signals([FrameEvidence(0, 1, (40.0, 30.0), players(41.0, 55.0), 0.0, False)])[0]
        self.assertEqual(result.stationary_state, "stationary_live_or_unresolved")
        self.assertFalse(result.restart_motion.candidate)

    def test_half_change_resets_all_temporal_support(self):
        frames = [
            FrameEvidence(0, 1, (10.0, 30.0), players(10.5, 18.0)),
            FrameEvidence(1, 2, (10.1, 30.0), players(10.6, 18.0, 0.1)),
        ]
        result = signals(frames)
        self.assertEqual(result[-1].control.persistent_frames, 1)
        self.assertFalse(result[-1].boundary.candidate)


if __name__ == "__main__":
    unittest.main()
