import math
import unittest

from starter_v6.emissions import fuse_evidence
from starter_v6.features import E02Config
from starter_v6.hmm import HMMConfig, decode
from starter_v6.inference import iter_infer_e02
from starter_v6.possession import FrameEvidence, PlayerEvidence, PossessionConfig, possession_spells


def live_frame(index, team="H", half=1):
    other = "A" if team == "H" else "H"
    return FrameEvidence(
        index, half, (10.0, 10.0),
        (PlayerEvidence(team, 10.2, 10.0, 1.0, 0),
         PlayerEvidence(other, 18.0, 10.0, 1.0, 1)),
        1.0,
    )


class Phase6FusionTests(unittest.TestCase):
    def test_fusion_contract_is_finite_normalized_and_preserves_conflicts(self):
        emission = fuse_evidence(
            0, 1, home=0.8, away=0.2, dead=0.55, live=0.9,
            sources=("geometry", "restart_context"),
        )
        values = (emission.home, emission.away, emission.dead)
        self.assertTrue(all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in values))
        self.assertAlmostEqual(sum(values), 1.0)
        self.assertGreater(emission.home, emission.dead)
        self.assertTrue(emission.informative)

    def test_raw_h_d_h_decodes_to_two_possession_spells(self):
        frames = [live_frame(i, "H") for i in range(3)]
        frames += [
            FrameEvidence(3, 1, (10.0, 10.0), (), 0.1, True),
            FrameEvidence(4, 1, (10.0, 10.0), (), 0.1, True),
        ]
        frames += [live_frame(i, "H") for i in range(5, 8)]
        results = list(iter_infer_e02(
            frames,
            PossessionConfig(min_observation_confidence=0.1, deadball_confirm_frames=1),
            E02Config(),
        ))
        labels, _ = decode([result.emission for result in results], config=HMMConfig())
        self.assertIn("D", labels)
        self.assertEqual(possession_spells(labels), [("H", 0, 2), ("H", 5, 7)])

    def test_raw_h_to_a_recovery_changes_decoder_input(self):
        frames = [live_frame(i, "H") for i in range(3)]
        frames += [
            FrameEvidence(3, 1, None, (PlayerEvidence("H", 10.8, 10.0, 1.0, 0), PlayerEvidence("A", 12.5, 10.0, 1.0, 1))),
            FrameEvidence(4, 1, None, (PlayerEvidence("H", 11.1, 10.0, 1.0, 0), PlayerEvidence("A", 12.0, 10.0, 1.0, 1))),
            FrameEvidence(5, 1, None, (PlayerEvidence("H", 11.4, 10.0, 1.0, 0), PlayerEvidence("A", 11.5, 10.0, 1.0, 1))),
        ]
        frames += [live_frame(i, "A") for i in range(6, 9)]
        config = E02Config(top_k=2, quality_reference_players=2, low_player_count=1,
                           gap_min_players_per_team=1, gap_support_frames=2,
                           gap_score_threshold=0.45, gap_score_margin=0.15)
        results = list(iter_infer_e02(frames, PossessionConfig(), config))
        self.assertTrue(any(result.ownership_evidence and result.ownership_evidence.accepted for result in results))
        self.assertTrue(any(result.emission.away > result.emission.home for result in results[3:6]))

    def test_uninformative_half_is_deterministic_and_does_not_carry_prior(self):
        emissions = [fuse_evidence(i, 1) for i in range(3)]
        first, _ = decode(emissions, config=HMMConfig())
        second, _ = decode(emissions, config=HMMConfig())
        self.assertEqual(first, second)
        self.assertEqual(first, ["H", "H", "H"])
        second_half, _ = decode([fuse_evidence(i, 2) for i in range(3)], config=HMMConfig())
        self.assertEqual(second_half, ["H", "H", "H"])

    def test_prespecified_duration_grid_is_reproducible(self):
        values = ((0.98, 0.01, 0.01), (0.01, 0.98, 0.01), (0.01, 0.01, 0.98))
        observations = []
        for h_count, a_count, d_count in ((3, 3, 2), (5, 1, 2), (1, 5, 2)):
            observations.append([values[0]] * h_count + [values[1]] * a_count + [values[2]] * d_count)
        results = []
        for sequence in observations:
            first, score = decode([fuse_evidence(i, 1, home=h, away=a, dead=d) for i, (h, a, d) in enumerate(sequence)], config=HMMConfig())
            second, score_again = decode([fuse_evidence(i, 1, home=h, away=a, dead=d) for i, (h, a, d) in enumerate(sequence)], config=HMMConfig())
            self.assertEqual(first, second)
            self.assertEqual(score, score_again)
            results.append(tuple(first))
        self.assertEqual(len(results), 3)


if __name__ == "__main__":
    unittest.main()
