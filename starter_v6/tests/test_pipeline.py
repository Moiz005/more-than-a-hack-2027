"""Synthetic adapter, Smart Tag context, and aggregate reporting tests."""

import unittest

from starter_v5.ingestion import ATDFrame, ATDMetadata, Observation, SmartTagEvent, TrackSlot
from starter_v5.pipeline import (
    frame_evidence_from_atd,
    iter_frame_evidence,
    restart_frame_mask,
    summarize_inferences,
)
from starter_v5.possession import FrameEvidence, PlayerEvidence, infer_possession


def observation(x=0.5, y=0.5, speed=1.0, valid=True, speed_valid=True):
    return Observation(
        x_norm=x if valid else float("nan"),
        y_norm=y if valid else float("nan"),
        speed_mps=speed if speed_valid else float("nan"),
        x_m=x * 105.3 if valid else float("nan"),
        y_m=y * 68.0 if valid else float("nan"),
        valid=valid,
        speed_valid=speed_valid,
    )


class PipelineAdapterTests(unittest.TestCase):
    def setUp(self):
        self.metadata = ATDMetadata(
            team_ids=("home", "away"),
            team_names=("Barcelona", "Athletic Club"),
            slots=(TrackSlot(0, "slot-1", "Track 1", "H"),
                   TrackSlot(1, "slot-2", "Track 2", "A")),
            pitch_length_m=105.3,
            pitch_width_m=68.0,
        )

    def test_adapter_preserves_missing_ball_and_team_slot_mapping(self):
        raw = ATDFrame(1, 0, (observation(0.2, 0.3), observation(0.8, 0.7)),
                       observation(valid=False, speed_valid=False))
        frame = frame_evidence_from_atd(raw, self.metadata, half=1, restart_context=False)
        self.assertEqual(frame.frame, 0)
        self.assertIsNone(frame.ball_xy)
        self.assertIsNone(frame.ball_speed_mps)
        self.assertEqual([player.team for player in frame.players], ["H", "A"])
        self.assertAlmostEqual(frame.players[0].x_m, 21.06)

    def test_adapter_does_not_promote_missing_player_coordinates_to_zero(self):
        raw = ATDFrame(1, 0, (observation(valid=False), observation(0.8, 0.7)), observation())
        frame = frame_evidence_from_atd(raw, self.metadata, half=1, restart_context=False)
        self.assertEqual(len(frame.players), 1)
        self.assertEqual(frame.players[0].team, "A")

    def test_adapter_rejects_slot_count_and_frame_alignment_errors(self):
        wrong_slots = ATDFrame(1, 0, (observation(),), observation())
        with self.assertRaisesRegex(ValueError, "slot count"):
            frame_evidence_from_atd(wrong_slots, self.metadata, half=1, restart_context=False)
        shifted = ATDFrame(2, 0, (observation(), observation()), observation())
        with self.assertRaisesRegex(ValueError, "frame_id"):
            frame_evidence_from_atd(shifted, self.metadata, half=1, restart_context=False)

    def test_stream_adapter_checks_first_last_rows_and_mask_alignment(self):
        raw = [
            ATDFrame(1, 0, (observation(), observation()), observation(valid=False)),
            ATDFrame(2, 1, (observation(), observation()), observation()),
        ]
        output = list(iter_frame_evidence(raw, self.metadata, bytearray([1, 2]), bytearray([0, 1])))
        self.assertEqual([item.frame for item in output], [0, 1])
        self.assertEqual([item.half for item in output], [1, 2])
        self.assertEqual([item.restart_context for item in output], [False, True])
        with self.assertRaisesRegex(ValueError, "expected video_frame 1"):
            list(iter_frame_evidence([raw[0], ATDFrame(3, 2, raw[1].players, raw[1].ball)],
                                     self.metadata, bytearray([1, 2]), bytearray([0, 0])))

    def test_restart_mask_uses_only_set_piece_types_and_half_open_intervals(self):
        events = [
            SmartTagEvent("SET PIECES", 1.0, 2.0, 25, 50,
                          {"Type": "Corner Kick"}, "H", "Barcelona"),
            SmartTagEvent("SET PIECES", 2.0, 3.0, 50, 75,
                          {"Type": "Throw-in"}, "N/A", "N/A"),
            SmartTagEvent("BUILD UP", 1.0, 2.0, 25, 50,
                          {"Type": "Free Kick"}, "A", "Athletic Club"),
        ]
        mask = restart_frame_mask(events, frame_count=80)
        self.assertEqual(mask[24], 0)
        self.assertEqual(mask[25], 1)
        self.assertEqual(mask[49], 1)
        self.assertEqual(mask[50], 1)
        self.assertEqual(mask[74], 1)
        self.assertEqual(mask[75], 0)


class AggregateSummaryTests(unittest.TestCase):
    def test_summary_separates_observations_inferences_and_ground_truth(self):
        frames = [
            FrameEvidence(0, 1, (1.0, 1.0), (PlayerEvidence("H", 1.1, 1.0),)),
            FrameEvidence(1, 1, None, ()),
            FrameEvidence(2, 1, (-1.0, 1.0), ()),
        ]
        results = infer_possession(frames)
        report = summarize_inferences(iter(results), runtime_seconds=0.2)
        self.assertEqual(report["observations"]["ball_observed_frames"], 2)
        self.assertIn("predicted_possession_count", report["inferences"])
        self.assertEqual(report["ground_truth"], {"used": False, "accuracy_or_score_computed": False})
        self.assertNotIn("ground_truth_labels", report)


if __name__ == "__main__":
    unittest.main()
