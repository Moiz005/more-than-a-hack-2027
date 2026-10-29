"""Synthetic schema and alignment tests; none of these tests use competition assets."""

import math
import tempfile
import unittest
from pathlib import Path

from games import half_video_blocks, half_of_video_frame
from starter_v2.ingestion import (
    HOMOGRAPHY_COLUMNS,
    IngestionError,
    half_index_by_video_frame,
    load_atd_arrays,
    load_homography_arrays,
    parse_atd_metadata,
    parse_smart_tagging,
)


METADATA_XML = """<Metadata>
  <Pitch><Length>105</Length><Width>68</Width></Pitch>
  <Team id="home"><Name>Home Team</Name></Team>
  <Team id="away"><Name>Away Team</Name></Team>
  <Player id="slot-1" teamId="home"><Name>Track 1</Name></Player>
  <Player id="slot-2" teamId="away"><Name>Track 2</Name></Player>
</Metadata>"""


class IngestionTests(unittest.TestCase):
    def write(self, folder, name, value):
        path = Path(folder) / name
        path.write_text(value, encoding="utf-8")
        return path

    def metadata(self, folder, xml=METADATA_XML):
        return parse_atd_metadata(self.write(folder, "metadata.xml", xml))

    def test_metadata_team_order_slot_mapping_and_dimensions(self):
        with tempfile.TemporaryDirectory() as folder:
            metadata = self.metadata(folder)
            self.assertEqual(metadata.team_names, ("Home Team", "Away Team"))
            self.assertEqual([slot.team for slot in metadata.slots], ["H", "A"])
            self.assertEqual(len(metadata.slots), 2)
            self.assertEqual((metadata.pitch_length_m, metadata.pitch_width_m), (105.3, 68.0))
            self.assertEqual((metadata.declared_pitch_length_m, metadata.declared_pitch_width_m), (105.0, 68.0))

    def test_duplicate_metadata_player_slots_are_rejected(self):
        duplicate = METADATA_XML.replace('id="slot-2"', 'id="slot-1"')
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(IngestionError, "duplicate track-slot"):
                self.metadata(folder, duplicate)

    def test_metadata_reads_declared_width_when_xml_omits_pitch_container(self):
        xml = METADATA_XML.replace("<Pitch><Length>105</Length><Width>68</Width></Pitch>", "<Width>68</Width>")
        with tempfile.TemporaryDirectory() as folder:
            metadata = self.metadata(folder, xml)
            self.assertIsNone(metadata.declared_pitch_length_m)
            self.assertEqual(metadata.declared_pitch_width_m, 68.0)

    def test_atd_first_last_frames_nan_masks_and_metric_coordinates(self):
        with tempfile.TemporaryDirectory() as folder:
            metadata = self.metadata(folder)
            raw = self.write(folder, "atd.txt", (
                "1:0.1,0.2,3.0;NaN,NaN,NaN:0.5,0.6\n"
                "2:0.2,0.3,NaN;0.4,0.5,1.2:NaN,NaN\n"
            ))
            arrays = load_atd_arrays(raw, metadata, expected_frames=2)
            self.assertEqual(list(arrays.frame_ids), [1, 2])
            self.assertEqual(list(arrays.video_frames), [0, 1])
            self.assertEqual(arrays.slot_count, 2)
            self.assertEqual(list(arrays.player_valid), [1, 0, 1, 1])
            self.assertEqual(list(arrays.player_speed_valid), [1, 0, 0, 1])
            self.assertAlmostEqual(arrays.player_x_norm[0], 0.1)
            self.assertAlmostEqual(arrays.player_x_m[0], 10.53)
            self.assertAlmostEqual(arrays.player_y_m[0], 13.6)
            self.assertTrue(math.isnan(arrays.player_x_norm[1]))
            self.assertTrue(math.isnan(arrays.player_x_m[1]))
            self.assertTrue(math.isnan(arrays.player_y_m[1]))
            self.assertEqual(list(arrays.ball_valid), [1, 0])
            self.assertTrue(math.isnan(arrays.ball_x_norm[1]))
            self.assertTrue(math.isnan(arrays.ball_x_m[1]))

    def test_full_normalized_pitch_span_scales_to_metres(self):
        with tempfile.TemporaryDirectory() as folder:
            metadata = self.metadata(folder)
            raw = self.write(folder, "atd.txt", "1:0,0,0;1,1,0:NaN,NaN\n")
            arrays = load_atd_arrays(raw, metadata, expected_frames=1)
            self.assertEqual(arrays.player_x_m[0], 0.0)
            self.assertEqual(arrays.player_y_m[0], 0.0)
            self.assertAlmostEqual(arrays.player_x_m[1] - arrays.player_x_m[0], 105.3)
            self.assertAlmostEqual(arrays.player_y_m[1] - arrays.player_y_m[0], 68.0)
            self.assertEqual(arrays.player_valid[1], 1)
            self.assertEqual(arrays.ball_valid[0], 0)
            self.assertTrue(math.isnan(arrays.ball_x_m[0]))

    def test_atd_shifted_duplicate_dropped_and_malformed_frames_fail(self):
        cases = (
            ("2:0.1,0.2,0.3;0.2,0.3,0.4:0.3,0.4\n", "expected frame_id 1"),
            ("1:0.1,0.2,0.3;0.2,0.3,0.4:0.3,0.4\n"
             "1:0.1,0.2,0.3;0.2,0.3,0.4:0.3,0.4\n", "expected frame_id 2"),
            ("1:0.1,0.2,0.3;0.2,0.3,0.4:0.3,0.4\n", "expected 2 frames, found 1"),
            ("1:0.1,0.2,0.3:0.3,0.4\n", "expected 2 player slots"),
            ("not-a-frame\n", "expected frame:players:ball"),
            ("1:inf,0.2,0.3;0.2,0.3,0.4:0.3,0.4\n", "infinity is not a valid observation"),
        )
        for content, expected_error in cases:
            with self.subTest(error=expected_error), tempfile.TemporaryDirectory() as folder:
                metadata = self.metadata(folder)
                raw = self.write(folder, "atd.txt", content)
                with self.assertRaisesRegex(IngestionError, expected_error):
                    load_atd_arrays(raw, metadata, expected_frames=2)

    def test_smart_tagging_rounding_team_normalization_and_na(self):
        xml = """<document><instance>
          <start>0.1</start><end>0.14</end><code>Set Pieces</code>
          <label><group>team</group><text> bArCeLoNa </text></label>
          <label><group>Half</group><text>1st Half</text></label>
        </instance><instance>
          <start>1.0</start><end>1.1</end><code>Build Up</code>
          <label><group>Team</group><text>N/A</text></label>
        </instance></document>"""
        with tempfile.TemporaryDirectory() as folder:
            path = self.write(folder, "tags.xml", xml)
            events = parse_smart_tagging(path, fps=25, expected_frames=100)
            self.assertEqual(len(events), 2)
            self.assertEqual((events[0].start_frame, events[0].end_frame), (2, 4))
            self.assertEqual(events[0].code, "SET PIECES")
            self.assertEqual(events[0].team, "H")
            self.assertEqual(events[0].tags["Half"], "1st Half")
            self.assertEqual(events[1].team, "N/A")

    def test_empty_and_malformed_smart_tagging(self):
        with tempfile.TemporaryDirectory() as folder:
            empty = self.write(folder, "empty.xml", "<document />")
            self.assertEqual(parse_smart_tagging(empty), [])
            malformed = self.write(folder, "malformed.xml", "<document><instance><start>bad</start></instance></document>")
            with self.assertRaisesRegex(IngestionError, "missing start or end"):
                parse_smart_tagging(malformed)

    def test_games_half_boundaries_and_ungraded_frames(self):
        blocks = half_video_blocks("BAR-ATH")
        first, second = blocks
        self.assertEqual(half_of_video_frame("BAR-ATH", first[1]), 1)
        self.assertEqual(half_of_video_frame("BAR-ATH", first[2]), 1)
        self.assertIsNone(half_of_video_frame("BAR-ATH", first[1] - 1))
        self.assertIsNone(half_of_video_frame("BAR-ATH", first[2] + 1))
        self.assertEqual(half_of_video_frame("BAR-ATH", second[1]), 2)
        self.assertEqual(half_of_video_frame("BAR-ATH", second[2]), 2)
        labels, ranges = half_index_by_video_frame(199319)
        self.assertEqual(labels[0], 0)
        self.assertEqual(labels[first[1]], 1)
        self.assertEqual(labels[first[2]], 1)
        self.assertEqual(labels[second[1]], 2)
        self.assertEqual(labels[second[2]], 2)
        self.assertEqual(labels[100000], 0)
        self.assertEqual(ranges[1], (first[1], first[2]))

    def test_homography_shape_flags_alignment_and_direction(self):
        columns = ("frame",) + HOMOGRAPHY_COLUMNS + ("reprojection_error", "valid")
        valid_values = [str(value) for value in range(1, 10)]
        invalid_values = ["nan"] * 9
        content = ",".join(columns) + "\n"
        content += "0," + ",".join(valid_values) + ",0.25,1\n"
        content += "1," + ",".join(invalid_values) + ",nan,0\n"
        with tempfile.TemporaryDirectory() as folder:
            path = self.write(folder, "homography.csv", content)
            matrices = load_homography_arrays(path, expected_frames=2)
            self.assertEqual(list(matrices.frame_indices), [0, 1])
            self.assertEqual(list(matrices.valid), [1, 0])
            self.assertEqual(len(matrices.matrices), 18)
            self.assertEqual(matrices.mapping_direction, "normalized_pitch_xy_to_video_pixel_xy")

    def test_homography_invalid_flag_and_missing_frame_are_rejected(self):
        columns = ("frame",) + HOMOGRAPHY_COLUMNS + ("reprojection_error", "valid")
        matrix = ",".join(["1"] * 9)
        with tempfile.TemporaryDirectory() as folder:
            bad_flag = self.write(folder, "bad_flag.csv",
                                  ",".join(columns) + "\n0," + matrix + ",0,maybe\n")
            with self.assertRaisesRegex(IngestionError, "malformed matrix or validity"):
                load_homography_arrays(bad_flag, expected_frames=1)
            missing = self.write(folder, "missing.csv", ",".join(columns) + "\n")
            with self.assertRaisesRegex(IngestionError, "expected 1 homography frames, found 0"):
                load_homography_arrays(missing, expected_frames=1)
            extra = self.write(folder, "extra.csv",
                               ",".join(columns) + "\n0," + matrix + ",0,1,unexpected\n")
            with self.assertRaisesRegex(IngestionError, "unexpected extra columns"):
                load_homography_arrays(extra, expected_frames=1)


if __name__ == "__main__":
    unittest.main()
