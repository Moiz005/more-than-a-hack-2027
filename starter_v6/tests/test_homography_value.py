"""Synthetic counterfactuals for deciding whether H adds inference evidence."""

import unittest
from dataclasses import replace

import numpy as np

from starter_v6.features import E02Config
from starter_v6.contracts import ObservationQuality
from starter_v6.inference import iter_infer_e02
from starter_v6.load_homography import project, unproject
from starter_v6.possession import FrameEvidence, PlayerEvidence


PITCH_LENGTH_M = 105.3
PITCH_WIDTH_M = 68.0
SYNTHETIC_PITCH_TO_PIXEL = np.array([
    [1240.0, 30.0, 120.0],
    [15.0, 820.0, 110.0],
    [0.03, -0.02, 1.0],
])


def players(home_xy, away_xy):
    rows = []
    for team, point, slot_start in (("H", home_xy, 0), ("A", away_xy, 10)):
        for index in range(5):
            offset = 0.0 if index == 0 else index * 2.5
            rows.append(PlayerEvidence(
                team, point[0] + offset, point[1] + index * 3.0, 1.0,
                slot_start + index,
            ))
    return tuple(rows)


def project_then_unproject_xy(point):
    normalized_x = point[0] / PITCH_LENGTH_M
    normalized_y = point[1] / PITCH_WIDTH_M
    pixel_x, pixel_y = project(
        SYNTHETIC_PITCH_TO_PIXEL, normalized_x, normalized_y,
    )
    recovered_x, recovered_y = unproject(
        SYNTHETIC_PITCH_TO_PIXEL, pixel_x, pixel_y,
    )
    return recovered_x * PITCH_LENGTH_M, recovered_y * PITCH_WIDTH_M


def transform_frame_by_roundtrip(frame):
    ball = project_then_unproject_xy(frame.ball_xy) if frame.ball_xy is not None else None
    transformed_players = []
    for player in frame.players:
        x_m, y_m = project_then_unproject_xy((player.x_m, player.y_m))
        transformed_players.append(replace(player, x_m=x_m, y_m=y_m))
    return replace(frame, ball_xy=ball, players=tuple(transformed_players))


def decision_signature(frames):
    results = iter_infer_e02(
        frames,
        feature_config=E02Config(atd_signal_fusion_enabled=True),
    )
    return [
        (
            item.inference.label,
            item.inference.team_evidence.team,
            item.inference.dead_ball_evidence.confirmed,
            item.inference.dead_ball_evidence.cues,
            item.atd_signals.control.candidate_team,
            item.atd_signals.boundary.candidate,
            item.atd_signals.restart_motion.candidate,
        )
        for item in results
    ]


class HomographyValueTests(unittest.TestCase):
    def test_matrix_direction_and_inverse_are_pitch_to_pixel_then_back(self):
        pixel = project(SYNTHETIC_PITCH_TO_PIXEL, 0.25, 0.4)
        self.assertTrue(np.allclose(pixel, (442.0 / 0.9995, 441.75 / 0.9995), atol=1e-9))
        recovered = unproject(SYNTHETIC_PITCH_TO_PIXEL, *pixel)
        self.assertTrue(np.allclose(recovered, (0.25, 0.4), atol=1e-12))

    def test_roundtrip_preserves_corrupted_atd_coordinate_without_correcting_it(self):
        observed = (45.0, 27.0)
        corrupted = (observed[0] + 3.0, observed[1] - 2.0)
        roundtripped = project_then_unproject_xy(corrupted)
        self.assertTrue(np.allclose(roundtripped, corrupted, atol=1e-10))
        self.assertFalse(np.allclose(roundtripped, observed, atol=0.1))

    def test_homography_quality_metadata_is_distinct_from_atd_observation_quality(self):
        calibration_points = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.5, 0.5))
        observed_pixels = [
            project(SYNTHETIC_PITCH_TO_PIXEL, x, y)
            for x, y in calibration_points
        ]
        corrupted_matrix = SYNTHETIC_PITCH_TO_PIXEL.copy()
        corrupted_matrix[0, 2] += 12.0

        def synthetic_reprojection_error(matrix):
            predicted_pixels = [project(matrix, x, y) for x, y in calibration_points]
            squared_errors = [
                (predicted[0] - observed[0]) ** 2 + (predicted[1] - observed[1]) ** 2
                for predicted, observed in zip(predicted_pixels, observed_pixels)
            ]
            return float(np.sqrt(np.mean(squared_errors)))

        good_error = synthetic_reprojection_error(SYNTHETIC_PITCH_TO_PIXEL)
        corrupted_error = synthetic_reprojection_error(corrupted_matrix)
        atd_quality = ObservationQuality(
            observed=True,
            missing=False,
            finite_coordinate=True,
            valid_coordinate=True,
            plausible_speed=True,
            provenance=("ATD",),
        )
        well_fit = replace(
            atd_quality, homography_valid=True,
            homography_reprojection_error=good_error,
        )
        poorly_fit = replace(
            atd_quality, homography_valid=True,
            homography_reprojection_error=corrupted_error,
        )
        unavailable = replace(
            atd_quality, homography_valid=False,
            homography_reprojection_error=None,
        )

        self.assertEqual(well_fit.observed, poorly_fit.observed)
        self.assertEqual(well_fit.valid_coordinate, poorly_fit.valid_coordinate)
        self.assertEqual(well_fit.provenance, poorly_fit.provenance)
        self.assertNotEqual(
            well_fit.homography_reprojection_error,
            poorly_fit.homography_reprojection_error,
        )
        self.assertAlmostEqual(well_fit.homography_reprojection_error, 0.0)
        self.assertAlmostEqual(poorly_fit.homography_reprojection_error, 12.0, delta=0.1)
        self.assertFalse(unavailable.homography_valid)
        self.assertEqual(unavailable.homography_reprojection_error, None)

    def test_roundtrip_ablation_preserves_control_missing_boundary_and_restart_decisions(self):
        controlled = [
            FrameEvidence(
                index, 1, (20.0 + index * 0.1, 30.0),
                players((20.5 + index * 0.1, 30.0), (45.0, 30.0)),
            )
            for index in range(4)
        ]
        missing = [
            FrameEvidence(10, 1, (20.0, 30.0), players((20.5, 30.0), (45.0, 30.0))),
            FrameEvidence(11, 1, None, players((20.5, 30.0), (45.0, 30.0))),
            FrameEvidence(12, 1, (20.1, 30.0), players((20.6, 30.0), (45.0, 30.0))),
        ]
        boundary = [
            FrameEvidence(20, 1, (52.0, 67.7), players((54.0, 65.0), (95.0, 50.0))),
            FrameEvidence(21, 1, (52.0, 68.2), players((54.0, 65.0), (95.0, 50.0))),
        ]
        goal_line = [
            FrameEvidence(25, 1, (105.0, 25.0), players((103.0, 25.0), (95.0, 50.0))),
            FrameEvidence(26, 1, (105.5, 25.0), players((103.0, 25.0), (95.0, 50.0))),
        ]
        restart = [
            FrameEvidence(30, 1, (50.0, 34.0), players((52.0, 34.0), (80.0, 34.0)), 0.0, True),
            FrameEvidence(31, 1, (51.0, 34.0), players((53.0, 34.0), (80.0, 34.0)), 25.0, True),
            FrameEvidence(32, 1, (52.0, 34.0), players((54.0, 34.0), (80.0, 34.0)), 25.0, True),
        ]
        touchline_restart = [
            FrameEvidence(40, 1, (50.0, 66.8), players((52.0, 66.0), (80.0, 34.0)), 0.0, True),
            FrameEvidence(41, 1, (50.0, 67.0), players((52.0, 66.0), (80.0, 34.0)), 5.0, True),
            FrameEvidence(42, 1, (50.0, 67.2), players((52.0, 66.0), (80.0, 34.0)), 5.0, True),
        ]
        corner_restart = [
            FrameEvidence(50, 1, (104.0, 66.8), players((102.0, 65.0), (80.0, 34.0)), 0.0, True),
            FrameEvidence(51, 1, (103.8, 66.6), players((102.0, 65.0), (80.0, 34.0)), 7.1, True),
            FrameEvidence(52, 1, (103.6, 66.4), players((102.0, 65.0), (80.0, 34.0)), 7.1, True),
        ]

        for fixture in (
            controlled, missing, boundary, goal_line, restart,
            touchline_restart, corner_restart,
        ):
            roundtripped = [transform_frame_by_roundtrip(item) for item in fixture]
            self.assertEqual(decision_signature(fixture), decision_signature(roundtripped))

        boundary_signals = decision_signature(boundary)
        self.assertTrue(any(row[5] for row in boundary_signals))
        self.assertTrue(any(row[5] for row in decision_signature(goal_line)))
        restart_signals = decision_signature(restart)
        self.assertTrue(any(row[6] for row in restart_signals))
        self.assertTrue(any(row[6] for row in decision_signature(touchline_restart)))
        self.assertTrue(any(row[6] for row in decision_signature(corner_restart)))


if __name__ == "__main__":
    unittest.main()
