"""Synthetic E02 temporal-state and gap-transition tests."""

import unittest

from starter_v4.features import E02Config
from starter_v4.inference import iter_infer_e02
from starter_v4.possession import FrameEvidence, PlayerEvidence, PossessionConfig, possession_spells


def frame(index, team="H", half=1, ball=True, home_x=None, away_x=None):
    if home_x is None:
        home_x = 0.5 if team == "H" else 4.0
    if away_x is None:
        away_x = 4.0 if team == "H" else 0.5
    players = (
        PlayerEvidence("H", home_x, 0.0, 1.0, 0),
        PlayerEvidence("A", away_x, 0.0, 1.0, 1),
    )
    return FrameEvidence(index, half, (0.0, 0.0) if ball else None, players)


def config(**overrides):
    values = {
        "top_k": 2,
        "quality_reference_players": 2,
        "low_player_count": 1,
        "gap_min_players_per_team": 1,
        "gap_support_frames": 2,
        "gap_score_threshold": 0.45,
        "gap_score_margin": 0.15,
    }
    values.update(overrides)
    feature = E02Config(**values)
    return feature, PossessionConfig()


def labels_for(frames, feature_config=None, possession_config=None):
    feature_config = feature_config or config()[0]
    possession_config = possession_config or PossessionConfig()
    return list(iter_infer_e02(frames, possession_config, feature_config))


class GapInferenceTests(unittest.TestCase):
    def test_h_missing_gap_h_is_one_h_spell_and_missing_is_not_d(self):
        frames = [frame(i) for i in range(3)]
        frames += [frame(i, ball=False) for i in range(3, 8)]
        frames += [frame(i) for i in range(8, 11)]
        results = labels_for(frames)
        labels = [result.inference.label for result in results]
        self.assertEqual(labels, ["X", "X"] + ["H"] * 9)
        self.assertEqual(possession_spells(labels), [("H", 2, 10)])
        self.assertTrue(all(result.inference.label != "D" for result in results[3:8]))

    def test_stationary_near_anchor_a_does_not_create_gap_turnover(self):
        frames = [frame(i) for i in range(3)]
        frames += [frame(i, ball=False, home_x=0.5, away_x=0.8) for i in range(3, 6)]
        frames += [frame(i, team="A") for i in range(6, 9)]
        results = labels_for(frames)
        labels = [result.inference.label for result in results]
        self.assertEqual(labels[3:6], ["H", "H", "H"])
        self.assertEqual(labels[-1], "A")
        self.assertEqual(results[4].gap_decision, "none")

    def test_low_quality_gap_motion_cannot_backfill_a_turnover(self):
        feature_config, _ = config(quality_reference_players=10, gap_min_quality_weight=0.6)
        frames = [frame(i) for i in range(3)]
        frames += [
            frame(3, ball=False, home_x=0.8, away_x=2.5),
            frame(4, ball=False, home_x=1.1, away_x=2.0),
            frame(5, ball=False, home_x=1.4, away_x=1.5),
        ]
        frames += [frame(i, team="A", home_x=4.0, away_x=0.5) for i in range(6, 9)]
        labels = [
            item.inference.label
            for item in labels_for(frames, feature_config, PossessionConfig(min_observation_confidence=0.1))
        ]
        self.assertEqual(labels[3:6], ["H", "H", "H"])
        self.assertEqual(labels[-1], "A")

    def test_independent_a_motion_during_gap_and_recovery_confirm_gap_switch(self):
        frames = [frame(i) for i in range(3)]
        frames += [
            frame(3, ball=False, home_x=0.8, away_x=2.5),
            frame(4, ball=False, home_x=1.1, away_x=2.0),
            frame(5, ball=False, home_x=1.4, away_x=1.5),
        ]
        frames += [frame(i, team="A", home_x=4.0, away_x=0.5) for i in range(6, 9)]

        results = labels_for(frames)
        labels = [result.inference.label for result in results]

        self.assertEqual(labels[:3], ["X", "X", "H"])
        # The first ambiguous missing frame retains H; the following two supported frames are
        # backfilled to A after post-gap confirmation.
        self.assertEqual(labels[3:6], ["H", "A", "A"])
        self.assertEqual(labels[6:], ["A", "A", "A"])
        self.assertTrue(all(not result.features.quality.ball_observed for result in results[3:6]))
        self.assertEqual(results[3].gap_decision, "accepted")

    def test_long_gap_expires_to_x_and_does_not_carry_owner_forever(self):
        feature_config, _ = config(gap_max_frames=2)
        possession_config = PossessionConfig(max_missing_frames=2)
        frames = [frame(i) for i in range(3)]
        frames += [frame(i, ball=False) for i in range(3, 8)]
        frames += [frame(i, team="A") for i in range(8, 11)]
        results = labels_for(frames, feature_config, possession_config)
        labels = [result.inference.label for result in results]
        self.assertEqual(labels[5:8], ["X", "X", "X"])
        self.assertEqual(labels[-1], "A")
        self.assertFalse(any(result.gap_decision == "accepted" for result in results))

    def test_unconfirmed_recovery_then_a_new_gap_preserves_frame_order(self):
        frames = [frame(i) for i in range(3)]
        frames += [frame(i, ball=False) for i in range(3, 5)]
        frames += [frame(i, team="A") for i in range(5, 7)]
        frames += [frame(i, ball=False) for i in range(7, 9)]
        frames += [frame(i) for i in range(9, 12)]
        results = labels_for(frames)
        self.assertEqual([result.inference.frame for result in results], list(range(12)))

    def test_long_gap_emits_incrementally_instead_of_buffering_the_sequence(self):
        feature_config, _ = config(gap_max_frames=2)
        possession_config = PossessionConfig(max_missing_frames=2)
        consumed = [0]

        def source():
            for index in range(3):
                consumed[0] += 1
                yield frame(index)
            for index in range(3, 1003):
                consumed[0] += 1
                yield frame(index, ball=False)

        results = iter_infer_e02(source(), possession_config, feature_config)
        first = [next(results) for _ in range(4)]
        self.assertEqual([item.inference.frame for item in first], [0, 1, 2, 3])
        self.assertLess(consumed[0], 100)

    def test_dead_ball_still_splits_same_team_into_two_spells(self):
        frames = [frame(i) for i in range(3)]
        frames.append(FrameEvidence(3, 1, (-1.0, 0.0), ()))
        frames += [frame(i) for i in range(4, 7)]
        labels = [result.inference.label for result in labels_for(frames)]
        self.assertEqual(labels[3], "D")
        self.assertEqual(len(possession_spells(labels)), 2)
        self.assertEqual([spell[0] for spell in possession_spells(labels)], ["H", "H"])

    def test_half_boundary_resets_label_carry(self):
        frames = [frame(i) for i in range(3)]
        frames += [frame(3, half=2, ball=False), frame(4, half=2, ball=False)]
        labels = [result.inference.label for result in labels_for(frames)]
        self.assertEqual(labels[:3], ["X", "X", "H"])
        self.assertEqual(labels[3:], ["X", "X"])


if __name__ == "__main__":
    unittest.main()
