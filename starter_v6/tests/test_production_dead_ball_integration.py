import unittest

from starter_v6.features import E02Config
from starter_v6.hmm import HMMConfig, decode
from starter_v6.inference import iter_infer_e02
from starter_v6.possession import (
    FrameEvidence,
    PlayerEvidence,
    PossessionConfig,
    possession_spells,
)


def live_frame(index, half=1, team="H"):
    other = "A" if team == "H" else "H"
    return FrameEvidence(
        index, half, (10.0, 10.0),
        (PlayerEvidence(team, 10.2, 10.0, 1.0),
         PlayerEvidence(other, 18.0, 10.0, 1.0)),
        1.0,
    )


def production(frames, possession=None):
    return list(iter_infer_e02(
        frames,
        possession or PossessionConfig(min_observation_confidence=0.1),
        E02Config(),
    ))


class ProductionDeadBallIntegrationTests(unittest.TestCase):
    def test_live_and_missing_ball_do_not_create_dead_evidence(self):
        frames = [live_frame(i) for i in range(3)]
        frames += [FrameEvidence(i, 1, None, ()) for i in range(3, 6)]
        frames += [live_frame(i) for i in range(6, 9)]
        results = production(frames)
        self.assertTrue(all(not result.inference.dead_ball_evidence.cues for result in results))
        labels, _ = decode([result.emission for result in results], config=HMMConfig())
        self.assertNotIn("D", labels)

    def test_near_boundary_disappearance_reaches_production_but_is_not_confirmed(self):
        config = PossessionConfig(
            min_observation_confidence=0.1,
            boundary_disappearance_pre_frames=1,
            boundary_disappearance_min_missing_frames=3,
        )
        frames = [FrameEvidence(0, 1, (0.25, 20.0), (), 1.0)]
        frames += [FrameEvidence(i, 1, None, ()) for i in range(1, 4)]
        results = production(frames, config)
        candidate = results[-1].inference.dead_ball_evidence
        self.assertEqual(candidate.cues, ("near_boundary_disappearance",))
        self.assertEqual(candidate.event_context, "boundary_disappearance")
        self.assertFalse(candidate.confirmed)
        self.assertFalse(candidate.confirmable)
        labels, _ = decode([result.emission for result in results], config=HMMConfig())
        self.assertNotIn("D", labels)

    def test_supported_boundary_stoppage_reaches_emission_and_decoder(self):
        frames = [live_frame(i) for i in range(3)]
        frames += [FrameEvidence(i, 1, (-1.0, 20.0), (), 0.1) for i in range(3, 5)]
        frames += [live_frame(i) for i in range(5, 8)]
        results = production(frames)
        self.assertTrue(all(result.inference.dead_ball_evidence.confirmed for result in results[3:5]))
        self.assertTrue(all(result.emission.dead > result.emission.home for result in results[3:5]))
        labels, _ = decode([result.emission for result in results], config=HMMConfig())
        self.assertEqual(possession_spells(labels), [("H", 0, 2), ("H", 5, 7)])

    def test_stateful_context_resets_at_half_boundary(self):
        config = PossessionConfig(
            min_observation_confidence=0.1,
            boundary_disappearance_pre_frames=1,
            boundary_disappearance_min_missing_frames=2,
        )
        frames = [FrameEvidence(0, 1, (0.25, 20.0), (), 1.0)]
        frames += [FrameEvidence(1, 1, None, ())]
        frames += [FrameEvidence(2, 2, None, ()), FrameEvidence(3, 2, None, ())]
        results = production(frames, config)
        self.assertEqual(results[1].inference.dead_ball_evidence.cues, ())
        self.assertEqual(results[2].inference.dead_ball_evidence.cues, ())
        self.assertEqual(results[3].inference.dead_ball_evidence.cues, ())


if __name__ == "__main__":
    unittest.main()
