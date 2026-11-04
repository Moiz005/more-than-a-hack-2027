"""Phase 5 synthetic contracts for ownership modes and controlled transfers."""

import json
import tempfile
import unittest
from pathlib import Path

from starter_v6.config import load_e04_config
from starter_v6.features import E02Config
from starter_v6.inference import iter_infer_e02
from starter_v6.possession import FrameEvidence, PlayerEvidence, PossessionConfig


def frame(index, owner="H", ball_x=20.0, half=1, home_x=None, away_x=None,
          home_id=1, away_id=2):
    if home_x is None:
        home_x = ball_x + 0.4 if owner == "H" else ball_x + 5.0
    if away_x is None:
        away_x = ball_x + 0.4 if owner == "A" else ball_x + 5.0
    return FrameEvidence(
        index, half, (ball_x, 30.0),
        (PlayerEvidence("H", home_x, 30.0, 1.0, home_id),
         PlayerEvidence("A", away_x, 30.0, 1.0, away_id)),
    )


def run(frames, *, atd=False, acquire_frames=3, min_confidence=0.6,
        tags=None, extra_features=None):
    values = dict(top_k=2, quality_reference_players=2, low_player_count=1,
                  atd_signal_fusion_enabled=atd)
    values.update(extra_features or {})
    return list(iter_infer_e02(
        frames,
        PossessionConfig(acquire_frames=acquire_frames,
                         min_observation_confidence=min_confidence),
        E02Config(**values),
        tag_evidence=tags,
    ))


class Phase5ModeTests(unittest.TestCase):
    def load_mode(self, mode, **overrides):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "mode.json"
            payload = {"ownership_mode": mode}
            payload.update(overrides)
            path.write_text(json.dumps(payload))
            return load_e04_config(path)

    def test_named_modes_expand_to_expected_control_and_context_flags(self):
        exact = self.load_mode("v3_exact")
        control = self.load_mode("atd_control")
        combined = self.load_mode("atd_control_plus_context")
        self.assertFalse(exact["features"].atd_signal_fusion_enabled)
        self.assertTrue(exact["tag_features"]["enabled"])
        self.assertTrue(control["features"].atd_signal_fusion_enabled)
        self.assertFalse(control["tag_features"]["enabled"])
        self.assertTrue(combined["features"].atd_signal_fusion_enabled)
        self.assertTrue(combined["tag_features"]["enabled"])

    def test_named_mode_rejects_unknown_value(self):
        with self.assertRaises(ValueError):
            self.load_mode("homography_magic")

    def test_flight_policy_config_rejects_boolean_numeric_values(self):
        with self.assertRaises(ValueError):
            E02Config(ownership_flight_speed_mps=True)
        with self.assertRaises(ValueError):
            E02Config(flight_owner_carry_confidence=True)

    def test_named_mode_overrides_conflicting_legacy_switches_explicitly(self):
        cfg = self.load_mode(
            "atd_control", features={"atd_signal_fusion_enabled": False},
            tag_features={"enabled": True},
        )
        self.assertTrue(cfg["features"].atd_signal_fusion_enabled)
        self.assertFalse(cfg["tag_features"]["enabled"])

    def test_v3_exact_mode_is_neutral_to_custom_v3_default_inference(self):
        cfg = self.load_mode("v3_exact")
        frames = [frame(i) for i in range(3)]
        frames += [frame(3, owner="A"), frame(4, owner="H"), frame(5, owner="H")]
        baseline = list(iter_infer_e02(frames, PossessionConfig(), E02Config()))
        mode = list(iter_infer_e02(
            frames, PossessionConfig(), cfg["features"],
        ))
        self.assertEqual(
            [(item.inference.label, item.emission) for item in baseline],
            [(item.inference.label, item.emission) for item in mode],
        )

    def test_control_hypothesis_records_unknown_state_provenance_and_quality(self):
        results = run([frame(0), FrameEvidence(1, 1, None, ())])
        controlled, missing = results
        self.assertEqual(controlled.control_hypothesis.status, "H")
        self.assertIn("geometry", controlled.control_hypothesis.evidence_groups)
        self.assertEqual(controlled.control_hypothesis.quality_flags,
                         controlled.features.quality.flags)
        self.assertEqual(missing.control_hypothesis.status, "UNKNOWN")
        self.assertIsNone(missing.control_hypothesis.team)
        self.assertIn("ball_missing", missing.control_hypothesis.quality_flags)
        self.assertNotIn(missing.inference.label, {"UNKNOWN"})

    def test_confirmed_dead_frames_always_have_unknown_control_hypothesis(self):
        frames = [frame(i) for i in range(3)]
        frames += [FrameEvidence(i, 1, (50.0, 34.0), (), 0.1, True)
                   for i in range(3, 7)]
        results = run(frames)
        dead = [item for item in results if item.inference.label == "D"]
        self.assertTrue(dead)
        self.assertTrue(all(item.control_hypothesis.status == "UNKNOWN" for item in dead))
        self.assertTrue(all(item.control_hypothesis.team is None for item in dead))

    def test_controlled_transfers_are_temporally_supported_in_both_directions(self):
        for source, target in (("H", "A"), ("A", "H")):
            frames = [frame(i, owner=source) for i in range(3)]
            frames += [frame(i, owner=target) for i in range(3, 6)]
            results = run(frames)
            transition = results[-1].control_transition
            repeat = run(frames)
            self.assertEqual(
                [(item.inference.label, item.emission, item.control_transition)
                 for item in results],
                [(item.inference.label, item.emission, item.control_transition)
                 for item in repeat],
            )
            self.assertEqual(transition.from_team, source)
            self.assertEqual(transition.to_team, target)
            self.assertTrue(transition.accepted)
            self.assertEqual(transition.support_frames, 3)
            self.assertEqual(transition.start_frame, 3)
            self.assertEqual(transition.end_frame, 5)
            self.assertEqual(results[3].inference.label, source)
            self.assertEqual(results[-1].inference.label, target)

    def test_one_frame_opponent_nearest_flip_does_not_transfer_control(self):
        for blip_frames in (1, 2):
            with self.subTest(blip_frames=blip_frames):
                frames = [frame(i) for i in range(3)]
                frames += [frame(i, owner="A") for i in range(3, 3 + blip_frames)]
                frames += [frame(i, owner="H") for i in range(3 + blip_frames, 7)]
                results = run(frames)
                self.assertTrue(all(item.inference.label != "A" for item in results))
                self.assertFalse(any(item.control_transition is not None
                                     and item.control_transition.to_team == "A"
                                     for item in results))
                self.assertTrue(all(item.inference.label == "H" for item in results[2:]))

    def test_low_coverage_and_contest_remain_unknown_with_quality_flags(self):
        low_coverage = run(
            [frame(0)],
            extra_features={"quality_reference_players": 10, "low_player_count": 6},
        )[0].control_hypothesis
        contested = run([frame(0, home_x=20.4, away_x=20.4)])[0].control_hypothesis
        self.assertEqual(low_coverage.status, "UNKNOWN")
        self.assertIn("low_player_coverage", low_coverage.quality_flags)
        self.assertEqual(contested.status, "UNKNOWN")

    def test_fast_ball_flight_near_opponent_without_control_keeps_current_owner(self):
        frames = [frame(i, owner="H", ball_x=20.0) for i in range(3)]
        frames += [
            frame(3, owner="A", ball_x=20.4, home_x=16.0, away_x=20.6),
            frame(4, owner="A", ball_x=20.8, home_x=16.0, away_x=20.6),
            frame(5, owner="A", ball_x=21.2, home_x=16.0, away_x=20.6),
        ]
        results = run(frames, atd=True)
        self.assertTrue(all(item.atd_signals.ball_motion.observed_speed_mps >= 8.0
                            for item in results[3:]))
        self.assertTrue(all(item.atd_signals.control.candidate_team is None
                            for item in results[3:]))
        self.assertTrue(all(item.inference.label == "H" for item in results[2:]))
        self.assertTrue(all(item.control_hypothesis.status == "UNKNOWN"
                            for item in results[3:]))
        self.assertTrue(all(item.emission.home > item.emission.away
                            for item in results[3:]))

    def test_slot_position_discontinuity_does_not_create_single_frame_transfer(self):
        frames = [frame(i) for i in range(3)]
        frames += [
            frame(3, owner="A", home_x=25.0, away_x=20.4),
            frame(4, owner="H", home_x=20.4, away_x=25.0),
            frame(5, owner="H", home_x=20.4, away_x=25.0),
        ]
        results = run(frames)
        self.assertEqual([item.inference.label for item in results[2:]], ["H"] * 4)

    def test_unknown_or_weak_context_cannot_create_owner_without_control_geometry(self):
        from starter_v6.tag_features import TagEvidence
        tags = [TagEvidence(active=True, restart_context=True) for _ in range(4)]
        frames = [frame(i, home_x=35.0, away_x=35.0) for i in range(4)]
        results = run(frames, tags=tags)
        self.assertTrue(all(item.control_hypothesis.status == "UNKNOWN" for item in results))
        self.assertTrue(all(item.control_hypothesis.confidence < 0.6 for item in results))
        self.assertTrue(all(item.inference.label == "X" for item in results))

    def test_dead_interval_does_not_blind_carry_prior_owner_after_reappearance(self):
        for restarting_team in ("A", "H"):
            with self.subTest(restarting_team=restarting_team):
                frames = [frame(i, owner="H") for i in range(4)]
                frames += [FrameEvidence(i, 1, (50.0, 34.0), (), 0.1, True)
                           for i in range(4, 7)]
                frames += [frame(i, owner=restarting_team,
                                 ball_x=50.0 + (i - 7) * 0.1)
                           for i in range(7, 12)]
                results = run(
                    frames,
                    extra_features={"atd_signal_fusion_enabled": True},
                )
                self.assertTrue(any(item.inference.label == "D" for item in results[4:7]))
                self.assertNotEqual(results[7].inference.label, "H")
                self.assertTrue(all(
                    item.inference.label != "H" for item in results[7:]
                ) if restarting_team == "A" else all(
                    item.inference.label != "D" for item in results[9:]
                ))

    def test_unknown_restart_owner_stays_unknown_after_dead(self):
        from starter_v6.tag_features import TagEvidence
        frames = [frame(i, owner="H") for i in range(4)]
        frames += [FrameEvidence(i, 1, (50.0, 34.0), (), 0.1, True)
                   for i in range(4, 7)]
        frames += [
            FrameEvidence(
                i, 1, (50.0, 34.0),
                (PlayerEvidence("H", 49.5, 34.0, 1.0, 1),
                 PlayerEvidence("A", 50.5, 34.0, 1.0, 2)),
                1.0, False,
                restart_action="restart_delivery" if i == 7 else None,
            )
            for i in range(7, 10)
        ]
        tags = [TagEvidence() for _ in frames]
        for index in range(4, 10):
            tags[index] = TagEvidence(
                active=True, restart_context=True, team_prior=None,
                source_teams=(None,),
            )
        results = run(frames, tags=tags)
        self.assertTrue(all(item.inference.label != "H" for item in results[7:]))
        self.assertTrue(all(item.control_hypothesis.status == "UNKNOWN"
                            for item in results[7:]))


if __name__ == "__main__":
    unittest.main()
