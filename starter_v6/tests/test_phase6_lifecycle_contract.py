"""Phase 6 Stage 1 contracts using invented tracking and tag records only."""

import unittest

from starter_v6.inference import iter_infer_e02
from starter_v6.features import E02Config
from starter_v6.ingestion import SmartTagEvent
from starter_v6.pipeline import RuntimeRestartActionDetector, restart_type_frames
from starter_v6.possession import FrameEvidence, PlayerEvidence, PossessionConfig


def restart_event(kind, start=0, end=10, code="SET PIECES"):
    return SmartTagEvent(code, start / 25.0, end / 25.0, start, end,
                         {"Type": kind, "Team": "N/A"}, None, "N/A")


def frame(index, x=20.0, speed=0.1, *, kind=(), context=True, half=1, action=None):
    ball = None if x is None else (x, 20.0)
    players = () if x is None else tuple(
        PlayerEvidence(team, x + offset, 20.0, 0.2, slot)
        for slot, (team, offset) in enumerate(
            [("H", 0.2), ("A", 8.0)] +
            [("H", 6.0 + slot) for slot in range(3)] +
            [("A", 12.0 + slot) for slot in range(3)],
        )
    )
    return FrameEvidence(index, half, ball, players, speed, context, action,
                         restart_types=tuple(kind))


class Phase6LifecycleContracts(unittest.TestCase):
    def infer(self, values):
        return list(iter_infer_e02(
            values, PossessionConfig(), E02Config(stage1_lifecycle_enabled=True),
        ))

    def test_restart_type_timeline_keeps_all_types_and_ignores_non_restart_tags(self):
        events = [
            restart_event("Throw-in", 1, 4),
            restart_event("Corner Kick", 3, 6),
            restart_event("Free Kick", 2, 5, code="BUILD UP"),
        ]
        timeline = restart_type_frames(events, 8)
        self.assertEqual(timeline[0], ())
        self.assertEqual(timeline[1], ("throw-in",))
        self.assertEqual(timeline[2], ("throw-in",))
        self.assertEqual(timeline[3], ("corner kick", "throw-in"))
        self.assertEqual(timeline[5], ("corner kick",))
        self.assertEqual(timeline[6:], [(), ()])

    def test_duplicate_context_collapses_and_conflicting_types_do_not_execute(self):
        duplicate = restart_type_frames([
            restart_event("Corner Kick", 0, 4),
            restart_event("Corner Kick", 0, 4),
        ], 4)
        self.assertEqual(duplicate, [("corner kick",)] * 4)
        conflict = restart_type_frames([
            restart_event("Corner Kick", 0, 3),
            restart_event("Goal Kick", 0, 3),
        ], 3)
        detector = RuntimeRestartActionDetector()
        values = [frame(i, 20.0 + 0.3 * i, 2.0, kind=conflict[i])
                  for i in range(3)]
        self.assertTrue(all(item.restart_action is None
                            for item in (detector.observe(value) for value in values)))

    def test_five_kick_restarts_require_stationary_setup_and_clear_motion(self):
        for kind in ("corner kick", "goal kick", "free kick",
                     "kick off (start)", "kick off (after goal)"):
            with self.subTest(kind=kind):
                detector = RuntimeRestartActionDetector()
                values = [frame(0, 20.0, 0.1, kind=(kind,)),
                          frame(1, 20.0, 0.1, kind=(kind,)),
                          frame(2, 20.3, 2.0, kind=(kind,))]
                output = [detector.observe(item) for item in values]
                self.assertIsNone(output[0].restart_action)
                self.assertIsNone(output[1].restart_action)
                self.assertEqual(output[2].restart_action, "restart_delivery")

                no_setup = RuntimeRestartActionDetector()
                output = [no_setup.observe(item) for item in (
                    frame(0, 20.0, 2.0, kind=(kind,)),
                    frame(1, 20.3, 2.0, kind=(kind,)),
                )]
                self.assertTrue(all(item.restart_action is None for item in output))

                implausible = RuntimeRestartActionDetector()
                output = [implausible.observe(item) for item in (
                    frame(0, 20.0, 0.1, kind=(kind,)),
                    frame(1, 20.0, 0.1, kind=(kind,)),
                    frame(2, 35.0, 20.0, kind=(kind,)),
                )]
                self.assertTrue(all(item.restart_action is None for item in output))

    def test_throw_in_becomes_live_only_on_observed_field_entry(self):
        detector = RuntimeRestartActionDetector()
        values = [
            frame(0, -1.2, 0.1, kind=("throw-in",)),
            frame(1, None, None, kind=("throw-in",)),
            frame(2, -0.2, 2.0, kind=("throw-in",)),
            frame(3, 0.1, 2.0, kind=("throw-in",)),
        ]
        output = [detector.observe(item) for item in values]
        self.assertIsNone(output[2].restart_action)
        self.assertEqual(output[3].restart_action, "restart_throw_in_entry")

    def test_throw_in_missing_or_in_field_reappearance_alone_stays_unknown(self):
        for values in (
            [frame(0, None, None, kind=("throw-in",)),
             frame(1, 20.0, 2.0, kind=("throw-in",))],
            [frame(0, 20.0, 0.1, kind=("throw-in",)),
             frame(1, 20.3, 2.0, kind=("throw-in",))],
        ):
            with self.subTest(values=values):
                detector = RuntimeRestartActionDetector()
                output = [detector.observe(item) for item in values]
                self.assertTrue(all(item.restart_action is None for item in output))

    def test_stationary_free_kick_context_does_not_assert_referee_award(self):
        values = [frame(i, 20.0, 0.1, kind=("free kick",)) for i in range(6)]
        results = self.infer(values)
        self.assertTrue(all(item.inference.label != "D" for item in results))
        self.assertTrue(all(not item.inference.dead_ball_evidence.confirmed
                            for item in results))
        self.assertTrue(all(item.play_state_hypothesis.status == "RESTART_PREPARATION"
                            for item in results))

    def test_confirmed_dead_persists_until_restart_or_observed_live_recovery(self):
        stop = [frame(0, -1.2, 1.0, context=False),
                frame(1, -1.2, 1.0, context=False)]
        held = [frame(i, 20.0, 0.1, kind=("corner kick",)) for i in range(2, 4)]
        recovered = [frame(i, 20.0 + 0.3 * (i - 4), 2.0,
                           kind=("corner kick",),
                           action="restart_delivery" if i == 4 else None)
                     for i in range(4, 8)]
        results = self.infer(stop + held + recovered)
        self.assertEqual(results[1].play_state_hypothesis.status, "STOP_ONSET")
        self.assertEqual(results[2].play_state_hypothesis.status, "DEAD_PERSISTENCE")
        self.assertTrue(all(item.inference.label == "D" for item in results[1:4]))
        self.assertEqual(results[4].play_state_hypothesis.status,
                         "LEGAL_RESTART_EXECUTION")
        self.assertNotEqual(results[4].inference.label, "D")

        boundary = [frame(0, -1.2, 1.0, context=False),
                    frame(1, -1.2, 1.0, context=False)]
        moving_control = [frame(i, 20.0 + 0.3 * (i - 2), 2.0,
                                context=False) for i in range(2, 6)]
        results = self.infer(boundary + moving_control)
        self.assertEqual(results[3].play_state_hypothesis.status, "DEAD_PERSISTENCE")
        self.assertEqual(results[5].play_state_hypothesis.status, "LIVE_RECOVERED")
        self.assertEqual(results[5].inference.label, "H")

    def test_single_noisy_outside_observation_is_only_a_stop_candidate(self):
        values = [frame(0, -1.2, 1.0, context=False),
                  frame(1, None, None, context=False)]
        results = self.infer(values)
        self.assertEqual(results[0].play_state_hypothesis.status, "STOP_ONSET")
        self.assertEqual(results[0].play_state_hypothesis.confidence, 0.0)
        self.assertFalse(results[0].inference.dead_ball_evidence.hard_evidence)
        self.assertFalse(any(item.inference.label == "D" for item in results))

    def test_unknown_onset_missingness_and_half_boundary_do_not_leak_dead_state(self):
        values = [frame(0, -1.2, 1.0, context=False),
                  frame(1, -1.2, 1.0, context=False),
                  frame(2, None, None, context=False),
                  frame(3, 20.0, 2.0, context=False, half=2)]
        results = self.infer(values)
        self.assertEqual(results[2].play_state_hypothesis.status, "DEAD_PERSISTENCE")
        self.assertEqual(results[3].play_state_hypothesis.status, "UNKNOWN")
        self.assertNotEqual(results[3].inference.label, "D")


if __name__ == "__main__":
    unittest.main()
