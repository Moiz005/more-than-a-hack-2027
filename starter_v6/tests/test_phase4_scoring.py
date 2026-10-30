import unittest

from starter_v6.inference import iter_infer_e02
from starter_v6.features import E02Config
from starter_v6.possession import (
    FrameEvidence,
    PlayerEvidence,
    PossessionConfig,
    infer_possession,
)


def stationary_players():
    return tuple(
        PlayerEvidence("H" if index % 2 == 0 else "A", 20.0 + index, 20.0, 0.0, index)
        for index in range(8)
    )


class Phase4ScoringTests(unittest.TestCase):
    def test_switching_cue_families_does_not_share_confirmation_counter(self):
        frames = [
            FrameEvidence(0, 1, (20.0, 20.0), (), 0.1, True),
            FrameEvidence(1, 1, (20.0, 20.0), stationary_players(), 0.0),
        ]
        results = infer_possession(frames, PossessionConfig())
        self.assertFalse(results[0].dead_ball_evidence.confirmed)
        self.assertFalse(results[1].dead_ball_evidence.confirmed)
        self.assertEqual(results[0].dead_ball_evidence.cues, ("restart_stationary",))
        self.assertEqual(results[1].dead_ball_evidence.cues, ("stationary_context",))

    def test_persistent_same_cue_confirms_and_retains_soft_score(self):
        frames = [
            FrameEvidence(0, 1, (20.0, 20.0), (), 0.1, True),
            FrameEvidence(1, 1, (20.0, 20.0), (), 0.1, True),
        ]
        results = infer_possession(frames, PossessionConfig())
        self.assertFalse(results[0].dead_ball_evidence.confirmed)
        self.assertTrue(results[1].dead_ball_evidence.confirmed)
        self.assertEqual(results[1].dead_ball_evidence.confirmation_family, "restart_stationary")
        self.assertEqual(results[1].dead_ball_evidence.dead_score, 0.75)

    def test_unconfirmed_dead_context_reaches_e02_as_competing_soft_evidence(self):
        players = tuple(
            [PlayerEvidence("H", 10.1 + 0.1 * index, 10.0, 0.0, index) for index in range(5)]
            + [PlayerEvidence("A", 18.0 + 0.1 * index, 10.0, 0.0, index + 5) for index in range(5)]
        )
        frames = [FrameEvidence(0, 1, (10.0, 10.0), (
            *players,
        ), 0.1, True)]
        result = list(iter_infer_e02(frames, PossessionConfig(min_observation_confidence=0.1), E02Config()))[0]
        self.assertGreater(result.emission.dead, 0.0)
        self.assertGreater(result.emission.home, 0.0)
        self.assertFalse(result.inference.dead_ball_evidence.confirmed)

    def test_boundary_hard_evidence_is_not_added_to_a_second_dead_vote(self):
        frame = FrameEvidence(0, 1, (-1.0, 20.0), stationary_players(), 0.0, True)
        result = infer_possession([frame], PossessionConfig())[0]
        self.assertTrue(result.dead_ball_evidence.hard_evidence)
        self.assertEqual(result.dead_ball_evidence.cues, ("out_of_bounds",))
        self.assertEqual(result.dead_ball_evidence.confirmation_family, "out_of_bounds")

    def test_optional_micro_dead_filters_are_explicit_and_hard_evidence_is_exempt(self):
        weak_frames = [
            FrameEvidence(i, 1, (20.0, 20.0), (), 0.1, True)
            for i in range(2)
        ]
        short_filtered = infer_possession(
            weak_frames,
            PossessionConfig(micro_dead_filter="short"),
        )
        self.assertEqual([item.label for item in short_filtered], ["X", "X"])

        hard = infer_possession(
            [FrameEvidence(0, 1, (-1.0, 20.0), (), 0.0)],
            PossessionConfig(micro_dead_filter="long"),
        )
        self.assertEqual(hard[0].label, "D")
        self.assertTrue(hard[0].dead_ball_evidence.hard_evidence)

    def test_micro_dead_filter_rejects_unknown_modes(self):
        with self.assertRaises(ValueError):
            PossessionConfig(micro_dead_filter="tuned")


if __name__ == "__main__":
    unittest.main()
