"""Missing-aware, conservative E01 evidence fusion and temporal state inference.

This rule-based baseline separates observations (ball visibility and team proximity) from
inferences (H/A/D/X). It is deterministic and intentionally exposes its thresholds in config.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Iterator, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class PlayerEvidence:
    team: str
    x_m: float
    y_m: float
    speed_mps: Optional[float] = None


@dataclass(frozen=True)
class FrameEvidence:
    frame: int
    half: int
    ball_xy: Optional[Tuple[float, float]]
    players: Tuple[PlayerEvidence, ...]
    ball_speed_mps: Optional[float] = None
    restart_context: bool = False


@dataclass(frozen=True)
class PossessionConfig:
    control_radius_m: float = 1.5
    min_team_margin_m: float = 0.5
    min_observation_confidence: float = 0.6
    acquire_frames: int = 3
    max_missing_frames: int = 25
    max_uncertain_frames: int = 12
    pitch_length_m: float = 105.3
    pitch_width_m: float = 68.0
    out_of_bounds_margin_m: float = 0.5
    restart_ball_speed_max_mps: float = 0.5
    stationary_ball_speed_max_mps: float = 0.25
    stationary_player_speed_max_mps: float = 0.4
    min_players_for_motion: int = 8
    stationary_player_fraction: float = 0.8
    deadball_confirm_frames: int = 2
    contradiction_confidence: float = 0.8

    def __post_init__(self) -> None:
        positive = (
            "control_radius_m", "min_team_margin_m", "pitch_length_m", "pitch_width_m",
            "restart_ball_speed_max_mps", "stationary_ball_speed_max_mps",
            "stationary_player_speed_max_mps",
        )
        for name in positive:
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError("{} must be finite and positive".format(name))
        for name in ("out_of_bounds_margin_m",):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0:
                raise ValueError("{} must be finite and non-negative".format(name))
        for name in ("min_observation_confidence", "stationary_player_fraction", "contradiction_confidence"):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("{} must be in [0, 1]".format(name))
        for name in (
            "acquire_frames", "max_missing_frames", "max_uncertain_frames",
            "min_players_for_motion", "deadball_confirm_frames",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError("{} must be a positive integer".format(name))


@dataclass(frozen=True)
class TeamObservation:
    ball_observed: bool
    team: Optional[str]
    confidence: float
    nearest_home_m: Optional[float]
    nearest_away_m: Optional[float]
    margin_m: Optional[float]


@dataclass(frozen=True)
class DeadBallObservation:
    cues: Tuple[str, ...]
    confidence: float
    confirmed: bool = False
    hard_evidence: bool = False


@dataclass(frozen=True)
class FrameInference:
    frame: int
    half: int
    label: str
    team_evidence: TeamObservation
    dead_ball_evidence: DeadBallObservation


def _validate_frame(frame: FrameEvidence) -> None:
    if frame.frame < 0 or frame.half not in {0, 1, 2}:
        raise ValueError("frame must be non-negative and half must be 0, 1, or 2")
    if frame.ball_xy is not None:
        if len(frame.ball_xy) != 2 or any(not math.isfinite(float(value)) for value in frame.ball_xy):
            raise ValueError("ball coordinates must be finite or absent")
    if frame.ball_speed_mps is not None:
        if not math.isfinite(frame.ball_speed_mps) or frame.ball_speed_mps < 0:
            raise ValueError("ball speed must be finite and non-negative or absent")
    for player in frame.players:
        if player.team not in {"H", "A"}:
            raise ValueError("player team must be H or A")
        if not math.isfinite(player.x_m) or not math.isfinite(player.y_m):
            raise ValueError("player coordinates must be finite")
        if player.speed_mps is not None and (
            not math.isfinite(player.speed_mps) or player.speed_mps < 0
        ):
            raise ValueError("player speed must be finite and non-negative or absent")


def observe_team(frame: FrameEvidence, config: PossessionConfig) -> TeamObservation:
    """Return team/unknown evidence from nearest-team distance and between-team margin."""
    _validate_frame(frame)
    if frame.ball_xy is None:
        return TeamObservation(False, None, 0.0, None, None, None)

    bx, by = frame.ball_xy
    nearest = {"H": None, "A": None}
    for player in frame.players:
        distance = math.hypot(player.x_m - bx, player.y_m - by)
        previous = nearest[player.team]
        if previous is None or distance < previous:
            nearest[player.team] = distance
    home, away = nearest["H"], nearest["A"]
    if home is None and away is None:
        return TeamObservation(True, None, 0.0, None, None, None)
    if away is None:
        best_team, best_distance, margin, separated = "H", home, None, True
    elif home is None:
        best_team, best_distance, margin, separated = "A", away, None, True
    elif home <= away:
        best_team, best_distance, margin = "H", home, away - home
        separated = margin >= config.min_team_margin_m
    else:
        best_team, best_distance, margin = "A", away, home - away
        separated = margin >= config.min_team_margin_m

    if best_distance is None or best_distance > config.control_radius_m:
        confidence = 0.0
        team = None
    else:
        proximity = max(0.0, min(1.0, 1.0 - best_distance / config.control_radius_m))
        separation = 1.0 if margin is None else max(
            0.0, min(1.0, margin / config.min_team_margin_m)
        )
        confidence = 0.5 * (proximity + separation)
        team = best_team if separated and confidence >= config.min_observation_confidence else None
    return TeamObservation(True, team, confidence, home, away, margin)


def observe_dead_ball(
    frame: FrameEvidence,
    team_observation: TeamObservation,
    config: PossessionConfig,
) -> DeadBallObservation:
    """Compute independent dead-ball cues; a missing ball or tag alone is never sufficient."""
    if frame.ball_xy is None:
        return DeadBallObservation((), 0.0)
    bx, by = frame.ball_xy
    margin = config.out_of_bounds_margin_m
    outside = (
        bx < -margin or bx > config.pitch_length_m + margin
        or by < -margin or by > config.pitch_width_m + margin
    )
    if outside:
        return DeadBallObservation(("out_of_bounds",), 1.0, True, hard_evidence=True)

    if team_observation.team is not None or frame.ball_speed_mps is None:
        return DeadBallObservation((), 0.0)

    if frame.restart_context and frame.ball_speed_mps <= config.restart_ball_speed_max_mps:
        return DeadBallObservation(("restart_stationary",), 0.75)

    if frame.ball_speed_mps > config.stationary_ball_speed_max_mps:
        return DeadBallObservation((), 0.0)
    speeds = [player.speed_mps for player in frame.players if player.speed_mps is not None]
    if len(speeds) < config.min_players_for_motion:
        return DeadBallObservation((), 0.0)
    stationary_fraction = sum(
        speed <= config.stationary_player_speed_max_mps for speed in speeds
    ) / float(len(speeds))
    if stationary_fraction >= config.stationary_player_fraction:
        return DeadBallObservation(("stationary_context",), 0.55)
    return DeadBallObservation((), 0.0)


def iter_infer_possession(
    frames: Iterable[FrameEvidence],
    config: PossessionConfig = PossessionConfig(),
) -> Iterator[FrameInference]:
    """Infer labels in one pass, resetting all temporal state at each half boundary."""
    state = "X"
    previous_half: Optional[int] = None
    previous_frame: Optional[int] = None
    missing_count = uncertain_count = 0
    candidate_team: Optional[str] = None
    candidate_count = dead_candidate_count = 0

    for frame in frames:
        if previous_frame is not None and frame.frame != previous_frame + 1:
            raise ValueError("frames must be contiguous and ordered")
        previous_frame = frame.frame
        if previous_half is not None and frame.half != previous_half:
            state = "X"
            missing_count = uncertain_count = candidate_count = dead_candidate_count = 0
            candidate_team = None
        previous_half = frame.half

        team_evidence = observe_team(frame, config)
        raw_deadball = observe_dead_ball(frame, team_evidence, config)
        if frame.half == 0:
            state = "X"
            missing_count = uncertain_count = candidate_count = dead_candidate_count = 0
            candidate_team = None
            yield FrameInference(
                frame.frame, frame.half, "X", team_evidence,
                DeadBallObservation(raw_deadball.cues, raw_deadball.confidence, False, raw_deadball.hard_evidence),
            )
            continue

        if raw_deadball.hard_evidence:
            confirmed_deadball = True
            dead_candidate_count = 0
        elif raw_deadball.cues:
            dead_candidate_count += 1
            confirmed_deadball = dead_candidate_count >= config.deadball_confirm_frames
        else:
            dead_candidate_count = 0
            confirmed_deadball = False

        dead_evidence = DeadBallObservation(
            raw_deadball.cues, raw_deadball.confidence, confirmed_deadball, raw_deadball.hard_evidence
        )
        if confirmed_deadball:
            state = "D"
            missing_count = uncertain_count = candidate_count = 0
            candidate_team = None
            yield FrameInference(frame.frame, frame.half, "D", team_evidence, dead_evidence)
            continue

        if not team_evidence.ball_observed:
            missing_count += 1
            uncertain_count = candidate_count = 0
            candidate_team = None
            if missing_count > config.max_missing_frames:
                state = "X"
            label = state if state in {"H", "A"} else "X"
            yield FrameInference(frame.frame, frame.half, label, team_evidence, dead_evidence)
            continue

        missing_count = 0
        if team_evidence.team is None:
            uncertain_count += 1
            candidate_count = 0
            candidate_team = None
            if uncertain_count > config.max_uncertain_frames:
                state = "X"
            label = state if state in {"H", "A"} else "X"
            yield FrameInference(frame.frame, frame.half, label, team_evidence, dead_evidence)
            continue

        uncertain_count = 0
        observed_team = team_evidence.team
        if observed_team == state:
            candidate_team = None
            candidate_count = 0
        elif observed_team == candidate_team:
            candidate_count += 1
        else:
            candidate_team = observed_team
            candidate_count = 1
        if observed_team != state and candidate_count >= config.acquire_frames:
            state = observed_team
            candidate_team = None
            candidate_count = 0
        label = state if state in {"H", "A"} else "X"
        yield FrameInference(frame.frame, frame.half, label, team_evidence, dead_evidence)


def infer_possession(
    frames: Iterable[FrameEvidence],
    config: PossessionConfig = PossessionConfig(),
) -> List[FrameInference]:
    """Convenience materialization for synthetic tests; production CLI uses the iterator."""
    return list(iter_infer_possession(frames, config))


def possession_spells(labels: Sequence[str]) -> List[Tuple[str, int, int]]:
    """Return inclusive maximal H/A runs; D and X split possession spells."""
    spells: List[Tuple[str, int, int]] = []
    index = 0
    while index < len(labels):
        team = labels[index]
        if team not in {"H", "A"}:
            index += 1
            continue
        end = index
        while end + 1 < len(labels) and labels[end + 1] == team:
            end += 1
        spells.append((team, index, end))
        index = end + 1
    return spells
