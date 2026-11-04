"""Synthetic quality-aware kickoff execution detection contracts."""

import unittest

from starter_v6.ingestion import ATDFrame, ATDMetadata, Observation, TrackSlot
from starter_v6.timeline import TacticalTimeline
from starter_v6.kickoff_atd import (
    AMBIGUOUS,
    ARMED,
    BOUNDED_INTERVAL,
    CONFIRMED,
    EXECUTED,
    INSUFFICIENT_EVIDENCE,
    INVALID_ALIGNMENT,
    KickoffATDConfig,
    detect_kickoff_execution,
    distance_to_centre_m,
)
from starter_v6.kickoff_tags import extract_opening_kickoff_candidates
from starter_v6.ingestion import SmartTagEvent


METADATA = ATDMetadata(
    team_ids=("home", "away"),
    team_names=("Barcelona", "Athletic Club"),
    slots=(
        TrackSlot(0, "home-1", "Home 1", "H"),
        TrackSlot(1, "away-1", "Away 1", "A"),
    ),
    pitch_length_m=100.0,
    pitch_width_m=60.0,
)


def timeline(frame_count=400, split=300):
    half_by_frame = bytearray(frame_count)
    for frame in range(split):
        half_by_frame[frame] = 1
    for frame in range(split, frame_count):
        half_by_frame[frame] = 2
    return TacticalTimeline(
        source="tactical", fps=25, frame_count=frame_count,
        half_by_frame=bytes(half_by_frame),
        half_ranges=((1, 0, split - 1), (2, split, frame_count - 1)),
    )


def candidate(start, end, half=1, before=0, after=0):
    event = SmartTagEvent(
        "SET PIECES", start / 25.0, end / 25.0, start, end,
        {"Type": "Kick Off (Start)", "Half": "1st Half" if half == 1 else "2nd Half", "Team": "N/A"},
        None, "N/A",
    )
    return extract_opening_kickoff_candidates(
        [event], timeline=timeline(),
        search_margin_before_frames=before, search_margin_after_frames=after,
    ).records[0]


def observation(x, y=0.5, speed=0.0, valid=True, speed_valid=True):
    return Observation(
        x, y, speed if speed_valid else float("nan"),
        x * METADATA.pitch_length_m if valid else float("nan"),
        y * METADATA.pitch_width_m if valid else float("nan"),
        valid, speed_valid,
    )


def frame(index, ball_x=0.5, ball_y=0.5, ball_speed=0.0, ball_valid=True,
          speed_valid=True, player_x=0.52, player_valid=True):
    players = (
        observation(player_x, 0.5, speed=0.0, valid=player_valid),
        observation(0.75, 0.5, speed=0.0, valid=player_valid),
    )
    return ATDFrame(
        frame_id=index + 1,
        video_frame=index,
        players=players,
        ball=observation(ball_x, ball_y, speed=ball_speed,
                          valid=ball_valid, speed_valid=speed_valid),
    )


def setup_and_kick(start=0, kick=3, step=0.004, speed_valid=True, player_x=0.52):
    rows = [frame(index, player_x=player_x) for index in range(start, kick)]
    for index in range(kick, kick + 2):
        rows.append(frame(index, ball_x=0.5 + step * (index - kick + 1),
                          ball_speed=step * METADATA.pitch_length_m * 25.0,
                          speed_valid=speed_valid, player_x=player_x))
    return rows


class KickoffATDTests(unittest.TestCase):
    def test_distance_to_centre_is_metric_scaled_on_both_axes(self):
        ball = observation(0.52, 0.55)
        self.assertAlmostEqual(distance_to_centre_m(ball, METADATA), 3.6055512755)

    def test_normal_kickoff_returns_first_motion_frame_and_evidence_reasons(self):
        result = detect_kickoff_execution(
            setup_and_kick(), METADATA, candidate(0, 5), timeline=timeline(),
        )

        self.assertEqual(result.status, CONFIRMED)
        self.assertEqual(result.execution_frame, 3)
        self.assertAlmostEqual(result.video_timestamp_seconds, 3 / 25.0)
        self.assertIn("centre_setup", result.reasons)
        self.assertIn("stationary_preparation", result.reasons)
        self.assertIn("consecutive_ball_motion", result.reasons)
        self.assertIn("nearby_player", result.reasons)

    def test_subtle_motion_is_confirmed_without_exact_centre_coordinate(self):
        result = detect_kickoff_execution(
            [frame(0, 0.505), frame(1, 0.505), frame(2, 0.505),
             frame(3, 0.507, ball_speed=0.0, speed_valid=False),
             frame(4, 0.509, ball_speed=0.0, speed_valid=False)],
            METADATA, candidate(0, 5), timeline=timeline(),
            config=KickoffATDConfig(min_movement_displacement_m=0.1),
        )
        self.assertEqual(result.status, CONFIRMED)
        self.assertEqual(result.execution_frame, 3)

    def test_missing_provider_speed_does_not_invalidate_valid_position_motion(self):
        result = detect_kickoff_execution(
            setup_and_kick(speed_valid=False), METADATA, candidate(0, 5), timeline=timeline(),
        )
        self.assertEqual(result.status, CONFIRMED)
        self.assertEqual(result.execution_frame, 3)

    def test_stationary_forever_and_jitter_only_fail_closed(self):
        stationary = detect_kickoff_execution(
            [frame(index) for index in range(8)], METADATA,
            candidate(0, 8), timeline=timeline(),
        )
        jitter = detect_kickoff_execution(
            [frame(0, 0.5), frame(1, 0.501), frame(2, 0.499), frame(3, 0.5),
             frame(4, 0.501)], METADATA, candidate(0, 5), timeline=timeline(),
        )
        self.assertEqual(stationary.status, INSUFFICIENT_EVIDENCE)
        self.assertIsNone(stationary.execution_frame)
        self.assertEqual(jitter.status, INSUFFICIENT_EVIDENCE)

    def test_player_motion_with_stationary_ball_is_not_a_kick(self):
        result = detect_kickoff_execution(
            [frame(index, player_x=0.52 + index * 0.03) for index in range(8)],
            METADATA, candidate(0, 8), timeline=timeline(),
        )
        self.assertEqual(result.status, INSUFFICIENT_EVIDENCE)

    def test_missing_ball_breaks_preparation_and_never_bridges_motion(self):
        rows = [frame(0), frame(1), frame(2), frame(3, ball_valid=False),
                frame(4, ball_x=0.52), frame(5, ball_x=0.54)]
        result = detect_kickoff_execution(
            rows, METADATA, candidate(0, 6), timeline=timeline(),
        )
        self.assertEqual(result.status, INSUFFICIENT_EVIDENCE)
        self.assertIsNone(result.execution_frame)
        self.assertIn("ball_missing", result.reasons)

    def test_one_frame_implausible_jump_is_rejected(self):
        rows = [frame(0), frame(1), frame(2), frame(3, ball_x=0.9), frame(4, ball_x=0.9)]
        result = detect_kickoff_execution(
            rows, METADATA, candidate(0, 5), timeline=timeline(),
        )
        self.assertEqual(result.status, INSUFFICIENT_EVIDENCE)
        self.assertIn("quality_rejected_jump", result.reasons)

    def test_long_gap_is_invalid_alignment_and_not_interpolated(self):
        rows = [frame(0), frame(1), frame(2), frame(4, ball_x=0.53), frame(5, ball_x=0.55)]
        result = detect_kickoff_execution(
            rows, METADATA, candidate(0, 6), timeline=timeline(),
        )
        self.assertEqual(result.status, INVALID_ALIGNMENT)
        self.assertIsNone(result.execution_frame)

    def test_repeated_false_start_is_rejected_before_later_confirmed_start(self):
        rows = [frame(0), frame(1), frame(2),
                frame(3, ball_x=0.504, ball_speed=10.0),
                frame(4, ball_x=0.504, ball_speed=0.0),
                frame(5, ball_x=0.504), frame(6, ball_x=0.504), frame(7, ball_x=0.504),
                frame(8, ball_x=0.508, ball_speed=10.0),
                frame(9, ball_x=0.512, ball_speed=10.0)]
        result = detect_kickoff_execution(
            rows, METADATA, candidate(0, 10), timeline=timeline(),
            config=KickoffATDConfig(min_movement_displacement_m=0.2),
        )
        self.assertEqual(result.status, CONFIRMED)
        self.assertEqual(result.execution_frame, 8)

    def test_multiple_confirmed_motion_starts_are_ambiguous(self):
        rows = setup_and_kick()
        rows += [frame(5, ball_x=0.508), frame(6, ball_x=0.508), frame(7, ball_x=0.508),
                 frame(8, ball_x=0.512, ball_speed=10.0),
                 frame(9, ball_x=0.516, ball_speed=10.0)]
        result = detect_kickoff_execution(
            rows, METADATA, candidate(0, 10), timeline=timeline(),
        )
        self.assertEqual(result.status, AMBIGUOUS)
        self.assertIsNone(result.execution_frame)
        self.assertIn("multiple_motion_candidates", result.reasons)

    def test_sparse_players_do_not_block_valid_ball_motion(self):
        rows = [frame(0, player_valid=False), frame(1, player_valid=False),
                frame(2, player_valid=False),
                frame(3, ball_x=0.504, ball_speed=10.0, player_valid=False),
                frame(4, ball_x=0.508, ball_speed=10.0, player_valid=False)]
        result = detect_kickoff_execution(
            rows, METADATA, candidate(0, 5), timeline=timeline(),
        )
        self.assertEqual(result.status, CONFIRMED)
        self.assertEqual(result.execution_frame, 3)

    def test_frame_shift_does_not_change_detection_frame_relative_to_sequence(self):
        shifted = setup_and_kick(start=250, kick=253)
        result = detect_kickoff_execution(
            shifted, METADATA, candidate(250, 255, before=0, after=0), timeline=timeline(),
        )
        self.assertEqual(result.status, CONFIRMED)
        self.assertEqual(result.execution_frame, 253)

    def test_temporal_scale_can_require_longer_continuous_confirmation(self):
        rows = [frame(0), frame(1), frame(2), frame(3, ball_x=0.502, ball_speed=5.0),
                frame(4, ball_x=0.504, ball_speed=5.0), frame(5, ball_x=0.506, ball_speed=5.0)]
        result = detect_kickoff_execution(
            rows, METADATA, candidate(0, 6), timeline=timeline(),
            config=KickoffATDConfig(
                min_movement_displacement_m=0.1,
                movement_confirmation_frames=3,
            ),
        )
        self.assertEqual(result.status, CONFIRMED)
        self.assertEqual(result.execution_frame, 3)

    def test_candidate_window_is_the_only_search_region(self):
        rows = [frame(0), frame(1), frame(2), frame(3, ball_x=0.53, ball_speed=75.0), frame(4, ball_x=0.55, ball_speed=50.0),
                frame(10), frame(11), frame(12), frame(13), frame(14)]
        result = detect_kickoff_execution(
            rows, METADATA, candidate(10, 15, before=0, after=0), timeline=timeline(),
        )
        self.assertEqual(result.status, INSUFFICIENT_EVIDENCE)
        self.assertIsNone(result.execution_frame)

    def test_half_transition_is_rejected_even_if_positions_move(self):
        local_timeline = timeline(frame_count=10, split=3)
        result = detect_kickoff_execution(
            [frame(0), frame(1), frame(2), frame(3, ball_x=0.53), frame(4, ball_x=0.55)],
            METADATA, candidate(0, 5), timeline=local_timeline,
        )
        self.assertEqual(result.status, INVALID_ALIGNMENT)

    def test_invalid_config_thresholds_are_rejected(self):
        with self.assertRaises(ValueError):
            KickoffATDConfig(fps=0)
        with self.assertRaises(ValueError):
            KickoffATDConfig(centre_setup_radius_m=-1)
        with self.assertRaises(ValueError):
            KickoffATDConfig(movement_confirmation_frames=0)

    def test_raw_frames_are_not_mutated(self):
        rows = setup_and_kick()
        before = tuple(rows)
        detect_kickoff_execution(rows, METADATA, candidate(0, 5), timeline=timeline())
        self.assertEqual(tuple(rows), before)

    def test_result_contains_aggregate_trace_without_frame_payload(self):
        result = detect_kickoff_execution(
            setup_and_kick(), METADATA, candidate(0, 5), timeline=timeline(),
        )
        self.assertIsNotNone(result.trace)
        self.assertEqual(result.trace.evaluated_frames, 5)
        self.assertEqual(result.trace.ball_observed_frames, 5)
        self.assertGreaterEqual(result.trace.center_ball_frames, 3)
        self.assertGreaterEqual(result.trace.nearby_player_frames, 1)
        self.assertEqual(result.evidence_state, EXECUTED)
        self.assertNotIn("frames", result.trace.as_dict())

    def test_short_missing_ball_gap_is_bounded_not_exact(self):
        rows = [frame(0), frame(1), frame(2), frame(3, ball_valid=False),
                frame(4, ball_x=0.506, speed_valid=False),
                frame(5, ball_x=0.512, speed_valid=False),
                frame(6, ball_x=0.518, speed_valid=False)]
        result = detect_kickoff_execution(
            rows, METADATA, candidate(0, 7), timeline=timeline(),
            config=KickoffATDConfig(min_movement_displacement_m=0.2),
        )
        self.assertEqual(result.status, BOUNDED_INTERVAL)
        self.assertEqual(result.evidence_state, ARMED)
        self.assertIsNone(result.execution_frame)
        self.assertIsNotNone(result.execution_interval)
        self.assertIn("gap_bounded_motion", result.reasons)


if __name__ == "__main__":
    unittest.main()
