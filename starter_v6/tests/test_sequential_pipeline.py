import unittest
from dataclasses import dataclass

from starter_v6.emissions import frame_emission
from starter_v6.hmm import HMMConfig
from starter_v6.sequential import PlayStateDecision, run_live_ownership, compose_labels
from starter_v6.features import E02Config
from starter_v6.inference import iter_infer_e02
from starter_v6.possession import FrameEvidence, PlayerEvidence, PossessionConfig


class SequentialPipelineTests(unittest.TestCase):
    def test_dead_decision_cannot_carry_stage2_ownership(self):
        with self.assertRaisesRegex(ValueError, "DEAD"):
            PlayStateDecision(0, 1, "DEAD", "confirmed_stop", 1.0, (), (), "H")

    def test_stage1_contract_rejects_team_assignment_and_bad_half_state(self):
        with self.assertRaisesRegex(ValueError, "cannot carry"):
            PlayStateDecision(0, 1, "LIVE", "observed", .8, (), (), "A")
        with self.assertRaisesRegex(ValueError, "half mask"):
            PlayStateDecision(0, 0, "LIVE", "observed", .8, (), ())

    def test_live_ownership_decoder_splits_at_dead_and_x_and_emits_only_ha(self):
        rows = [
            (1, frame_emission(0, 1, home=.9, away=.1), True),
            (1, frame_emission(1, 1, home=.9, away=.1), True),
            (1, frame_emission(2, 1, home=.1, away=.9), False),
            (1, frame_emission(3, 1, home=.1, away=.9), True),
            (1, frame_emission(4, 1, home=.1, away=.9), True),
        ]
        labels, stats = run_live_ownership(rows, HMMConfig())
        self.assertEqual(set(labels.values()), {"H", "A"})
        self.assertEqual(stats["live_segments"], 2)
        self.assertEqual(stats["stage2_frames"], 4)

    def test_compose_preserves_stage1_dead_and_ungraded_x(self):
        states = ["LIVE", "DEAD", "LIVE", "UNGRADED"]
        ownership = {0: "H", 2: "A"}
        self.assertEqual(compose_labels(states, ownership), ["H", "D", "A", "X"])

    def test_composition_requires_stage2_to_cover_exactly_live_frames(self):
        with self.assertRaisesRegex(ValueError, "exactly"):
            compose_labels(["LIVE", "DEAD"], {})
        with self.assertRaisesRegex(ValueError, "exactly"):
            compose_labels(["LIVE", "DEAD"], {0: "H", 1: "A"})

    def test_stage1_is_invariant_to_home_away_identity(self):
        features = E02Config(top_k=2, quality_reference_players=2, low_player_count=1,
                             stage1_lifecycle_enabled=True,
                             stage1_stage2_fusion_enabled=True)
        def make(owner):
            other = "A" if owner == "H" else "H"
            frames = []
            for index, x in enumerate((-1.2, -1.2, 20.0, 20.3, 20.6, 20.9)):
                ball = (x, 30.0)
                players = (PlayerEvidence(owner, x + .3, 30.0, 1., 1),
                           PlayerEvidence(other, x + 5., 30.0, 1., 2))
                frames.append(FrameEvidence(index, 1, ball, players,
                                            (.1, .1, 2., 2., 2., 2.)[index]))
            return [row.inference.label for row in iter_infer_e02(
                frames, PossessionConfig(), features, stage1_only=True)]
        self.assertEqual(make("H"), make("A"))
        self.assertEqual(make("H"), ["X", "D", "D", "D", "D", "X"])

    def test_ownership_only_mode_cannot_emit_dead_even_for_boundary_frames(self):
        frames = [
            FrameEvidence(index, 1, (-1.2, 30.0), (), .1)
            for index in range(3)
        ]
        config = E02Config(stage1_lifecycle_enabled=True,
                           stage1_stage2_fusion_enabled=True)
        outputs = list(iter_infer_e02(
            frames, PossessionConfig(), config, ownership_only=True,
        ))
        self.assertTrue(all(row.inference.label != "D" for row in outputs))
        self.assertTrue(all(row.emission.dead == 0.0 for row in outputs))

    def test_stage2_restart_action_does_not_name_or_acquire_restarting_team(self):
        frame = FrameEvidence(
            17, 2, (50.0, 34.0),
            (PlayerEvidence("H", 50.2, 34.0, 1.0, 1),
             PlayerEvidence("A", 56.0, 34.0, 1.0, 2)),
            3.0, restart_action="restart_delivery",
        )
        config = E02Config(top_k=2, quality_reference_players=2, low_player_count=1,
                           stage1_lifecycle_enabled=True,
                           stage1_stage2_fusion_enabled=True)
        (result,) = list(iter_infer_e02(
            [frame], PossessionConfig(acquire_frames=1), config,
            ownership_only=True,
        ))
        self.assertEqual(result.inference.label, "X")
        self.assertEqual(result.emission.home, result.emission.away)


if __name__ == "__main__":
    unittest.main()
