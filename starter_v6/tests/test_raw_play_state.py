import unittest

from starter_v6.possession import (
    FrameEvidence,
    PlayerEvidence,
    PossessionConfig,
    iter_raw_play_state,
    observe_dead_ball,
    observe_team,
)


class RawPlayStateEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.config = PossessionConfig()

    def test_restart_cue_survives_nearby_controller_without_becoming_owner(self):
        frame = FrameEvidence(
            0, 1, (10.0, 10.0),
            (PlayerEvidence("H", 10.1, 10.0, 0.0), PlayerEvidence("A", 18.0, 10.0, 0.0)),
            0.1, True,
        )
        team = observe_team(frame, self.config)
        raw = observe_dead_ball(frame, team, self.config)
        self.assertEqual(team.team, "H")
        self.assertEqual(raw.cues, ("restart_stationary",))
        self.assertEqual(raw.source, ("restart_context",))
        self.assertIn("nearby_team_control", raw.live_counterevidence)
        self.assertEqual(raw.event_context, "restart_context")

    def test_missing_or_unknown_or_stationary_alone_is_not_confirmed_dead(self):
        missing = FrameEvidence(0, 1, None, ())
        unknown = FrameEvidence(1, 1, (20.0, 20.0), (), 0.0)
        for frame in (missing, unknown):
            raw = observe_dead_ball(frame, observe_team(frame, self.config), self.config)
            self.assertFalse(raw.confirmed)
            self.assertFalse(raw.hard_evidence)
        self.assertEqual(observe_dead_ball(missing, observe_team(missing, self.config), self.config).cues, ())

    def test_restart_action_is_live_context_and_not_dead(self):
        frame = FrameEvidence(0, 1, (20.0, 20.0), (), 0.0, True, "live_restart")
        raw = observe_dead_ball(frame, observe_team(frame, self.config), self.config)
        self.assertEqual(raw.cues, ())
        self.assertEqual(raw.event_context, "restart_action")
        self.assertIn("live_restart", raw.validity)

    def test_boundary_jitter_is_a_nonconfirmable_candidate(self):
        frame = FrameEvidence(0, 1, (-0.6, 20.0), (), 0.2)
        raw = observe_dead_ball(frame, observe_team(frame, self.config), self.config)
        self.assertEqual(raw.cues, ("out_of_bounds",))
        self.assertFalse(raw.hard_evidence)
        self.assertFalse(raw.confirmable)
        self.assertIn("boundary_candidate", raw.validity)

    def test_near_boundary_long_missing_gap_is_traceable_but_not_confirmable(self):
        frames = [FrameEvidence(0, 1, (0.25, 20.0), (), 1.0)]
        frames.extend(FrameEvidence(i, 1, None, ()) for i in range(1, 51))
        observations = list(iter_raw_play_state(frames, self.config))
        candidate = observations[-1].dead_ball_evidence
        self.assertEqual(candidate.cues, ("near_boundary_disappearance",))
        self.assertEqual(candidate.event_context, "boundary_disappearance")
        self.assertFalse(candidate.confirmable)
        self.assertIn("long_gap", candidate.validity)

    def test_boundary_context_expires_before_missing_gap(self):
        frames = [FrameEvidence(0, 1, (0.25, 20.0), (), 1.0)]
        frames.extend(FrameEvidence(i, 1, (20.0, 20.0), (), 1.0) for i in range(1, 4))
        frames.extend(FrameEvidence(i, 1, None, ()) for i in range(4, 54))
        observations = list(iter_raw_play_state(frames, PossessionConfig(boundary_disappearance_pre_frames=2)))
        self.assertTrue(all(item.dead_ball_evidence.cues == () for item in observations[4:]))


if __name__ == "__main__":
    unittest.main()
