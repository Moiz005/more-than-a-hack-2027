"""Synthetic acceptance tests for the HBK-01 half-boundary overlay policy."""

import unittest

from starter_v6.possession import possession_spells
from starter_v6.timeline import TacticalTimeline
from starter_v6.half_boundary_policy import (
    APPLIED,
    AUDIT_ONLY,
    NO_CHANGE,
    OVERLAY,
    REJECTED,
    apply_kickoff_prefix,
)
from starter_v6.kickoff_atd import (
    AMBIGUOUS,
    CONFIRMED,
    INSUFFICIENT_EVIDENCE,
    KickoffDetectionResult,
)


def timeline():
    mask = bytearray(16)
    mask[2:6] = bytes([1]) * 4
    mask[9:14] = bytes([2]) * 5
    return TacticalTimeline(
        source="tactical",
        fps=25,
        frame_count=16,
        half_by_frame=bytes(mask),
        half_ranges=((1, 2, 5), (2, 9, 13)),
    )


def result(status, execution_frame=None):
    return KickoffDetectionResult(
        status=status,
        execution_frame=execution_frame,
        video_timestamp_seconds=(execution_frame / 25.0
                                 if execution_frame is not None else None),
        reasons=(),
        candidates=(),
        evaluated_frames=0,
    )


class HalfBoundaryPolicyTests(unittest.TestCase):
    def setUp(self):
        self.timeline = timeline()
        self.base = (
            "X", "X", "H", "H", "A", "D", "X", "X", "X",
            "A", "A", "D", "H", "H", "X", "X",
        )

    def test_one_frame_prefix_changes_only_the_frame_before_execution(self):
        output = apply_kickoff_prefix(
            self.base, self.timeline,
            {1: result(CONFIRMED, 3), 2: result(CONFIRMED, 10)},
            mode=OVERLAY,
        )
        self.assertEqual(output.status, APPLIED)
        self.assertEqual(output.labels[9:14], ("D", "A", "D", "H", "H"))
        self.assertEqual(output.changed_frames, (9,))
        self.assertEqual(output.permitted_interval, (9, 10))
        self.assertEqual(output.changed_counts, (("A", "D", 1),))

    def test_long_prefix_stops_before_kickoff_and_preserves_suffix(self):
        output = apply_kickoff_prefix(
            self.base, self.timeline,
            {2: result(CONFIRMED, 13)}, mode=OVERLAY,
        )
        self.assertEqual(output.status, APPLIED)
        self.assertEqual(output.labels[9:14], ("D", "D", "D", "D", "H"))
        self.assertEqual(output.changed_frames, (9, 10, 12))
        self.assertEqual(output.unchanged_frame_count, 13)

    def test_first_half_result_is_audit_only(self):
        output = apply_kickoff_prefix(
            self.base, self.timeline,
            {1: result(CONFIRMED, 3), 2: result(INSUFFICIENT_EVIDENCE)},
            mode=OVERLAY,
        )
        self.assertEqual(output.status, REJECTED)
        self.assertEqual(output.labels, self.base)
        self.assertEqual(output.first_half_result.execution_frame, 3)

    def test_audit_mode_never_changes_labels(self):
        output = apply_kickoff_prefix(
            self.base, self.timeline,
            {2: result(CONFIRMED, 12)}, mode="audit",
        )
        self.assertEqual(output.status, AUDIT_ONLY)
        self.assertEqual(output.labels, self.base)
        self.assertEqual(output.changed_frames, ())
        self.assertEqual(output.permitted_interval, (9, 12))

    def test_already_dead_prefix_reports_no_change(self):
        base = self.base[:9] + ("D", "D", "D", "D", "H") + self.base[14:]
        output = apply_kickoff_prefix(
            base, self.timeline, {2: result(CONFIRMED, 13)}, mode=OVERLAY,
        )
        self.assertEqual(output.status, NO_CHANGE)
        self.assertEqual(output.labels, base)
        self.assertEqual(output.changed_frames, ())

    def test_ambiguous_or_missing_detection_fails_closed(self):
        for detection in (result(AMBIGUOUS), result(INSUFFICIENT_EVIDENCE)):
            output = apply_kickoff_prefix(
                self.base, self.timeline, {2: detection}, mode=OVERLAY,
            )
            self.assertEqual(output.status, REJECTED)
            self.assertEqual(output.labels, self.base)
            self.assertEqual(output.changed_frames, ())

    def test_kickoff_at_graded_start_is_rejected(self):
        output = apply_kickoff_prefix(
            self.base, self.timeline, {2: result(CONFIRMED, 9)}, mode=OVERLAY,
        )
        self.assertEqual(output.status, REJECTED)
        self.assertIn("kickoff_at_graded_start", output.reason)

    def test_kickoff_outside_second_half_is_rejected(self):
        for frame in (8, 14, 16):
            output = apply_kickoff_prefix(
                self.base, self.timeline, {2: result(CONFIRMED, frame)}, mode=OVERLAY,
            )
            self.assertEqual(output.status, REJECTED)
            self.assertEqual(output.labels, self.base)

    def test_wrong_sized_arrays_and_wrong_x_mask_are_rejected(self):
        with self.assertRaises(ValueError):
            apply_kickoff_prefix(
                self.base[:-1], self.timeline, {2: result(CONFIRMED, 10)}, mode=OVERLAY,
            )
        wrong_x = self.base[:1] + ("D",) + self.base[2:]
        with self.assertRaises(ValueError):
            apply_kickoff_prefix(
                wrong_x, self.timeline, {2: result(CONFIRMED, 10)}, mode=OVERLAY,
            )

    def test_x_is_required_outside_grade_and_h_a_d_inside_grade(self):
        wrong_graded = self.base[:3] + ("X",) + self.base[4:]
        with self.assertRaises(ValueError):
            apply_kickoff_prefix(
                wrong_graded, self.timeline, {2: result(CONFIRMED, 10)}, mode=OVERLAY,
            )

    def test_terminal_frames_and_first_half_are_preserved(self):
        output = apply_kickoff_prefix(
            self.base, self.timeline, {2: result(CONFIRMED, 13)}, mode=OVERLAY,
        )
        self.assertEqual(output.labels[2:6], self.base[2:6])
        self.assertEqual(output.labels[5], self.base[5])
        self.assertEqual(output.labels[13], self.base[13])
        self.assertTrue(all(output.preservation_assertions.values()))

    def test_spell_boundaries_show_why_false_dead_prefixes_are_risky(self):
        live = ("H", "H", "H", "H", "H")
        separated = ("H", "H", "D", "D", "H")
        self.assertEqual(possession_spells(live), [("H", 0, 4)])
        self.assertEqual(possession_spells(separated), [("H", 0, 1), ("H", 4, 4)])

    def test_input_sequence_is_not_mutated_and_diff_is_exact(self):
        mutable = list(self.base)
        output = apply_kickoff_prefix(
            mutable, self.timeline, {2: result(CONFIRMED, 12)}, mode=OVERLAY,
        )
        self.assertEqual(tuple(mutable), self.base)
        for index, label in enumerate(output.labels):
            if index in output.changed_frames:
                self.assertTrue(9 <= index < 12)
            else:
                self.assertEqual(label, self.base[index])


if __name__ == "__main__":
    unittest.main()
