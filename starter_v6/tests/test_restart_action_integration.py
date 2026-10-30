import unittest

from starter_v6.features import E02Config
from starter_v6.hmm import HMMConfig, decode
from starter_v6.ingestion import ATDFrame, ATDMetadata, Observation, TrackSlot
from starter_v6.inference import iter_infer_e02
from starter_v6.pipeline import iter_frame_evidence
from starter_v6.possession import PossessionConfig, possession_spells


def observation(x_m, y_m=10.0, speed=0.0, valid=True, speed_valid=True):
    return Observation(
        x_m / 105.3 if valid else float("nan"),
        y_m / 68.0 if valid else float("nan"),
        speed if speed_valid else float("nan"),
        x_m if valid else float("nan"),
        y_m if valid else float("nan"),
        valid,
        speed_valid,
    )


METADATA = ATDMetadata(
    team_ids=("home", "away"),
    team_names=("Barcelona", "Athletic Club"),
    slots=(TrackSlot(0, "h", "Home", "H"), TrackSlot(1, "a", "Away", "A")),
    pitch_length_m=105.3,
    pitch_width_m=68.0,
)


def atd_frame(index, ball_x=None, ball_speed=0.0, half=1, player_x=10.2):
    ball = observation(10.0 if ball_x is None else ball_x, speed=ball_speed,
                       valid=ball_x is not None, speed_valid=ball_x is not None)
    players = (observation(player_x), observation(18.0))
    return ATDFrame(index + 1, index, players, ball)


def runtime_frames(raw_frames, restart_context_frames, half_by_frame=None):
    count = len(raw_frames)
    contexts = bytearray(1 if index in restart_context_frames else 0 for index in range(count))
    halves = bytearray(half_by_frame or [1] * count)
    return list(iter_frame_evidence(raw_frames, METADATA, halves, contexts))


def infer(frames):
    return list(iter_infer_e02(
        frames,
        PossessionConfig(min_observation_confidence=0.1),
        E02Config(top_k=2, quality_reference_players=2, low_player_count=1),
    ))


class RuntimeRestartActionTests(unittest.TestCase):
    def test_free_kick_delivery_ends_dead_ball_in_production_decoder(self):
        raw = [atd_frame(0, 10.0, 0.1), atd_frame(1, 10.0, 0.1),
               atd_frame(2, 10.5, 2.0), atd_frame(3, 11.0, 2.0),
               atd_frame(4, 11.5, 2.0)]
        frames = runtime_frames(raw, range(5))
        results = infer(frames)
        self.assertEqual(frames[2].restart_action, "restart_delivery")
        self.assertFalse(results[2].inference.dead_ball_evidence.cues)
        labels, _ = decode([result.emission for result in results], config=HMMConfig())
        self.assertNotEqual(labels[-1], "D")

    def test_throw_in_missing_initially_requires_credible_reappearance(self):
        raw = [atd_frame(0, None), atd_frame(1, None),
               atd_frame(2, 10.5, 2.0, player_x=10.6),
               atd_frame(3, 11.0, 2.0, player_x=10.8)]
        frames = runtime_frames(raw, range(4))
        self.assertEqual(frames[0].restart_action, None)
        self.assertEqual(frames[2].restart_action, "restart_reappearance")

    def test_corner_stationary_setup_then_delivery_emits_one_action(self):
        raw = [atd_frame(0, 10.0, 0.1), atd_frame(1, 10.0, 0.1),
               atd_frame(2, 10.5, 2.0), atd_frame(3, 11.0, 2.0),
               atd_frame(4, 11.5, 2.0)]
        frames = runtime_frames(raw, range(5))
        self.assertEqual([frame.restart_action for frame in frames],
                         [None, None, "restart_delivery", None, None])

    def test_long_set_piece_context_stays_live_after_single_delivery(self):
        raw = [atd_frame(0, 10.0, 0.1), atd_frame(1, 10.0, 0.1)]
        raw += [atd_frame(index, 10.0 + 0.5 * (index - 1), 2.0)
                for index in range(2, 7)]
        frames = runtime_frames(raw, range(7))
        self.assertEqual(frames[2].restart_action, "restart_delivery")
        self.assertTrue(all(frame.restart_action is None for frame in frames[3:]))
        results = infer(frames)
        self.assertTrue(all(not result.inference.dead_ball_evidence.cues for result in results[2:]))

    def test_goalkeeper_like_live_motion_without_context_is_not_restart(self):
        raw = [atd_frame(0, 5.0, 0.2, player_x=5.2),
               atd_frame(1, 5.5, 2.0, player_x=5.7),
               atd_frame(2, 6.0, 2.0, player_x=6.2)]
        frames = runtime_frames(raw, ())
        self.assertTrue(all(frame.restart_action is None for frame in frames))

    def test_kickoff_context_and_ordinary_live_pass_do_not_fabricate_action(self):
        raw = [atd_frame(0, 10.0, 1.5), atd_frame(1, 10.5, 2.0),
               atd_frame(2, 11.0, 2.0)]
        frames = runtime_frames(raw, range(3))
        self.assertTrue(all(frame.restart_action is None for frame in frames))

    def test_kickoff_delivery_can_resume_away_live_emission(self):
        raw = [atd_frame(0, 10.0, 0.1), atd_frame(1, 10.0, 0.1),
               atd_frame(2, 10.5, 2.0, player_x=18.0),
               atd_frame(3, 11.0, 2.0, player_x=18.0)]
        frames = runtime_frames(raw, range(4))
        results = infer(frames)
        self.assertEqual(frames[2].restart_action, "restart_delivery")
        self.assertGreater(results[2].emission.away, results[2].emission.dead)

    def test_stationary_context_without_delivery_keeps_restart_uncertain(self):
        raw = [atd_frame(0, 10.0, 0.1), atd_frame(1, 10.0, 0.1),
               atd_frame(2, 10.0, 0.1)]
        frames = runtime_frames(raw, range(3))
        self.assertTrue(all(frame.restart_action is None for frame in frames))

    def test_jump_or_unknown_motion_preserves_uncertainty(self):
        raw = [atd_frame(0, 10.0, 0.1), atd_frame(1, 40.0, None),
               atd_frame(2, None, None)]
        frames = runtime_frames(raw, range(3))
        self.assertTrue(all(frame.restart_action is None for frame in frames))

    def test_half_boundary_resets_restart_state(self):
        raw = [atd_frame(0, 10.0, 0.1, half=1),
               atd_frame(1, None, None, half=1),
               atd_frame(2, 10.5, 2.0, half=2),
               atd_frame(3, 11.0, 2.0, half=2)]
        contexts = runtime_frames(raw, range(4), half_by_frame=[1, 1, 2, 2])
        self.assertTrue(all(frame.restart_action is None for frame in contexts[2:]))


if __name__ == "__main__":
    unittest.main()
