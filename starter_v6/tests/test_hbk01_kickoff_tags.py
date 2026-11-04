"""Synthetic Smart Tag kickoff-candidate extraction contracts."""

import unittest

from starter_v6.ingestion import SmartTagEvent
from starter_v6.timeline import TacticalTimeline
from starter_v6.kickoff_tags import (
    AMBIGUOUS,
    CANDIDATE_AVAILABLE,
    MISSING_TAG,
    extract_kickoff_candidates,
    extract_opening_kickoff_candidates,
)


def timeline():
    return TacticalTimeline(
        source="tactical",
        fps=25,
        frame_count=300,
        half_by_frame=bytes(300),
        half_ranges=((1, 100, 159), (2, 200, 259)),
    )


def event(code="SET PIECES", start=100, end=110, *, tag_type="Kick Off (Start)",
          half="1st Half", team="N/A", start_s=None, end_s=None,
          start_frame=None, end_frame=None):
    if start_s is None:
        start_s = start / 25.0
    if end_s is None:
        end_s = end / 25.0
    if start_frame is None:
        start_frame = start
    if end_frame is None:
        end_frame = end
    return SmartTagEvent(
        code, start_s, end_s, start_frame, end_frame,
        {"Type": tag_type, "Half": half, "Team": team}, None, team,
    )


class KickoffTagExtractionTests(unittest.TestCase):
    def test_case_and_whitespace_variation_is_normalized_but_original_values_preserved(self):
        inventory = extract_opening_kickoff_candidates([
            event(" set   pieces ", 95, 105, tag_type="  kICK oFF (sTART)  ", half=" 1ST   half ")
        ], timeline=timeline(), search_margin_before_frames=5, search_margin_after_frames=7)

        candidate = inventory.candidates_for_half(1)[0]
        self.assertTrue(candidate.eligible)
        self.assertEqual(candidate.start_frame, 95)
        self.assertEqual(candidate.end_frame, 105)
        self.assertEqual((candidate.search_start_frame, candidate.search_end_frame), (90, 112))
        self.assertEqual(candidate.type_value, "  kICK oFF (sTART)  ")
        self.assertEqual(candidate.half_value, " 1ST   half ")
        self.assertEqual(candidate.team_value, "N/A")
        self.assertEqual(inventory.status_for_half(1), CANDIDATE_AVAILABLE)

    def test_only_opening_kickoff_type_is_eligible_and_other_restart_types_are_preserved(self):
        records = [
            event(tag_type="Kick Off (After Goal)"),
            event(tag_type="Corner Kick"),
            event(code="BUILD UP"),
            event(),
        ]
        inventory = extract_opening_kickoff_candidates(records, timeline=timeline())

        self.assertEqual(len(inventory.records), 4)
        self.assertEqual(len(inventory.candidates_for_half(1)), 1)
        self.assertTrue(inventory.candidates_for_half(1)[0].eligible)
        self.assertTrue(all(not record.eligible for record in inventory.records[:3]))
        self.assertIn("excluded", inventory.records[0].selection_explanation)
        self.assertIn("excluded", inventory.records[1].selection_explanation)
        self.assertIn("code", inventory.records[2].selection_explanation)

    def test_first_half_tag_may_start_before_grade_but_search_window_is_bounded(self):
        inventory = extract_opening_kickoff_candidates([
            event(start=90, end=110, half="1st Half")
        ], timeline=timeline(), search_margin_before_frames=20, search_margin_after_frames=30)

        candidate = inventory.candidates_for_half(1)[0]
        self.assertTrue(candidate.eligible)
        self.assertEqual((candidate.start_frame, candidate.end_frame), (90, 110))
        self.assertEqual((candidate.search_start_frame, candidate.search_end_frame), (70, 140))

    def test_second_half_candidate_is_not_required_to_be_near_graded_start(self):
        inventory = extract_opening_kickoff_candidates([
            event(start=245, end=250, half="2nd Half")
        ], timeline=timeline(), search_margin_before_frames=10, search_margin_after_frames=10)

        self.assertTrue(inventory.candidates_for_half(2)[0].eligible)
        self.assertEqual(inventory.status_for_half(2), CANDIDATE_AVAILABLE)

    def test_duplicates_and_overlapping_candidates_are_ambiguous_not_first_selected(self):
        inventory = extract_opening_kickoff_candidates([
            event(start=105, end=115),
            event(start=105, end=115),
            event(start=110, end=120),
        ], timeline=timeline())

        self.assertEqual(len(inventory.candidates_for_half(1)), 3)
        self.assertEqual(inventory.status_for_half(1), AMBIGUOUS)
        self.assertIsNone(inventory.selected_candidate(1))

    def test_wrong_half_tags_are_retained_with_warning_and_rejected(self):
        inventory = extract_opening_kickoff_candidates([
            event(start=205, end=215, half="1st Half"),
            event(start=205, end=215, half="2nd Half"),
        ], timeline=timeline())

        self.assertEqual(len(inventory.records), 2)
        self.assertFalse(inventory.records[0].eligible)
        self.assertIn("does not intersect claimed half", inventory.records[0].warnings)
        self.assertTrue(inventory.records[1].eligible)
        self.assertEqual(inventory.status_for_half(1), MISSING_TAG)
        self.assertEqual(inventory.status_for_half(2), CANDIDATE_AVAILABLE)

    def test_missing_or_invalid_half_is_audited_but_cannot_proceed(self):
        inventory = extract_opening_kickoff_candidates([
            event(start=105, end=115, half=None),
            event(start=105, end=115, half="Third Half"),
            event(start=105, end=400, end_frame=400),
        ], timeline=timeline())

        self.assertEqual(len(inventory.records), 3)
        self.assertTrue(all(not record.eligible for record in inventory.records))
        self.assertIn("missing_half", inventory.records[0].warnings)
        self.assertIn("invalid_half", inventory.records[1].warnings)
        self.assertIn("invalid_frame_bounds", inventory.records[2].warnings)
        self.assertEqual(inventory.status_for_half(1), MISSING_TAG)

    def test_frame_rounding_uses_existing_half_open_conversion(self):
        inventory = extract_opening_kickoff_candidates([
            event(start=0, end=10, start_s=0.18, end_s=0.22, start_frame=4, end_frame=6, half="1st Half")
        ], timeline=timeline())

        candidate = inventory.records[0]
        self.assertEqual((candidate.start_frame, candidate.end_frame), (4, 6))
        self.assertEqual(candidate.raw_start_seconds, 0.18)
        self.assertEqual(candidate.raw_end_seconds, 0.22)

    def test_missing_tag_status_is_explicit_for_each_half(self):
        inventory = extract_opening_kickoff_candidates([], timeline=timeline())

        self.assertEqual(inventory.status_for_half(1), MISSING_TAG)
        self.assertEqual(inventory.status_for_half(2), MISSING_TAG)
        self.assertIsNone(inventory.selected_candidate(1))

    def test_candidate_records_are_context_only_and_do_not_emit_submission_labels(self):
        inventory = extract_opening_kickoff_candidates([
            event(start=205, end=215, half="2nd Half", team="Barcelona")
        ], timeline=timeline())

        candidate = inventory.candidates_for_half(2)[0]
        self.assertEqual(candidate.team_value, "Barcelona")
        self.assertNotIn(candidate.team_value, {"H", "A", "D", "X"})
        self.assertEqual(candidate.source, "smart_tagging")

    def test_generic_extractor_accepts_opening_and_after_goal_kickoffs(self):
        inventory = extract_kickoff_candidates([
            event(start=105, end=115, tag_type="Kick Off (Start)"),
            event(start=125, end=135, tag_type="Kick Off (After Goal)"),
            event(start=140, end=150, tag_type="Corner Kick"),
        ], timeline=timeline())

        self.assertEqual(len(inventory.candidates_for_half(1)), 2)
        self.assertEqual(
            [candidate.type_value for candidate in inventory.candidates_for_half(1)],
            ["Kick Off (Start)", "Kick Off (After Goal)"],
        )
        self.assertEqual(
            len(inventory.candidates_for_half(1, kickoff_type="opening")), 1,
        )
        self.assertEqual(
            len(inventory.candidates_for_half(1, kickoff_type="after_goal")), 1,
        )

    def test_opening_wrapper_still_excludes_after_goal_kickoffs(self):
        inventory = extract_opening_kickoff_candidates([
            event(start=105, end=115, tag_type="Kick Off (After Goal)"),
            event(start=125, end=135, tag_type="Kick Off (Start)"),
        ], timeline=timeline())
        self.assertEqual(len(inventory.candidates_for_half(1)), 1)
        self.assertEqual(inventory.candidates_for_half(1)[0].type_value, "Kick Off (Start)")


if __name__ == "__main__":
    unittest.main()
