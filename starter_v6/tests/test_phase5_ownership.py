import unittest

from starter_v6.features import E02Config
from starter_v6.inference import iter_infer_e02
from starter_v6.possession import FrameEvidence, PlayerEvidence, PossessionConfig


def frame(index, team="H", ball=True, home_x=None, away_x=None):
    if home_x is None:
        home_x = 0.5 if team == "H" else 4.0
    if away_x is None:
        away_x = 4.0 if team == "H" else 0.5
    return FrameEvidence(
        index, 1, (0.0, 0.0) if ball else None,
        (PlayerEvidence("H", home_x, 0.0, 1.0, 0),
         PlayerEvidence("A", away_x, 0.0, 1.0, 1)),
    )


def phase5_config():
    return E02Config(
        top_k=2, quality_reference_players=2, low_player_count=1,
        gap_min_players_per_team=1, gap_support_frames=2,
        gap_score_threshold=0.45, gap_score_margin=0.15,
    )


class Phase5OwnershipTests(unittest.TestCase):
    def test_team_observation_preserves_both_team_scores(self):
        results = list(iter_infer_e02(
            [frame(0)], PossessionConfig(), phase5_config(),
        ))
        evidence = results[0].inference.team_evidence
        self.assertGreater(evidence.home_score, evidence.away_score)
        self.assertGreaterEqual(evidence.home_score, 0.0)
        self.assertGreaterEqual(evidence.away_score, 0.0)

    def test_accepted_gap_has_direction_and_changes_decoder_emission(self):
        frames = [frame(i) for i in range(3)]
        frames += [
            frame(3, ball=False, home_x=0.8, away_x=2.5),
            frame(4, ball=False, home_x=1.1, away_x=2.0),
            frame(5, ball=False, home_x=1.4, away_x=1.5),
        ]
        frames += [frame(i, team="A") for i in range(6, 9)]
        results = list(iter_infer_e02(frames, PossessionConfig(), phase5_config()))
        accepted = results[3]
        self.assertEqual(accepted.gap_decision, "accepted")
        self.assertIsNotNone(accepted.ownership_evidence)
        self.assertTrue(accepted.ownership_evidence.accepted)
        self.assertEqual(accepted.ownership_evidence.direction, "H_to_A")
        self.assertGreater(accepted.emission.away, accepted.emission.home)
        self.assertEqual(accepted.ownership_evidence.start_frame, 3)
        self.assertEqual(accepted.ownership_evidence.end_frame, 5)

    def test_missing_ball_without_accepted_recovery_has_no_forced_team_evidence(self):
        frames = [frame(i) for i in range(3)]
        frames += [frame(i, ball=False) for i in range(3, 6)]
        frames += [frame(i) for i in range(6, 9)]
        results = list(iter_infer_e02(frames, PossessionConfig(), phase5_config()))
        self.assertTrue(all(item.ownership_evidence is None for item in results[3:6]))
        self.assertTrue(all(item.inference.label != "D" for item in results[3:6]))

    def test_live_goalkeeper_like_control_is_not_dead_ball(self):
        players = (
            PlayerEvidence("H", 5.2, 5.0, 0.3, 1),
            PlayerEvidence("A", 15.0, 5.0, 0.8, 2),
        )
        frames = [FrameEvidence(i, 1, (5.0 + 0.1 * i, 5.0), players, 0.2) for i in range(4)]
        results = list(iter_infer_e02(frames, PossessionConfig(min_observation_confidence=0.1), E02Config()))
        self.assertTrue(all(item.inference.label != "D" for item in results))
        self.assertTrue(all(item.emission.dead < 1.0 for item in results))


if __name__ == "__main__":
    unittest.main()
