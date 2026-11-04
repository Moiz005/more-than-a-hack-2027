"""Phase 6 synthetic acceptance matrix for HBK-01.

These fixtures deliberately use small invented timelines and metric coordinates.
They exercise the public HBK-01 seams without target-match labels or licensed
assets; full-length CSV validation is performed against synthetic labels only.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from starter_v6.half_boundary_policy import APPLIED, AUDIT_ONLY, REJECTED, apply_kickoff_prefix
from starter_v6.ingestion import ATDFrame, ATDMetadata, Observation, SmartTagEvent, TrackSlot
from starter_v6.kickoff_atd import (
    CONFIRMED,
    INSUFFICIENT_EVIDENCE,
    KickoffATDConfig,
    detect_kickoff_execution,
)
from starter_v6.kickoff_tags import AMBIGUOUS, extract_opening_kickoff_candidates
from starter_v6.possession import possession_spells
from starter_v6.run_half_boundaries import _submission_bytes
from starter_v6.timeline import (
    TacticalTimeline,
    seconds_to_half_open_frames,
    validate_atd_frame_mapping,
)


METADATA = ATDMetadata(
    team_ids=("home", "away"),
    team_names=("Synthetic Home", "Synthetic Away"),
    slots=(
        TrackSlot(0, "home-1", "Home 1", "H"),
        TrackSlot(1, "away-1", "Away 1", "A"),
    ),
    pitch_length_m=100.0,
    pitch_width_m=60.0,
)


def synthetic_timeline():
    mask = bytearray(40)
    mask[2:6] = bytes([1]) * 4
    mask[20:35] = bytes([2]) * 15
    return TacticalTimeline(
        source="tactical", fps=25, frame_count=40,
        half_by_frame=bytes(mask), half_ranges=((1, 2, 5), (2, 20, 34)),
    )


def detection(status, execution_frame=None):
    return type("Detection", (), {
        "status": status,
        "execution_frame": execution_frame,
        "video_timestamp_seconds": (
            execution_frame / 25.0 if execution_frame is not None else None
        ),
        "reasons": (),
        "candidates": (),
        "evaluated_frames": 0,
    })()


def event(start, end, *, tag_type="Kick Off (Start)", half="1st Half",
          code="SET PIECES"):
    return SmartTagEvent(
        code, start / 25.0, end / 25.0, start, end,
        {"Type": tag_type, "Half": half, "Team": "N/A"}, None, "N/A",
    )


def observation(x_norm, y_norm=0.5, *, speed=0.0, valid=True, speed_valid=True):
    return Observation(
        x_norm, y_norm, speed if speed_valid else float("nan"),
        x_norm * METADATA.pitch_length_m if valid else float("nan"),
        y_norm * METADATA.pitch_width_m if valid else float("nan"),
        valid, speed_valid,
    )


def atd_frame(index, *, ball_x=0.5, ball_valid=True, ball_speed=0.0,
              speed_valid=True, player_x=0.52, player_valid=True):
    player = observation(player_x, valid=player_valid)
    return ATDFrame(
        frame_id=index + 1,
        video_frame=index,
        players=(player,),
        ball=observation(
            ball_x, valid=ball_valid, speed=ball_speed,
            speed_valid=speed_valid,
        ),
    )


def kickoff_candidate(start, end, *, half=1, before=0, after=0):
    value = "1st Half" if half == 1 else "2nd Half"
    inventory = extract_opening_kickoff_candidates(
        [event(start, end, half=value)],
        timeline=TacticalTimeline(
            "tactical", 25, 40, bytes(bytearray([1] * 20 + [2] * 20)),
            ((1, 0, 19), (2, 20, 39)),
        ),
        search_margin_before_frames=before,
        search_margin_after_frames=after,
    )
    return inventory.records[0]


def setup_then_kick(start, kick, *, speed_valid=True):
    rows = [atd_frame(index) for index in range(start, kick)]
    for index in range(kick, kick + 2):
        rows.append(atd_frame(
            index,
            ball_x=0.5 + 0.004 * (index - kick + 1),
            ball_speed=10.0,
            speed_valid=speed_valid,
        ))
    return rows


class Phase6BoundaryMatrixTests(unittest.TestCase):
    def setUp(self):
        self.timeline = synthetic_timeline()
        self.base = tuple(
            "X" if marker == 0 else ("H" if marker == 1 else "A")
            for marker in self.timeline.half_by_frame
        )

    def test_first_half_opening_is_audit_only_and_pre_grade_frames_stay_x(self):
        result = apply_kickoff_prefix(
            self.base,
            self.timeline,
            {1: detection(CONFIRMED, 3), 2: detection(CONFIRMED, 24)},
            mode="audit",
        )
        self.assertEqual(result.status, AUDIT_ONLY)
        self.assertEqual(result.labels, self.base)
        self.assertEqual(result.labels[:2], ("X", "X"))
        self.assertEqual(result.first_half_result.execution_frame, 3)

    def test_second_half_overlay_is_x_to_d_to_parent_and_kick_frame_is_excluded(self):
        result = apply_kickoff_prefix(
            self.base,
            self.timeline,
            {2: detection(CONFIRMED, 24)},
            mode="overlay",
        )
        self.assertEqual(result.status, APPLIED)
        self.assertEqual(result.labels[20:24], ("D", "D", "D", "D"))
        self.assertEqual(result.labels[24], self.base[24])
        self.assertEqual(result.changed_frames, (20, 21, 22, 23))

    def test_ungraded_regions_are_x_and_both_graded_terminal_frames_are_preserved(self):
        base = list(self.base)
        base[5] = "D"
        base[34] = "D"
        result = apply_kickoff_prefix(
            base, self.timeline, {2: detection(CONFIRMED, 24)}, mode="overlay",
        )
        self.assertEqual(result.labels[0:2], ("X", "X"))
        self.assertEqual(result.labels[6:20], ("X",) * 14)
        self.assertEqual(result.labels[35:40], ("X",) * 5)
        self.assertEqual(result.labels[5], "D")
        self.assertEqual(result.labels[34], "D")

    def test_tag_endpoint_is_context_not_execution_endpoint(self):
        before_tag = kickoff_candidate(5, 8, before=0, after=10)
        after_tag = kickoff_candidate(5, 15, before=0, after=0)
        late_kick = detect_kickoff_execution(
            setup_then_kick(5, 10), METADATA, before_tag,
            config=KickoffATDConfig(),
        )
        early_kick = detect_kickoff_execution(
            setup_then_kick(5, 10), METADATA, after_tag,
            config=KickoffATDConfig(),
        )
        self.assertEqual(late_kick.status, CONFIRMED)
        self.assertEqual(late_kick.execution_frame, 10)
        self.assertEqual(early_kick.execution_frame, 10)
        self.assertNotEqual(before_tag.end_frame, late_kick.execution_frame)
        self.assertNotEqual(after_tag.end_frame, early_kick.execution_frame)

    def test_tag_filter_excludes_all_non_opening_restart_types(self):
        types = ("Kick Off (After Goal)", "Corner Kick", "Throw-in", "Free Kick", "Goal Kick")
        inventory = extract_opening_kickoff_candidates(
            [event(5, 8, tag_type=value) for value in types],
            timeline=TacticalTimeline(
                "tactical", 25, 40, bytes(40), ((1, 0, 19), (2, 20, 39)),
            ),
        )
        self.assertEqual(len(inventory.candidates_for_half(1)), 0)
        self.assertTrue(all(not record.eligible for record in inventory.records))

    def test_missing_duplicate_and_wrong_half_tags_are_explicitly_ambiguous_or_missing(self):
        timeline = TacticalTimeline(
            "tactical", 25, 40, bytes(40), ((1, 0, 19), (2, 20, 39)),
        )
        duplicate = extract_opening_kickoff_candidates(
            [event(5, 8), event(6, 9)], timeline=timeline,
        )
        wrong_half = extract_opening_kickoff_candidates(
            [event(25, 28, half="1st Half")], timeline=timeline,
        )
        missing = extract_opening_kickoff_candidates([], timeline=timeline)
        self.assertEqual(duplicate.status_for_half(1), AMBIGUOUS)
        self.assertEqual(wrong_half.status_for_half(1), "MISSING_TAG")
        self.assertEqual(wrong_half.status_for_half(2), "MISSING_TAG")
        self.assertEqual(missing.status_for_half(1), "MISSING_TAG")
        self.assertIsNone(duplicate.selected_candidate(1))

    def test_displaced_kickoff_has_no_match_specific_frame_constant(self):
        candidate = kickoff_candidate(20, 24, half=2, after=8)
        result = detect_kickoff_execution(
            setup_then_kick(20, 27), METADATA, candidate,
            timeline=TacticalTimeline(
                "tactical", 25, 40, bytes([1] * 20 + [2] * 20),
                ((1, 0, 19), (2, 20, 39)),
            ),
        )
        self.assertEqual(result.status, CONFIRMED)
        self.assertEqual(result.execution_frame, 27)

    def test_missing_ball_and_player_motion_do_not_confirm_kickoff(self):
        missing = detect_kickoff_execution(
            [atd_frame(0), atd_frame(1), atd_frame(2, ball_valid=False),
             atd_frame(3, ball_x=0.52), atd_frame(4, ball_x=0.54)],
            METADATA, kickoff_candidate(0, 5),
        )
        player_only = detect_kickoff_execution(
            [atd_frame(index, player_x=0.52 + index * 0.03) for index in range(8)],
            METADATA, kickoff_candidate(0, 8),
        )
        self.assertEqual(missing.status, INSUFFICIENT_EVIDENCE)
        self.assertEqual(player_only.status, INSUFFICIENT_EVIDENCE)

    def test_one_frame_jump_is_rejected_but_missing_provider_speed_can_confirm(self):
        jump = detect_kickoff_execution(
            [atd_frame(0), atd_frame(1), atd_frame(2), atd_frame(3, ball_x=0.9),
             atd_frame(4, ball_x=0.9)],
            METADATA, kickoff_candidate(0, 5),
        )
        missing_speed = detect_kickoff_execution(
            setup_then_kick(0, 3, speed_valid=False), METADATA,
            kickoff_candidate(0, 5),
        )
        self.assertEqual(jump.status, INSUFFICIENT_EVIDENCE)
        self.assertEqual(missing_speed.status, CONFIRMED)
        self.assertEqual(missing_speed.execution_frame, 3)

    def test_stationary_centre_ball_without_kick_stays_unconfirmed(self):
        result = detect_kickoff_execution(
            [atd_frame(index) for index in range(10)],
            METADATA, kickoff_candidate(0, 10),
        )
        self.assertEqual(result.status, INSUFFICIENT_EVIDENCE)
        self.assertIsNone(result.execution_frame)

    def test_half_open_and_source_index_conversions_are_explicit(self):
        self.assertEqual(seconds_to_half_open_frames(0.18, 0.22, fps=25, frame_count=40), (4, 6))
        validate_atd_frame_mapping(1, 0)
        validate_atd_frame_mapping(28, 27)
        with self.assertRaises(ValueError):
            validate_atd_frame_mapping(28, 28)
        result = apply_kickoff_prefix(
            self.base, self.timeline, {2: detection(CONFIRMED, 24)}, mode="overlay",
        )
        self.assertEqual(result.permitted_interval, (20, 24))
        self.assertEqual(result.labels[24], self.base[24])

    def test_false_dead_prefix_can_fragment_a_possession_spell(self):
        self.assertEqual(possession_spells(("H", "H", "H", "H")), [("H", 0, 3)])
        self.assertEqual(
            possession_spells(("H", "H", "D", "D", "H")),
            [("H", 0, 1), ("H", 4, 4)],
        )

    def test_full_length_synthetic_csv_passes_official_structural_validator(self):
        frame_count = 199319
        labels = ["X"] * frame_count
        labels[11185] = "H"
        labels[110808] = "D"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic_submission.csv"
            path.write_bytes(_submission_bytes(labels))
            validator = Path(__file__).parents[2] / "evaluation" / "validate_submission.py"
            completed = subprocess.run(
                [sys.executable, str(validator), str(path)],
                cwd=str(Path(__file__).parents[2]),
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertIn("OK", completed.stdout)
            self.assertIn("199319 rows, frame 0..199318", completed.stdout)

    def test_unconfirmed_overlay_is_rejected_without_a_modified_label_result(self):
        result = apply_kickoff_prefix(
            self.base, self.timeline, {2: detection(INSUFFICIENT_EVIDENCE)}, mode="overlay",
        )
        self.assertEqual(result.status, REJECTED)
        self.assertEqual(result.labels, self.base)
        self.assertEqual(result.changed_frames, ())


if __name__ == "__main__":
    unittest.main()
