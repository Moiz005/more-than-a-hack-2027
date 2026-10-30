"""Phase 2 synthetic fixtures, counterfactuals, and trace contracts."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from starter_v6.synthetic import (
    ALL_RULES,
    FRAME_RATE,
    TIMING_HYPOTHESES,
    frames_from_seconds,
    fixture_catalog,
    fixture_rule_coverage,
    trace_fixture,
)


ROOT = Path(__file__).resolve().parents[2]


class SyntheticIntegrationTests(unittest.TestCase):
    def test_catalog_is_synthetic_and_covers_every_rule(self):
        fixtures = fixture_catalog()
        self.assertGreaterEqual(len(fixtures), 8)
        coverage = fixture_rule_coverage()
        self.assertEqual(set(coverage), set(ALL_RULES))
        self.assertTrue(all(coverage[rule] for rule in ALL_RULES))
        self.assertTrue(all(fixture.expectation_kind in {"characterization", "acceptance"} for fixture in fixtures))
        self.assertTrue(any(fixture.expectation_kind == "acceptance" for fixture in fixtures))
        self.assertTrue(any(fixture.expectation_kind == "characterization" for fixture in fixtures))
        self.assertTrue(all(not fixture.name.startswith("BAR-") for fixture in fixtures))

    def test_trace_preserves_known_architecture_signals(self):
        signals = {
            signal
            for fixture in fixture_catalog()
            for signal in fixture.failure_signals
        }
        self.assertTrue({
            "baseline_confirmed_dead_emission_is_one_hot",
            "gap_evidence_not_encoded_in_hmm_emission",
        }.issubset(signals))

    def test_timing_hypotheses_convert_explicitly_at_25_fps(self):
        self.assertEqual(FRAME_RATE, 25)
        self.assertEqual(frames_from_seconds(TIMING_HYPOTHESES["boundary_crossing_window_s"]), 25)
        self.assertEqual(frames_from_seconds(TIMING_HYPOTHESES["near_boundary_missing_duration_s"]), 50)
        self.assertEqual(frames_from_seconds(TIMING_HYPOTHESES["micro_dead_long_family_s"][0]), 50)
        with self.assertRaises(ValueError):
            frames_from_seconds(TIMING_HYPOTHESES["micro_dead_long_family_s"][1])

    def test_trace_has_every_stage_and_is_deterministic(self):
        fixture = next(item for item in fixture_catalog() if item.name == "cue_change_and_restart_end")
        first = trace_fixture(fixture).as_dict()
        second = trace_fixture(fixture).as_dict()
        self.assertEqual(first, second)
        self.assertEqual(len(first["rows"]), len(fixture.frames))
        for row in first["rows"]:
            self.assertEqual(
                set(row),
                {"frame", "half", "tag", "quality", "gap", "team", "raw_dead",
                 "confirmed_dead", "emission", "decoded_label"},
            )
        self.assertIn("possession_spells", first)

    def test_nearby_controller_preserves_raw_restart_and_records_counterevidence(self):
        no_controller = next(item for item in fixture_catalog() if item.name == "restart_no_controller")
        nearby = next(item for item in fixture_catalog() if item.name == "restart_nearby_controller")
        no_trace = trace_fixture(no_controller).as_dict()
        nearby_trace = trace_fixture(nearby).as_dict()
        self.assertTrue(any("restart_stationary" in row["raw_dead"]["cues"] for row in no_trace["rows"]))
        nearby_rows = [row["raw_dead"] for row in nearby_trace["rows"]]
        self.assertTrue(any("restart_stationary" in row["cues"] for row in nearby_rows))
        self.assertTrue(any("nearby_team_control" in row["live_counterevidence"] for row in nearby_rows))
        self.assertTrue(all(row["event_context"] == "restart_context" for row in nearby_rows))

    def test_missing_ball_and_overlong_tags_are_traced_without_manual_labels(self):
        missing = next(item for item in fixture_catalog() if item.name == "live_missing_ball_and_gap_recovery")
        result = trace_fixture(missing).as_dict()
        missing_rows = [row for row in result["rows"] if "ball_missing" in row["quality"]["flags"]]
        self.assertTrue(missing_rows)
        self.assertTrue(all(row["confirmed_dead"]["confirmed"] is False for row in missing_rows))
        self.assertTrue(any(row["gap"]["score_away"] > 0 for row in missing_rows))

        overlong = next(item for item in fixture_catalog() if item.name == "overlong_set_piece")
        overlong_trace = trace_fixture(overlong).as_dict()
        self.assertTrue(all(row["tag"]["active"] for row in overlong_trace["rows"][:5]))
        self.assertTrue(any(row["team"]["inference_team"] == "H" for row in overlong_trace["rows"][2:]))

    def test_dead_cue_strengths_and_conflicting_tag_are_traceable(self):
        strengths = {}
        for name in ("restart_no_controller", "cue_change_and_restart_end", "boundary_and_jitter"):
            trace = trace_fixture(next(item for item in fixture_catalog() if item.name == name)).as_dict()
            strengths[name] = max(row["raw_dead"]["confidence"] for row in trace["rows"])
        self.assertLess(strengths["cue_change_and_restart_end"], strengths["boundary_and_jitter"])

        fixture = next(item for item in fixture_catalog() if item.name == "conflicting_tag_counterfactual")
        trace = trace_fixture(fixture).as_dict()
        self.assertTrue(any(row["tag"]["team_conflict"] for row in trace["rows"]))
        self.assertTrue(all(row["team"]["inference_team"] == "H" for row in trace["rows"]))

    def test_trace_cli_is_asset_free_and_json_deterministic(self):
        command = [sys.executable, "-B", "-m", "starter_v6.trace_synthetic", "--fixture", "boundary_and_jitter"]
        first = subprocess.run(command, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        second = subprocess.run(command, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(json.loads(first.stdout), json.loads(second.stdout))
        self.assertEqual(json.loads(first.stdout)["fixture"], "boundary_and_jitter")

    def test_full_catalog_trace_has_no_nonfinite_values(self):
        for fixture in fixture_catalog():
            with self.subTest(fixture=fixture.name):
                encoded = json.dumps(trace_fixture(fixture).as_dict(), allow_nan=False)
                self.assertIn('"decoded_labels"', encoded)


if __name__ == "__main__":
    unittest.main()
