"""Phase 7 cross-stage contracts using invented evidence only."""

import json
import tempfile
import unittest
from pathlib import Path

from starter_v6.config import load_e04_config
from starter_v6.features import E02Config
from starter_v6.inference import iter_infer_e02
from starter_v6.ingestion import SmartTagEvent
from starter_v6.pipeline import RuntimeRestartActionDetector
from starter_v6.possession import FrameEvidence, PlayerEvidence, PossessionConfig
from starter_v6.tag_features import iter_tag_evidence


def frame(index, ball_x=20.0, speed=2.0, *, owner="H", half=1,
          restart_context=False, restart_types=(), restart_action=None):
    if ball_x is None:
        ball = None
        players = ()
    else:
        ball = (ball_x, 30.0)
        home_x = ball_x + (0.3 if owner == "H" else 5.0)
        away_x = ball_x + (0.3 if owner == "A" else 5.0)
        players = (
            PlayerEvidence("H", home_x, 30.0, 1.0, 1),
            PlayerEvidence("A", away_x, 30.0, 1.0, 2),
        )
    return FrameEvidence(index, half, ball, players, speed, restart_context,
                         restart_action, restart_types=tuple(restart_types))


class Phase7IntegrationTests(unittest.TestCase):
    def load_mode(self, mode):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"integration_mode": mode}))
            return load_e04_config(path)

    def test_integration_modes_define_controlled_independent_combinations(self):
        expected = {
            "exact_v3": (False, False, False),
            "atd_only": (True, False, False),
            "tag_context_only": (False, True, True),
            "atd_plus_tag": (True, True, True),
            "stage1_then_stage2": (True, True, True),
        }
        for mode, flags in expected.items():
            with self.subTest(mode=mode):
                cfg = self.load_mode(mode)
                self.assertEqual(
                    (cfg["features"].atd_signal_fusion_enabled,
                     cfg["features"].stage1_lifecycle_enabled,
                     cfg["features"].stage1_stage2_fusion_enabled),
                    flags,
                )
                self.assertTrue(cfg["tag_features"]["enabled"])

    def test_unsupported_homography_mode_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "integration_mode"):
            self.load_mode("atd_plus_tag_plus_homography")

    def test_stage1_dead_masks_stage2_owner_and_restart_releases_live_unknown(self):
        config = E02Config(
            top_k=2,
            quality_reference_players=2,
            low_player_count=1,
            stage1_lifecycle_enabled=True,
            stage1_stage2_fusion_enabled=True,
        )
        evidence = [
            frame(0, -1.2), frame(1, -1.2),
            frame(2, 20.0, 0.1, restart_context=True,
                  restart_types=("corner kick",)),
            frame(3, 20.0, 0.1, restart_context=True,
                  restart_types=("corner kick",)),
            frame(4, 20.3, 2.0, restart_context=True,
                  restart_types=("corner kick",), restart_action="restart_delivery"),
            frame(5, 20.6, 2.0), frame(6, 20.9, 2.0), frame(7, 21.2, 2.0),
        ]
        results = list(iter_infer_e02(evidence, PossessionConfig(), config))
        dead = results[1:4]
        self.assertTrue(all(item.inference.label == "D" for item in dead))
        self.assertTrue(all(item.emission.home == item.emission.away for item in dead))
        restart = results[4]
        self.assertEqual(restart.play_state_hypothesis.status,
                         "LEGAL_RESTART_EXECUTION")
        self.assertEqual(restart.emission.home, restart.emission.away)
        self.assertGreater(restart.emission.home, restart.emission.dead)
        self.assertEqual(results[7].inference.label, "H")
        transition_frame = next(item for item in results
                                if item.control_transition is not None)
        self.assertEqual(transition_frame.play_state_hypothesis.status,
                         "LIVE_RECOVERED")
        self.assertEqual(transition_frame.control_transition.from_team, "UNKNOWN")

    def test_stage2_mask_flag_requires_stage1_lifecycle(self):
        with self.assertRaisesRegex(ValueError, "requires stage1_lifecycle_enabled"):
            E02Config(stage1_stage2_fusion_enabled=True)

    def test_restart_execution_frame_does_not_count_toward_owner_acquisition(self):
        observations = [
            frame(0, -1.2), frame(1, -1.2),
            frame(2, 20.0, 0.1, restart_context=True,
                  restart_types=("corner kick",)),
            frame(3, 20.0, 0.1, restart_context=True,
                  restart_types=("corner kick",)),
            frame(4, 20.3, 2.0, restart_context=True,
                  restart_types=("corner kick",), restart_action="restart_delivery"),
            frame(5, 20.6, 2.0), frame(6, 20.9, 2.0),
        ]
        results = list(iter_infer_e02(
            observations, PossessionConfig(acquire_frames=1),
            E02Config(top_k=2, quality_reference_players=2, low_player_count=1,
                      stage1_lifecycle_enabled=True,
                      stage1_stage2_fusion_enabled=True),
        ))
        self.assertEqual(results[4].inference.label, "X")
        self.assertEqual(results[4].control_hypothesis.status, "UNKNOWN")
        self.assertEqual(results[5].inference.label, "H")
        self.assertEqual(results[5].play_state_hypothesis.status, "LIVE_RECOVERED")

    def test_recognized_restart_releases_prior_dead_even_with_same_frame_boundary_cue(self):
        observations = [
            frame(0, -1.2, 0.1), frame(1, -1.0, 0.1),
            frame(2, -0.8, 2.0, restart_context=True,
                  restart_types=("corner kick",),
                  restart_action="restart_delivery"),
            frame(3, -0.6, 2.0), frame(4, -0.4, 2.0),
        ]
        results = list(iter_infer_e02(
            observations, PossessionConfig(acquire_frames=1),
            E02Config(top_k=2, quality_reference_players=2, low_player_count=1,
                      stage1_lifecycle_enabled=True,
                      stage1_stage2_fusion_enabled=True),
        ))
        action = results[2]
        self.assertEqual(action.play_state_hypothesis.status,
                         "LEGAL_RESTART_EXECUTION")
        self.assertEqual(action.inference.label, "X")
        self.assertEqual(action.control_hypothesis.status, "UNKNOWN")
        self.assertGreater(action.emission.home, action.emission.dead)
        self.assertEqual(results[3].inference.label, "H")

    def test_exact_v3_mode_matches_baseline_with_legacy_restart_context_and_tag(self):
        cfg = self.load_mode("exact_v3")
        self.assertFalse(cfg["features"].atd_signal_fusion_enabled)
        self.assertFalse(cfg["features"].stage1_lifecycle_enabled)
        self.assertFalse(cfg["features"].stage1_stage2_fusion_enabled)
        event = SmartTagEvent(
            "BUILD UP", 0.0, 2 / 25.0, 0, 2,
            {"Type": "N/A", "Team": "Barcelona"}, None, "Barcelona",
        )
        frames = [
            frame(0, 20.0, 2.0, restart_context=True),
            frame(1, 20.3, 2.0, restart_context=True),
            frame(2, 20.6, 2.0),
        ]
        legacy = list(iter_infer_e02(
            frames, PossessionConfig(), E02Config(),
            tag_evidence=iter_tag_evidence([event], len(frames)),
        ))
        exact = list(iter_infer_e02(
            frames, PossessionConfig(), cfg["features"],
            tag_evidence=iter_tag_evidence([event], len(frames)),
        ))
        self.assertEqual(
            [(item.inference, item.emission, item.control_hypothesis,
              item.play_state_hypothesis, item.integration_decision) for item in legacy],
            [(item.inference, item.emission, item.control_hypothesis,
              item.play_state_hypothesis, item.integration_decision) for item in exact],
        )

    def test_all_six_restart_types_integrate_dead_live_and_owner_reacquisition(self):
        kick_types = (
            "corner kick", "goal kick", "free kick",
            "kick off (start)", "kick off (after goal)",
        )
        for kind in kick_types + ("throw-in",):
            with self.subTest(kind=kind):
                detector = RuntimeRestartActionDetector()
                if kind == "throw-in":
                    observations = [
                        frame(0, -1.2, 0.1, restart_context=True,
                              restart_types=(kind,)),
                        frame(1, -1.2, 0.1, restart_context=True,
                              restart_types=(kind,)),
                        frame(2, -0.2, 2.0, restart_context=True,
                              restart_types=(kind,)),
                        frame(3, 0.1, 2.0, restart_context=True,
                              restart_types=(kind,)),
                    ]
                elif kind == "free kick":
                    observations = [
                        frame(0, -1.2, 0.1, restart_context=True,
                              restart_types=(kind,)),
                        frame(1, -1.2, 0.1, restart_context=True,
                              restart_types=(kind,)),
                        frame(2, 20.0, 0.1, restart_context=True,
                              restart_types=(kind,)),
                        frame(3, 20.0, 0.1, restart_context=True,
                              restart_types=(kind,)),
                        frame(4, 20.3, 2.0, restart_context=True,
                              restart_types=(kind,)),
                    ]
                else:
                    observations = [
                        frame(0, 20.0, 0.1, restart_context=True,
                              restart_types=(kind,)),
                        frame(1, 20.0, 0.1, restart_context=True,
                              restart_types=(kind,)),
                        frame(2, 20.3, 2.0, restart_context=True,
                              restart_types=(kind,)),
                    ]
                first_live_frame = observations[-1].frame + 1
                observations.extend(
                    frame(i, (0.4 + 0.3 * (i - first_live_frame)) if kind == "throw-in"
                          else (20.3 + 0.3 * (i - first_live_frame)), 2.0)
                    for i in range(first_live_frame, first_live_frame + 3)
                )
                adapted = [detector.observe(item) for item in observations]
                actions = [item for item in adapted if item.restart_action]
                self.assertEqual(len(actions), 1)
                if kind == "throw-in":
                    self.assertEqual(actions[0].restart_action,
                                     "restart_throw_in_entry")
                results = list(iter_infer_e02(
                    adapted,
                    PossessionConfig(acquire_frames=1),
                    E02Config(
                        top_k=2, quality_reference_players=2, low_player_count=1,
                        stage1_lifecycle_enabled=True,
                        stage1_stage2_fusion_enabled=True,
                    ),
                ))
                action_index = actions[0].frame
                self.assertEqual(results[action_index].inference.label, "X")
                self.assertEqual(results[action_index].play_state_hypothesis.status,
                                 "LEGAL_RESTART_EXECUTION")
                self.assertEqual(results[action_index].emission.home,
                                 results[action_index].emission.away)
                self.assertEqual(results[-1].inference.label, "H")
                transitions = [item.control_transition for item in results
                               if item.control_transition is not None
                               and item.control_transition.start_frame > action_index]
                self.assertEqual(len(transitions), 1)
                self.assertEqual(transitions[0].from_team, "UNKNOWN")
                transition_frame = next(item for item in results
                                        if item.control_transition is not None
                                        and item.control_transition.start_frame > action_index)
                self.assertEqual(transition_frame.play_state_hypothesis.status,
                                 "LIVE_RECOVERED")
                self.assertEqual(transition_frame.features.frame.frame,
                                 action_index + 1)
                self.assertEqual(transition_frame.control_transition.support_frames,
                                 1)

    def test_duplicated_tag_source_does_not_inflate_atd_control_or_emissions(self):
        event = SmartTagEvent(
            "BUILD UP", 0.0, 3 / 25.0, 0, 3,
            {"Type": "N/A", "Team": "Barcelona"}, None, "Barcelona",
        )
        frames = [frame(i, 20.0 + 0.1 * i, 2.0) for i in range(3)]
        config = E02Config(
            top_k=2, quality_reference_players=2, low_player_count=1,
            atd_signal_fusion_enabled=True,
        )
        once = list(iter_infer_e02(
            frames, PossessionConfig(), config,
            tag_evidence=iter_tag_evidence([event], len(frames)),
        ))
        duplicated = list(iter_infer_e02(
            frames, PossessionConfig(), config,
            tag_evidence=iter_tag_evidence([event, event], len(frames)),
        ))
        self.assertEqual(
            [(item.inference.label, item.emission, item.control_hypothesis)
             for item in once],
            [(item.inference.label, item.emission, item.control_hypothesis)
             for item in duplicated],
        )

    def test_free_kick_context_does_not_reset_live_owner_without_confirmed_dead(self):
        detector = RuntimeRestartActionDetector()
        observations = [
            frame(0, 20.0, 0.1, restart_context=True,
                  restart_types=("free kick",)),
            frame(1, 20.0, 0.1, restart_context=True,
                  restart_types=("free kick",)),
            frame(2, 20.3, 2.0, restart_context=True,
                  restart_types=("free kick",)),
            frame(3, 20.6, 2.0), frame(4, 20.9, 2.0),
        ]
        adapted = [detector.observe(item) for item in observations]
        self.assertEqual(adapted[2].restart_action, "restart_delivery")
        results = list(iter_infer_e02(
            adapted, PossessionConfig(),
            E02Config(top_k=2, quality_reference_players=2,
                      low_player_count=1, stage1_lifecycle_enabled=True,
                      stage1_stage2_fusion_enabled=True),
        ))
        self.assertFalse(any(item.inference.label == "D" for item in results))
        self.assertNotEqual(results[2].play_state_hypothesis.status,
                            "LEGAL_RESTART_EXECUTION")
        self.assertEqual(results[-1].inference.label, "H")

    def test_contradictory_restart_types_do_not_create_restart_action(self):
        detector = RuntimeRestartActionDetector()
        frames = [
            frame(0, 20.0, 0.1, restart_context=True,
                  restart_types=("corner kick", "goal kick")),
            frame(1, 20.0, 0.1, restart_context=True,
                  restart_types=("corner kick", "goal kick")),
            frame(2, 20.3, 2.0, restart_context=True,
                  restart_types=("corner kick", "goal kick")),
        ]
        adapted = [detector.observe(item) for item in frames]
        self.assertTrue(all(item.restart_action is None for item in adapted))
        results = list(iter_infer_e02(
            adapted, PossessionConfig(),
            E02Config(stage1_lifecycle_enabled=True,
                      stage1_stage2_fusion_enabled=True),
        ))
        self.assertEqual(results[1].inference.label, "D")

    def test_missing_ball_keeps_confirmed_dead_without_fabricating_restart(self):
        frames = [frame(0, -1.2), frame(1, -1.2), frame(2, None, None)]
        results = list(iter_infer_e02(
            frames, PossessionConfig(),
            E02Config(stage1_lifecycle_enabled=True,
                      stage1_stage2_fusion_enabled=True),
        ))
        self.assertEqual(results[2].inference.label, "D")
        self.assertEqual(results[2].play_state_hypothesis.status,
                         "DEAD_PERSISTENCE")

    def test_half_change_resets_dead_and_owner_state(self):
        frames = [
            frame(0, -1.2), frame(1, -1.2),
            frame(2, None, None, half=2),
            frame(3, 20.0, 2.0, owner="A", half=2),
            frame(4, 20.3, 2.0, owner="A", half=2),
        ]
        results = list(iter_infer_e02(
            frames, PossessionConfig(acquire_frames=2),
            E02Config(top_k=2, quality_reference_players=2, low_player_count=1,
                      stage1_lifecycle_enabled=True,
                      stage1_stage2_fusion_enabled=True),
        ))
        self.assertEqual(results[2].play_state_hypothesis.status, "UNKNOWN")
        self.assertNotEqual(results[2].inference.label, "D")
        self.assertEqual(results[3].inference.label, "X")
        self.assertEqual(results[4].inference.label, "A")
        self.assertIsNotNone(results[4].control_transition)

    def test_contested_and_missing_live_evidence_stay_non_dead(self):
        contested = FrameEvidence(
            0, 1, (20.0, 30.0),
            (PlayerEvidence("H", 19.5, 30.0, 1.0, 1),
             PlayerEvidence("A", 20.5, 30.0, 1.0, 2)),
            2.0,
        )
        missing = frame(1, None, None)
        results = list(iter_infer_e02(
            [contested, missing], PossessionConfig(),
            E02Config(top_k=2, quality_reference_players=2,
                      low_player_count=1, stage1_lifecycle_enabled=True,
                      stage1_stage2_fusion_enabled=True),
        ))
        self.assertTrue(all(item.inference.label != "D" for item in results))
        self.assertEqual(results[0].control_hypothesis.status, "UNKNOWN")
        self.assertEqual(results[1].play_state_hypothesis.status, "UNKNOWN")
        self.assertEqual(results[0].emission.home, results[0].emission.away)

    def test_legacy_v3_mode_keeps_exact_emissions_and_labels(self):
        cfg = self.load_mode("exact_v3")
        frames = [frame(i, 20.0 + 0.1 * i, 2.0) for i in range(3)]
        frames += [frame(3, -1.2), frame(4, -1.2)]
        legacy = list(iter_infer_e02(frames, PossessionConfig(), E02Config()))
        exact = list(iter_infer_e02(frames, PossessionConfig(), cfg["features"]))
        self.assertEqual(
            [(item.inference.label, item.emission) for item in legacy],
            [(item.inference.label, item.emission) for item in exact],
        )


if __name__ == "__main__":
    unittest.main()
