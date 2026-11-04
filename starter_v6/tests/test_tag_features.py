import unittest

from starter_v6.ingestion import SmartTagEvent
from starter_v6.features import E02Config, iter_frame_features
from starter_v6.inference import _team_evidence, iter_infer_e02
from starter_v6.possession import FrameEvidence, PlayerEvidence, PossessionConfig
from starter_v6.tag_features import TagEvidence, iter_tag_evidence


def event(code, start, end, team=None, tag_type=None):
    tags = {}
    if team is not None:
        tags["Team"] = team
    if tag_type is not None:
        tags["Type"] = tag_type
    if tag_type is not None:
        tags["Half"] = "1st Half"
    return SmartTagEvent(code, start / 25, end / 25, start, end, tags,
                         None if team in (None, "N/A") else ("H" if team == "Barcelona" else "A"), team)


class TagFeatureTests(unittest.TestCase):
    def test_known_unknown_and_na_team_semantics(self):
        rows = list(iter_tag_evidence([
            event("BUILD UP", 0, 1, "Barcelona"),
            event("PROGRESSION", 1, 2, "Atletic Club"),
            event("SET PIECES", 2, 3, "N/A", "Throw-in"),
        ], 4))
        self.assertEqual(rows[0].team_prior, "H")
        self.assertEqual(rows[1].team_prior, "A")
        self.assertIsNone(rows[2].team_prior)
        self.assertTrue(rows[2].restart_context)
        self.assertEqual(rows[3].team_prior, None)
        self.assertEqual(rows[2].source_teams, ("N/A",))
        self.assertEqual(rows[2].restart_types, ("throw-in",))
        self.assertEqual(rows[2].half_values, ("1st Half",))
        self.assertEqual(rows[2].interval, (2, 3))
        self.assertIn("TAG:SET PIECES", rows[2].provenance)

    def test_all_six_restart_types_are_context_only_and_preserved(self):
        restart_types = ("Throw-in", "Corner Kick", "Goal Kick", "Free Kick",
                         "Kick Off (After Goal)", "Kick Off (Start)")
        events = [event("SET PIECES", i, i + 1, "N/A", restart_type)
                  for i, restart_type in enumerate(restart_types)]
        rows = iter_tag_evidence(events, 7)
        self.assertEqual(tuple(row.restart_types[0] for row in rows[:6]),
                         ("throw-in", "corner kick", "goal kick", "free kick",
                          "kick off (after goal)", "kick off (start)"))
        self.assertTrue(all(row.team_prior is None and row.restart_context for row in rows[:6]))
        self.assertTrue(all(row.interval is not None and row.provenance for row in rows[:6]))

    def test_overlap_group_is_stable_and_duplicate_context_is_capped(self):
        first = event("SET PIECES", 0, 3, "Barcelona", "Corner Kick")
        duplicate = event("SET PIECES", 0, 3, "Barcelona", "Corner Kick")
        rows = iter_tag_evidence([first, duplicate], 3)
        self.assertTrue(rows[1].overlap)
        self.assertTrue(rows[1].capped)
        self.assertEqual(rows[1].home_prior, 1.0)
        self.assertEqual(len(rows[1].overlap_group_id.split("|")), 1)

    def test_competing_restart_teams_are_unknown_and_half_is_metadata_only(self):
        rows = iter_tag_evidence([
            event("SET PIECES", 0, 2, "Barcelona", "Corner Kick"),
            event("SET PIECES", 0, 2, "Athletic Club", "Goal Kick"),
        ], 2)
        self.assertTrue(rows[0].team_conflict)
        self.assertIsNone(rows[0].team_prior)
        self.assertEqual(rows[0].home_prior, 0.0)
        self.assertEqual(rows[0].away_prior, 0.0)
        self.assertEqual(rows[0].half_values, ("1st Half",))
        self.assertEqual(len(rows[0].restart_types), 2)

    def test_overlap_is_capped_and_conflict_is_flagged(self):
        rows = list(iter_tag_evidence([
            event("BUILD UP", 0, 3, "Barcelona"),
            event("PROGRESSION", 0, 3, "Barcelona"),
            event("ATTACKING TRANSITION", 1, 2, "Atletic Club"),
        ], 3))
        self.assertLessEqual(rows[1].home_prior, 1.0)
        self.assertTrue(rows[1].team_conflict)

    def test_half_open_interval_edges_and_empty_input(self):
        rows = list(iter_tag_evidence([event("GOALS", 1, 2, "Barcelona")], 3))
        self.assertFalse(rows[0].active)
        self.assertTrue(rows[1].active)
        self.assertFalse(rows[2].active)
        self.assertFalse(list(iter_tag_evidence([], 3))[1].active)

    def test_invalid_intervals_rejected(self):
        with self.assertRaises(ValueError):
            list(iter_tag_evidence([event("BUILD UP", 0, 4, "Barcelona")], 3))

    def test_tag_only_resolves_close_observed_geometry_when_nearest_team_agrees(self):
        frame = FrameEvidence(0, 1, (0.0, 0.0), (
            PlayerEvidence("H", 0.25, 0.0), PlayerEvidence("A", 0.4, 0.0),
        ))
        feature_config = E02Config(top_k=1, quality_reference_players=2, low_player_count=1)
        features = next(iter_frame_features([frame], feature_config))
        possession_config = PossessionConfig(min_observation_confidence=0.15)
        without_tag = _team_evidence(features, possession_config, feature_config)
        with_tag = _team_evidence(
            features, possession_config, feature_config,
            TagEvidence(active=True, team_prior="H", home_prior=1.0),
        )
        self.assertIsNone(without_tag.team)
        self.assertEqual(with_tag.team, "H")

    def test_erroneous_opponent_tag_cannot_override_clear_control(self):
        frame = FrameEvidence(0, 1, (0.0, 0.0), (
            PlayerEvidence("H", 0.2, 0.0), PlayerEvidence("A", 4.0, 0.0),
        ))
        feature_config = E02Config(top_k=1, quality_reference_players=2, low_player_count=1)
        features = next(iter_frame_features([frame], feature_config))
        result = _team_evidence(
            features, PossessionConfig(), feature_config,
            TagEvidence(active=True, team_prior="A", away_prior=1.0),
        )
        self.assertEqual(result.team, "H")

    def test_conflicting_tag_cannot_resolve_ambiguous_geometry(self):
        frame = FrameEvidence(0, 1, (0.0, 0.0), (
            PlayerEvidence("H", 0.25, 0.0), PlayerEvidence("A", 0.4, 0.0),
        ))
        feature_config = E02Config(top_k=1, quality_reference_players=2, low_player_count=1)
        features = next(iter_frame_features([frame], feature_config))
        result = _team_evidence(
            features, PossessionConfig(), feature_config,
            TagEvidence(active=True, team_conflict=True, home_prior=0.0, away_prior=0.0),
        )
        self.assertIsNone(result.team)

    def test_restart_and_goal_context_alone_do_not_force_dead_ball(self):
        frame = FrameEvidence(0, 1, None, (), restart_context=True)
        result = next(iter_infer_e02(
            [frame], PossessionConfig(), E02Config(),
            tag_evidence=[TagEvidence(active=True, restart_context=True, goal_context=True)],
        ))
        self.assertNotEqual(result.inference.label, "D")
        self.assertFalse(result.inference.dead_ball_evidence.confirmed)


if __name__ == "__main__":
    unittest.main()
