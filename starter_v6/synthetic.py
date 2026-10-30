"""Synthetic-only fixtures and stage-by-stage E04 trace utilities.

This module contains invented evidence streams only. It is deliberately not
imported by the match prediction runner and cannot access licensed assets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from starter_v6.emissions import FrameEmission
from starter_v6.features import E02Config, iter_frame_features
from starter_v6.hmm import HMMConfig, decode
from starter_v6.ingestion import SmartTagEvent
from starter_v6.inference import E02FrameInference, _team_evidence, iter_infer_e02
from starter_v6.possession import (
    FrameEvidence,
    PlayerEvidence,
    PossessionConfig,
    observe_dead_ball,
    iter_raw_play_state,
    possession_spells,
)
from starter_v6.tag_features import TagEvidence, iter_tag_evidence


ALL_RULES = tuple("R{:02d}".format(number) for number in range(1, 16))
FRAME_RATE = 25
TIMING_HYPOTHESES = {
    "boundary_crossing_window_s": 1.0,
    "near_boundary_disappearance_s": 0.5,
    "near_boundary_missing_duration_s": 2.0,
    "micro_dead_short_family_s": (1.5, 2.0),
    "micro_dead_long_family_s": (2.0, 2.5),
}


def frames_from_seconds(seconds: float) -> int:
    """Convert a synthetic timing hypothesis to 25 FPS frames explicitly."""
    frames = seconds * FRAME_RATE
    if int(frames) != frames or frames < 0:
        raise ValueError("synthetic timing hypothesis must convert to non-negative whole frames")
    return int(frames)


@dataclass(frozen=True)
class SyntheticFixture:
    """An invented stream with explicit rule coverage and expectation type."""

    name: str
    description: str
    frames: Tuple[FrameEvidence, ...]
    events: Tuple[SmartTagEvent, ...] = ()
    rule_ids: Tuple[str, ...] = ()
    expectation_kind: str = "characterization"
    expected: Mapping[str, object] = None
    failure_signals: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.frames:
            raise ValueError("synthetic fixture must contain frames")
        if any(rule not in ALL_RULES for rule in self.rule_ids):
            raise ValueError("unknown rule id in synthetic fixture")
        if self.expectation_kind not in {"characterization", "acceptance"}:
            raise ValueError("expectation_kind must be characterization or acceptance")
        if self.expected is None:
            object.__setattr__(self, "expected", {})


@dataclass(frozen=True)
class SyntheticTrace:
    fixture: str
    rows: Tuple[Mapping[str, object], ...]
    decoded_labels: Tuple[str, ...]
    possession_spells: Tuple[Tuple[str, int, int], ...]
    expectation_kind: str
    expected: Mapping[str, object]
    failure_signals: Tuple[str, ...]

    def as_dict(self) -> Dict[str, object]:
        return {
            "fixture": self.fixture,
            "rows": list(self.rows),
            "decoded_labels": list(self.decoded_labels),
            "possession_spells": [list(spell) for spell in self.possession_spells],
            "expectation_kind": self.expectation_kind,
            "expected": dict(self.expected),
            "failure_signals": list(self.failure_signals),
        }


def player(team: str, x_m: float, y_m: float, speed_mps: Optional[float] = None,
           track_id: Optional[int] = None) -> PlayerEvidence:
    return PlayerEvidence(team, x_m, y_m, speed_mps=speed_mps, track_id=track_id)


def frame(index: int, ball_xy, players: Iterable[PlayerEvidence] = (), *, half: int = 1,
          ball_speed_mps: Optional[float] = None, restart_context: bool = False,
          restart_action: Optional[str] = None) -> FrameEvidence:
    return FrameEvidence(index, half, ball_xy, tuple(players), ball_speed_mps,
                         restart_context, restart_action)


def tag_event(code: str, start: int, end: int, team: Optional[str] = None,
              tag_type: Optional[str] = None) -> SmartTagEvent:
    tags = {}
    if team is not None:
        tags["Team"] = team
    if tag_type is not None:
        tags["Type"] = tag_type
    return SmartTagEvent(code, start / 25.0, end / 25.0, start, end, tags, None, team)


def _low_motion_players(count: int = 8, *, offset: float = 0.0) -> Tuple[PlayerEvidence, ...]:
    players = []
    for index in range(count):
        team = "H" if index % 2 == 0 else "A"
        players.append(player(team, 20.0 + index + offset, 20.0, 0.0, index))
    return tuple(players)


def _live_players(team: str = "H", *, x_m: float = 10.0, speed_mps: float = 1.0) -> Tuple[PlayerEvidence, ...]:
    other = "A" if team == "H" else "H"
    players = [player(team, x_m + 0.3 * index, 10.0, speed_mps, index + 1) for index in range(5)]
    players.extend(player(other, x_m + 8.0 + 0.3 * index, 10.0, speed_mps, index + 6) for index in range(5))
    return tuple(players)


def fixture_catalog() -> Tuple[SyntheticFixture, ...]:
    """Return the complete invented Phase 2 fixture catalog."""
    return (
        SyntheticFixture(
            "restart_no_controller",
            "Stationary tagged restart without a nearby controller.",
            tuple(frame(i, (10.0, 10.0), ball_speed_mps=0.1, restart_context=True) for i in range(4)),
            events=(tag_event("SET PIECES", 0, 4, "N/A", "Throw-in"),),
            rule_ids=("R03", "R04", "R11", "R12", "R14"),
            expected={"raw_restart_cue": True, "missing_ball_is_dead": False},
        ),
        SyntheticFixture(
            "restart_nearby_controller",
            "The same restart with a nearby home controller; raw cue remains visible with live counterevidence.",
            tuple(frame(i, (10.0, 10.0), _live_players("H", x_m=10.1, speed_mps=0.0),
                        ball_speed_mps=0.1, restart_context=True) for i in range(4)),
            events=(tag_event("SET PIECES", 0, 4, "Barcelona", "Throw-in"),),
            rule_ids=("R03", "R04", "R11", "R12", "R14"),
            expected={"raw_restart_cue": True, "nearby_controller_is_live_counterevidence": True},
            expectation_kind="acceptance",
        ),
        SyntheticFixture(
            "overlong_set_piece",
            "Set-piece context that continues after a live restart.",
            (
                frame(0, (10.0, 10.0), ball_speed_mps=0.1, restart_context=True),
                frame(1, (10.0, 10.0), ball_speed_mps=0.1, restart_context=True),
                frame(2, (10.5, 10.0), _live_players("H", x_m=10.4), ball_speed_mps=2.0, restart_context=True),
                frame(3, (11.0, 10.0), _live_players("H", x_m=10.8), ball_speed_mps=2.0, restart_context=True),
                frame(4, (11.5, 10.0), _live_players("H", x_m=11.2), ball_speed_mps=2.0, restart_context=True),
            ),
            events=(tag_event("SET PIECES", 0, 5, "Barcelona", "Corner Kick"),),
            rule_ids=("R04", "R11", "R14"),
            expected={"tag_alone_is_not_dead": True, "live_restart_frames": (2, 3, 4)},
            expectation_kind="acceptance",
        ),
        SyntheticFixture(
            "cue_change_and_restart_end",
            "Restart-stationary to stationary-context to live H/A after restart.",
            (
                frame(0, (20.0, 20.0), ball_speed_mps=0.1, restart_context=True),
                frame(1, (20.0, 20.0), ball_speed_mps=0.1, restart_context=True),
                frame(2, (20.0, 20.0), _low_motion_players(), ball_speed_mps=0.0),
                frame(3, (20.0, 20.0), _low_motion_players(offset=0.1), ball_speed_mps=0.0),
                frame(4, (20.5, 20.0), _live_players("H", x_m=20.4), ball_speed_mps=2.0),
                frame(5, (21.0, 20.0), _live_players("A", x_m=20.9), ball_speed_mps=2.0),
            ),
            rule_ids=("R03", "R04", "R07", "R09", "R11", "R12", "R14"),
            expected={"cue_families": ("restart_stationary", "stationary_context", "live")},
            failure_signals=("baseline_dead_confirmation_uses_mixed_cue_counter",),
        ),
        SyntheticFixture(
            "live_missing_ball_and_gap_recovery",
            "Live H possession, missing-ball interval, and an approaching A recovery.",
            (
                frame(0, (10.0, 10.0), _live_players("H", x_m=10.0), ball_speed_mps=1.0),
                frame(1, (10.0, 10.0), _live_players("H", x_m=10.0), ball_speed_mps=1.0),
                frame(2, None, (player("H", 9.0, 10.0, 1.0, 1), player("A", 7.0, 10.0, 1.0, 2))),
                frame(3, None, (player("H", 8.0, 10.0, 1.0, 1), player("A", 4.0, 10.0, 1.0, 2))),
                frame(4, None, (player("H", 7.0, 10.0, 1.0, 1), player("A", 1.5, 10.0, 1.0, 2))),
                frame(5, (1.0, 10.0), (player("A", 1.1, 10.0, 1.0, 2), player("H", 8.0, 10.0, 1.0, 1)), ball_speed_mps=1.0),
            ),
            rule_ids=("R08", "R10", "R12"),
            expected={"missing_ball_not_dead": True, "gap_trace_present": True},
            expectation_kind="acceptance",
            failure_signals=("gap_evidence_not_encoded_in_hmm_emission",),
        ),
        SyntheticFixture(
            "boundary_and_jitter",
            "Boundary crossing candidate, isolated off-pitch jump, and stable in-play frames.",
            (
                frame(0, (10.0, 10.0), _live_players("H", x_m=10.0), ball_speed_mps=1.0),
                frame(1, (-1.0, 10.0), (), ball_speed_mps=1.0),
                frame(2, (10.1, 10.0), _live_players("H", x_m=10.0), ball_speed_mps=1.0),
                frame(3, (10.2, 10.0), _live_players("H", x_m=10.0), ball_speed_mps=1.0),
            ),
            rule_ids=("R01", "R02", "R03", "R08", "R12"),
            expected={"out_of_bounds_candidate": 1, "jitter_requires_confirmation": True},
            failure_signals=("baseline_confirmed_dead_emission_is_one_hot",),
        ),
        SyntheticFixture(
            "contextual_restart_families",
            "Synthetic goal, foul/offside, restart, and kickoff contexts with half reset.",
            (
                frame(0, (-1.0, 20.0), (), half=1, ball_speed_mps=0.0),
                frame(1, (10.0, 10.0), _live_players("H", x_m=10.0), half=1, ball_speed_mps=1.0),
                frame(2, None, (), half=0),
                frame(3, (10.0, 10.0), (), half=2, ball_speed_mps=0.1, restart_context=True),
                frame(4, (10.5, 10.0), _live_players("A", x_m=10.4), half=2, ball_speed_mps=1.0),
            ),
            events=(
                tag_event("GOALS", 0, 1, "Barcelona"),
                tag_event("SET PIECES", 1, 2, "Atletic Club", "Goal Kick"),
                tag_event("SET PIECES", 2, 3, "Atletic Club", "Free Kick"),
                tag_event("SET PIECES", 3, 4, "Atletic Club", "Penalty"),
                tag_event("SET PIECES", 4, 5, "Atletic Club", "Kick off (start)"),
                tag_event("FOUL", 0, 1, "N/A"),
                tag_event("OFFSIDE", 0, 1, "N/A"),
            ),
            rule_ids=("R04", "R05", "R06", "R11", "R13", "R14"),
            expected={"halftime_frame_is_x": True, "second_half_restart_is_context": True},
        ),
        SyntheticFixture(
            "low_motion_and_goalkeeper_live",
            "Low-motion live play and a slow home controller, not automatically D.",
            (
                frame(0, (30.0, 30.0), _low_motion_players(), ball_speed_mps=0.4),
                frame(1, (30.1, 30.0), (player("H", 30.2, 30.0, 0.1, 1), player("A", 38.0, 30.0, 0.1, 2)), ball_speed_mps=0.1),
                frame(2, (30.2, 30.0), (player("H", 30.3, 30.0, 0.1, 1), player("A", 38.0, 30.0, 0.1, 2)), ball_speed_mps=0.1),
            ),
            rule_ids=("R03", "R07", "R09", "R10", "R12"),
            expected={"low_motion_is_support_only": True, "goalkeeper_live_is_not_dead": True},
        ),
        SyntheticFixture(
            "conflicting_tag_counterfactual",
            "Strong H geometry with an overlapping opposing-team contextual tag.",
            tuple(frame(i, (50.0, 10.0), _live_players("H", x_m=50.2), ball_speed_mps=1.0) for i in range(3)),
            events=(
                tag_event("BUILD UP", 0, 3, "Atletic Club"),
                tag_event("PROGRESSION", 0, 3, "Barcelona"),
            ),
            rule_ids=("R12",),
            expected={"conflicting_tag_is_flagged": True, "clear_geometry_wins": True},
        ),
        SyntheticFixture(
            "short_stop_and_false_blip",
            "Explicit short out-of-bounds stop versus a noisy isolated ball jump.",
            (
                frame(0, (40.0, 40.0), _live_players("H", x_m=40.0), ball_speed_mps=1.0),
                frame(1, (-1.0, 40.0), (), ball_speed_mps=0.0),
                frame(2, (40.0, 40.0), _live_players("H", x_m=40.0), ball_speed_mps=1.0),
                frame(3, (41.0, 40.0), _live_players("H", x_m=41.0), ball_speed_mps=1.0),
            ),
            rule_ids=("R01", "R02", "R03", "R15"),
            expected={"strong_short_stop_is_visible": True, "duration_filter_is_hypothesis": True},
        ),
    )


def _emission_dict(emission: FrameEmission) -> Dict[str, object]:
    return {
        "frame": emission.frame,
        "half": emission.half,
        "home": emission.home,
        "away": emission.away,
        "dead": emission.dead,
        "informative": emission.informative,
    }


def _tag_dict(tag: TagEvidence) -> Dict[str, object]:
    return {
        "active": tag.active,
        "team_prior": tag.team_prior,
        "restart_context": tag.restart_context,
        "restart_type": tag.restart_type,
        "goal_context": tag.goal_context,
        "team_conflict": tag.team_conflict,
        "overlap": tag.overlap,
        "families": list(tag.families),
    }


def _row(result: E02FrameInference, raw_team, raw_dead, tag: TagEvidence) -> Dict[str, object]:
    features = result.features
    return {
        "frame": result.emission.frame,
        "half": result.emission.half,
        "tag": _tag_dict(tag),
        "quality": {
            "flags": list(features.quality.flags),
            "confidence_weight": features.quality.confidence_weight,
            "ball_observed": features.quality.ball_observed,
        },
        "gap": {
            "score_home": features.motion.gap_score_home,
            "score_away": features.motion.gap_score_away,
            "candidate_team": features.motion.gap_candidate_team,
            "decision": result.gap_decision,
            "decision_reason": result.gap_decision_reason,
        },
        "team": {
            "raw_team": raw_team.team,
            "raw_confidence": raw_team.confidence,
            "inference_team": result.inference.team_evidence.team,
            "inference_label": result.inference.label,
            "tag_relation": result.tag_relation,
        },
        "raw_dead": {
            "cues": list(raw_dead.cues),
            "confidence": raw_dead.confidence,
            "hard_evidence": raw_dead.hard_evidence,
            "dead_score": raw_dead.dead_score,
            "live_score": raw_dead.live_score,
            "confirmation_family": raw_dead.confirmation_family,
            "source": list(raw_dead.source),
            "validity": list(raw_dead.validity),
            "event_context": raw_dead.event_context,
            "live_counterevidence": list(raw_dead.live_counterevidence),
            "confirmable": raw_dead.confirmable,
        },
        "confirmed_dead": {
            "cues": list(result.inference.dead_ball_evidence.cues),
            "confidence": result.inference.dead_ball_evidence.confidence,
            "confirmed": result.inference.dead_ball_evidence.confirmed,
            "dead_score": result.inference.dead_ball_evidence.dead_score,
            "live_score": result.inference.dead_ball_evidence.live_score,
            "confirmation_family": result.inference.dead_ball_evidence.confirmation_family,
        },
        "emission": _emission_dict(result.emission),
    }


def trace_fixture(fixture: SyntheticFixture, possession_config: PossessionConfig = PossessionConfig(),
                  feature_config: E02Config = E02Config(), hmm_config: HMMConfig = HMMConfig()) -> SyntheticTrace:
    """Trace raw evidence, confirmations, emissions, Viterbi labels and spells."""
    frames = fixture.frames
    tags = list(iter_tag_evidence(fixture.events, len(frames)))
    features = list(iter_frame_features(frames, feature_config))
    raw = []
    for item, tag in zip(features, tags):
        team = _team_evidence(item, possession_config, feature_config, tag)
        raw.append((team, observe_dead_ball(item.frame, team, possession_config)))
    results = list(iter_infer_e02(frames, possession_config, feature_config, tag_evidence=tags))
    if len(results) != len(frames):
        raise ValueError("synthetic trace result count does not match fixture")
    rows = [_row(result, raw_team, raw_dead, tag)
            for result, (raw_team, raw_dead), tag in zip(results, raw, tags)]
    decoded = ["X"] * len(results)
    for half in (1, 2):
        indices = [index for index, result in enumerate(results) if result.emission.half == half]
        if not indices:
            continue
        labels, _ = decode([results[index].emission for index in indices], config=hmm_config)
        for index, label in zip(indices, labels):
            decoded[index] = label
    for row, label in zip(rows, decoded):
        row["decoded_label"] = label
    return SyntheticTrace(
        fixture.name, tuple(rows), tuple(decoded), tuple(possession_spells(decoded)),
        fixture.expectation_kind, fixture.expected, fixture.failure_signals,
    )


def trace_all() -> List[Dict[str, object]]:
    return [trace_fixture(fixture).as_dict() for fixture in fixture_catalog()]


def fixture_rule_coverage() -> Dict[str, List[str]]:
    coverage = {rule: [] for rule in ALL_RULES}
    for fixture in fixture_catalog():
        for rule in fixture.rule_ids:
            coverage[rule].append(fixture.name)
    return coverage
