"""Synthetic E01 behavior tests. All coordinates and evidence are generated here."""

import unittest

from starter_v5.possession import (
    FrameEvidence,
    PlayerEvidence,
    PossessionConfig,
    infer_possession,
    observe_team,
    possession_spells,
)


def controlled_frame(index, half, team, ball_x=0.0):
    other = "A" if team == "H" else "H"
    return FrameEvidence(
        frame=index,
        half=half,
        ball_xy=(ball_x, 0.0),
        ball_speed_mps=0.3,
        players=(
            PlayerEvidence(team, ball_x + 0.25, 0.0, 1.2),
            PlayerEvidence(other, ball_x + 4.0, 0.0, 1.4),
        ),
    )


def restart_frame(index, half=1, speed=0.1):
    return FrameEvidence(
        frame=index,
        half=half,
        ball_xy=(30.0, 20.0),
        ball_speed_mps=speed,
        restart_context=True,
        players=(
            PlayerEvidence("H", 35.0, 20.0, 0.2),
            PlayerEvidence("A", 40.0, 20.0, 0.3),
        ),
    )


class MissingAwareEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.config = PossessionConfig()

    def test_close_opponent_margin_is_unknown_not_a_forced_team(self):
        frame = FrameEvidence(
            0, 1, (10.0, 10.0),
            (PlayerEvidence("H", 10.2, 10.0), PlayerEvidence("A", 10.3, 10.0)),
        )
        evidence = observe_team(frame, self.config)
        self.assertTrue(evidence.ball_observed)
        self.assertIsNone(evidence.team)
        self.assertLess(evidence.confidence, self.config.min_observation_confidence)

    def test_missing_ball_is_explicit_and_does_not_become_dead_ball(self):
        frames = [controlled_frame(i, 1, "H") for i in range(3)]
        frames += [FrameEvidence(i, 1, None, ()) for i in range(3, 8)]
        results = infer_possession(frames, self.config)
        self.assertEqual([item.label for item in results], ["X", "X", "H", "H", "H", "H", "H", "H"])
        self.assertFalse(results[3].team_evidence.ball_observed)
        self.assertFalse(results[3].dead_ball_evidence.confirmed)

    def test_home_gap_home_is_one_spell_without_artificial_dead_ball(self):
        frames = [controlled_frame(i, 1, "H") for i in range(3)]
        frames += [FrameEvidence(i, 1, None, ()) for i in range(3, 8)]
        frames += [controlled_frame(i, 1, "H") for i in range(8, 11)]

        results = infer_possession(frames, self.config)
        labels = [item.label for item in results]

        self.assertEqual(labels, ["X", "X"] + ["H"] * 9)
        self.assertEqual(possession_spells(labels), [("H", 2, 10)])
        self.assertTrue(all(not item.dead_ball_evidence.confirmed for item in results[3:8]))

    def test_missing_ball_carry_expires_to_unknown_without_switch(self):
        frames = [controlled_frame(i, 1, "H") for i in range(3)]
        gap_end = 3 + self.config.max_missing_frames + 1
        frames += [FrameEvidence(i, 1, None, ()) for i in range(3, gap_end)]
        frames += [controlled_frame(gap_end, 1, "A"), controlled_frame(gap_end + 1, 1, "A"),
                   controlled_frame(gap_end + 2, 1, "A")]
        labels = [item.label for item in infer_possession(frames, self.config)]
        self.assertEqual(labels[2], "H")
        self.assertEqual(labels[3 + self.config.max_missing_frames - 1], "H")
        self.assertEqual(labels[3 + self.config.max_missing_frames], "X")
        self.assertEqual(labels[-1], "A")

    def test_confirmed_turnover_requires_consecutive_clear_team_evidence(self):
        frames = [controlled_frame(i, 1, "H") for i in range(3)]
        frames += [controlled_frame(3, 1, "A"), controlled_frame(4, 1, "A"),
                   controlled_frame(5, 1, "A")]
        labels = [item.label for item in infer_possession(frames, self.config)]
        self.assertEqual(labels, ["X", "X", "H", "H", "H", "A"])

    def test_controlled_h_pass_survives_one_brief_nearest_a_observation(self):
        frames = [controlled_frame(i, 1, "H") for i in range(3)]
        frames.append(FrameEvidence(
            frame=3, half=1, ball_xy=(0.0, 0.0),
            players=(PlayerEvidence("H", 1.0, 0.0), PlayerEvidence("A", 0.2, 0.0)),
        ))
        frames.append(controlled_frame(4, 1, "H"))
        labels = [item.label for item in infer_possession(frames, self.config)]
        self.assertEqual(labels, ["X", "X", "H", "H", "H"])

    def test_ambiguous_frame_does_not_confirm_turnover(self):
        frames = [controlled_frame(i, 1, "H") for i in range(3)]
        frames.append(FrameEvidence(
            3, 1, (0.0, 0.0),
            (PlayerEvidence("H", 0.3, 0.0), PlayerEvidence("A", 0.4, 0.0)),
        ))
        frames += [controlled_frame(4, 1, "A"), controlled_frame(5, 1, "A"),
                   controlled_frame(6, 1, "A")]
        labels = [item.label for item in infer_possession(frames, self.config)]
        self.assertEqual(labels, ["X", "X", "H", "H", "H", "H", "A"])


class DeadBallAndTimelineTests(unittest.TestCase):
    def setUp(self):
        self.config = PossessionConfig()

    def test_reliable_out_of_bounds_location_is_independent_dead_ball_evidence(self):
        frame = FrameEvidence(
            frame=0, half=1, ball_xy=(-1.0, 20.0), ball_speed_mps=0.2,
            players=(PlayerEvidence("H", 5.0, 20.0),),
        )
        result = infer_possession([frame], self.config)[0]
        self.assertEqual(result.label, "D")
        self.assertIn("out_of_bounds", result.dead_ball_evidence.cues)

    def test_restart_marker_alone_does_not_force_dead_ball_or_owner(self):
        frame = FrameEvidence(
            frame=0, half=1, ball_xy=(30.0, 20.0), ball_speed_mps=3.0,
            players=(PlayerEvidence("A", 35.0, 20.0, 1.0),), restart_context=True,
        )
        result = infer_possession([frame], self.config)[0]
        self.assertEqual(result.label, "X")
        self.assertFalse(result.dead_ball_evidence.confirmed)
        self.assertIsNone(result.team_evidence.team)

    def test_restart_and_stationary_ball_confirm_dead_ball_without_owner(self):
        results = infer_possession([restart_frame(0), restart_frame(1)], self.config)
        self.assertEqual([item.label for item in results], ["X", "D"])
        self.assertIn("restart_stationary", results[-1].dead_ball_evidence.cues)

    def test_collective_stationary_motion_is_weak_dead_ball_evidence(self):
        players = tuple(
            PlayerEvidence("H" if index % 2 == 0 else "A", 5.0 + index, 10.0, 0.2)
            for index in range(8)
        )
        frames = [
            FrameEvidence(i, 1, (0.0, 0.0), players, ball_speed_mps=0.1)
            for i in range(2)
        ]
        results = infer_possession(frames, self.config)
        self.assertEqual([item.label for item in results], ["X", "D"])
        self.assertIn("stationary_context", results[-1].dead_ball_evidence.cues)

    def test_half_boundary_resets_state_and_labels_ungraded_frames_x(self):
        frames = [controlled_frame(i, 1, "H") for i in range(3)]
        frames += [FrameEvidence(3, 0, None, ()), FrameEvidence(4, 0, None, ())]
        frames += [controlled_frame(5, 2, "A"), controlled_frame(6, 2, "A"),
                   controlled_frame(7, 2, "A")]
        labels = [item.label for item in infer_possession(frames, self.config)]
        self.assertEqual(labels, ["X", "X", "H", "X", "X", "X", "X", "A"])

    def test_dead_ball_splits_same_team_possession_into_two_spells(self):
        frames = [controlled_frame(i, 1, "H") for i in range(3)]
        frames += [restart_frame(3), restart_frame(4)]
        frames += [controlled_frame(i, 1, "H") for i in range(5, 8)]
        labels = [item.label for item in infer_possession(frames, self.config)]
        self.assertEqual(labels, ["X", "X", "H", "H", "D", "X", "X", "H"])
        self.assertEqual(possession_spells(labels), [("H", 2, 3), ("H", 7, 7)])

    def test_noncontiguous_or_nonfinite_observations_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "contiguous"):
            infer_possession([controlled_frame(0, 1, "H"), controlled_frame(2, 1, "H")], self.config)
        bad = FrameEvidence(0, 1, (float("nan"), 0.0), ())
        with self.assertRaisesRegex(ValueError, "finite"):
            infer_possession([bad], self.config)


if __name__ == "__main__":
    unittest.main()
