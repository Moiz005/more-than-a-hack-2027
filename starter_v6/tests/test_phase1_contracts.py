import csv
import tempfile
import unittest
from pathlib import Path

from starter_v6.contracts import (
    Evidence,
    EvidenceSource,
    FrameReference,
    ObservationQuality,
    PossibleOwner,
    PlayState,
    RestartHypothesis,
    RestartPhase,
    RestartType,
)
from starter_v6.ingestion import ATDMetadata, SmartTagEvent, TrackSlot, iter_atd_frames, load_homography_arrays
from starter_v6.tag_features import iter_tag_evidence
from starter_v6.timeline import (
    build_tactical_timeline,
    seconds_to_half_open_frames,
    validate_atd_frame_mapping,
    validate_homography_frame_index,
    validate_tactical_reference,
)


class Phase1TimelineTests(unittest.TestCase):
    def test_pinned_tactical_reference_and_half_reset_contract(self):
        timeline = build_tactical_timeline()
        validate_tactical_reference(timeline.source, timeline.fps, timeline.frame_count)
        self.assertEqual(timeline.source, "tactical")
        self.assertEqual(timeline.fps, 25)
        self.assertEqual(timeline.frame_count, 199319)
        self.assertEqual(timeline.half_ranges, ((1, 11185, 90651), (2, 110808, 190197)))
        self.assertEqual(timeline.half_by_frame[11184], 0)
        self.assertEqual(timeline.half_by_frame[11185], 1)
        self.assertEqual(timeline.half_by_frame[90652], 0)
        self.assertEqual(timeline.half_by_frame[110807], 0)
        self.assertEqual(timeline.half_by_frame[110808], 2)

    def test_wrong_source_or_reference_dimensions_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "tactical"):
            validate_tactical_reference("broadcast", 25, 199319)
        with self.assertRaisesRegex(ValueError, "25 FPS"):
            validate_tactical_reference("tactical", 30, 199319)
        with self.assertRaisesRegex(ValueError, "199319"):
            validate_tactical_reference("tactical", 25, 199318)

    def test_atd_mapping_and_smart_tag_half_open_rounding(self):
        validate_atd_frame_mapping(1, 0)
        validate_atd_frame_mapping(199319, 199318)
        with self.assertRaisesRegex(ValueError, "frame_id"):
            validate_atd_frame_mapping(2, 0)
        self.assertEqual(seconds_to_half_open_frames(1.0, 2.0), (25, 50))
        self.assertEqual(seconds_to_half_open_frames(1.001, 2.001), (25, 50))
        with self.assertRaisesRegex(ValueError, "half-open"):
            seconds_to_half_open_frames(2.0, 1.0)

        event = SmartTagEvent(
            "SET PIECES", 1.0, 2.0, 25, 50,
            {"Type": "Corner Kick", "Half": "1st Half"}, "H", "Barcelona",
        )
        tag_rows = iter_tag_evidence([event], 60)
        self.assertFalse(tag_rows[24].active)
        self.assertTrue(tag_rows[25].active)
        self.assertTrue(tag_rows[49].restart_context)
        self.assertFalse(tag_rows[50].active)

        overlap = SmartTagEvent(
            "BUILD UP", 1.5, 2.5, 38, 63,
            {"Team": "Barcelona"}, "H", "Barcelona",
        )
        overlap_rows = iter_tag_evidence([event, overlap], 70)
        self.assertTrue(overlap_rows[40].overlap)
        self.assertTrue(overlap_rows[40].capped)
        self.assertEqual(overlap_rows[40].home_prior, 1.0)

    def test_atd_stream_rejects_missing_duplicate_and_out_of_order_ids(self):
        metadata = ATDMetadata(
            team_ids=("home", "away"), team_names=("Barcelona", "Athletic Club"),
            slots=(TrackSlot(0, "slot-1", "Track 1", "H"),),
            pitch_length_m=105.3, pitch_width_m=68.0,
        )

        def write_rows(rows):
            handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False)
            with handle:
                for row in rows:
                    handle.write(row + "\n")
            return Path(handle.name)

        valid = write_rows(["1:0.1,0.2,1.0:0.2,0.3,2.0", "2:0.2,0.3,1.0:0.3,0.4,2.0"])
        try:
            frames = list(iter_atd_frames(valid, metadata, expected_frames=2))
            self.assertEqual((frames[0].frame_id, frames[0].video_frame), (1, 0))
            self.assertEqual((frames[-1].frame_id, frames[-1].video_frame), (2, 1))
        finally:
            valid.unlink()

        for rows in (
            ["1:0.1,0.2,1.0:0.2,0.3,2.0", "3:0.2,0.3,1.0:0.3,0.4,2.0"],
            ["1:0.1,0.2,1.0:0.2,0.3,2.0", "1:0.2,0.3,1.0:0.3,0.4,2.0"],
            ["2:0.1,0.2,1.0:0.2,0.3,2.0", "3:0.2,0.3,1.0:0.3,0.4,2.0"],
        ):
            path = write_rows(rows)
            try:
                with self.assertRaisesRegex(ValueError, "expected frame_id"):
                    list(iter_atd_frames(path, metadata, expected_frames=2))
            finally:
                path.unlink()

    def test_homography_index_contract_and_loader_preserve_quality_fields(self):
        validate_homography_frame_index(0, 0)
        validate_homography_frame_index(199318, 199318)
        with self.assertRaisesRegex(ValueError, "zero-based"):
            validate_homography_frame_index(1, 0)

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "homography.csv"
            fields = ["frame"] + ["h{}{}".format(row, col) for row in range(3) for col in range(3)]
            fields += ["reprojection_error", "valid"]
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(fields)
                writer.writerow([0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0.25, 1])
                writer.writerow([1, "nan", "nan", "nan", "nan", "nan", "nan", "nan", "nan", "nan", 12.0, 0])
            loaded = load_homography_arrays(path, expected_frames=2)
            self.assertEqual(list(loaded.frame_indices), [0, 1])
            self.assertEqual(list(loaded.valid), [1, 0])
            self.assertEqual(list(loaded.reprojection_error), [0.25, 12.0])
            self.assertEqual(loaded.mapping_direction, "normalized_pitch_xy_to_video_pixel_xy")


class Phase1EvidenceContractTests(unittest.TestCase):
    def test_observation_quality_makes_missingness_and_provenance_explicit(self):
        quality = ObservationQuality(
            observed=False,
            missing=True,
            finite_coordinate=False,
            valid_coordinate=False,
            time_gap_frames=3,
            plausible_speed=None,
            jump_flag=False,
            player_coverage=0,
            homography_valid=None,
            homography_reprojection_error=None,
            provenance=("ATD.ball",),
        )
        self.assertTrue(quality.missing)
        self.assertEqual(quality.provenance, ("ATD.ball",))
        with self.assertRaisesRegex(ValueError, "observed and missing"):
            ObservationQuality(True, True, True, True)

    def test_evidence_requires_dependency_group_and_typed_reference(self):
        evidence = Evidence(
            reference=FrameReference(frame=12),
            source=EvidenceSource.ATD,
            value=0.8,
            sign=1,
            meaning="near controlled ball",
            quality=0.9,
            missing=False,
            uncertainty=0.1,
            dependency_group="ATD.geometry",
        )
        self.assertEqual(evidence.source, EvidenceSource.ATD)
        self.assertEqual(evidence.reference.frame, 12)
        with self.assertRaisesRegex(ValueError, "dependency_group"):
            Evidence(FrameReference(frame=12), EvidenceSource.TAG, 1.0, 1,
                     "tag", 1.0, False, 0.0, "")

    def test_restart_hypothesis_uses_internal_states_not_submission_labels(self):
        hypothesis = RestartHypothesis(
            reference=FrameReference(interval=(100, 120)),
            play_state=PlayState.UNKNOWN,
            restart_type=RestartType.THROW_IN,
            possible_owner=PossibleOwner.UNKNOWN,
            phase=RestartPhase.PREPARATION,
            confidence=0.4,
            uncertainty=0.6,
            dependency_groups=("TAG.restart", "ATD.motion"),
        )
        self.assertEqual(hypothesis.possible_owner, PossibleOwner.UNKNOWN)
        self.assertNotIn("X", [state.value for state in PlayState])
        with self.assertRaisesRegex(ValueError, "interval"):
            FrameReference(interval=(10, 10))


if __name__ == "__main__":
    unittest.main()
