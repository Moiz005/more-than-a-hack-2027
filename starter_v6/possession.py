"""Missing-aware, conservative E01 evidence fusion and temporal state inference.

This rule-based baseline separates observations (ball visibility and team proximity) from
inferences (H/A/D/X). It is deterministic and intentionally exposes its thresholds in config.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Iterable, Iterator, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class PlayerEvidence:
    team: str
    x_m: float
    y_m: float
    speed_mps: Optional[float] = None
    # Slot IDs identify observations within the ATD row only; they are not player identities.
    track_id: Optional[int] = None


@dataclass(frozen=True)
class FrameEvidence:
    frame: int
    half: int
    ball_xy: Optional[Tuple[float, float]]
    players: Tuple[PlayerEvidence, ...]
    ball_speed_mps: Optional[float] = None
    restart_context: bool = False
    # An observed restart action is distinct from the preceding award/context.
    # It never makes a frame dead by itself.
    restart_action: Optional[str] = None


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
    boundary_crossing_margin_m: float = 1.0
    boundary_disappearance_pre_frames: int = 13
    boundary_disappearance_min_missing_frames: int = 50
    micro_dead_filter: str = "off"
    micro_dead_short_min_frames: int = 38
    micro_dead_long_min_frames: int = 50

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
        for name in ("out_of_bounds_margin_m", "boundary_crossing_margin_m"):
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
            "boundary_disappearance_pre_frames", "boundary_disappearance_min_missing_frames",
            "micro_dead_short_min_frames", "micro_dead_long_min_frames",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError("{} must be a positive integer".format(name))
        if self.micro_dead_filter not in {"off", "short", "long"}:
            raise ValueError("micro_dead_filter must be off, short, or long")


@dataclass(frozen=True)
class TeamObservation:
    ball_observed: bool
    team: Optional[str]
    confidence: float
    nearest_home_m: Optional[float]
    nearest_away_m: Optional[float]
    margin_m: Optional[float]
    home_score: float = 0.0
    away_score: float = 0.0
    source: Tuple[str, ...] = ()


@dataclass(frozen=True)
class DeadBallObservation:
    cues: Tuple[str, ...]
    confidence: float
    confirmed: bool = False
    hard_evidence: bool = False
    source: Tuple[str, ...] = ()
    validity: Tuple[str, ...] = ()
    event_context: Optional[str] = None
    live_counterevidence: Tuple[str, ...] = ()
    confirmable: bool = True
    dead_score: float = 0.0
    live_score: float = 0.0
    confirmation_family: Optional[str] = None


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
        return TeamObservation(True, None, 0.0, None, None, None, 0.0, 0.0, ("proximity",))
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
    home_score = max(0.0, min(1.0, 1.0 - home / config.control_radius_m)) if home is not None else 0.0
    away_score = max(0.0, min(1.0, 1.0 - away / config.control_radius_m)) if away is not None else 0.0
    return TeamObservation(True, team, confidence, home, away, margin,
                          home_score, away_score, ("proximity",))


def observe_dead_ball(
    frame: FrameEvidence,
    team_observation: TeamObservation,
    config: PossessionConfig,
) -> DeadBallObservation:
    """Compute raw dead-ball cues independently of resolved team ownership.

    The returned object records observation provenance and counterevidence.  It is
    not a final state decision: callers still apply temporal confirmation.
    """
    _validate_frame(frame)
    if frame.ball_xy is None:
        return DeadBallObservation(
            (), 0.0, source=("ball_visibility",), validity=("ball_missing",),
            event_context="live_observation",
            live_score=0.15,
        )
    bx, by = frame.ball_xy
    margin = config.out_of_bounds_margin_m
    crossing = config.boundary_crossing_margin_m
    beyond_margin = (
        bx < -margin or bx > config.pitch_length_m + margin
        or by < -margin or by > config.pitch_width_m + margin
    )
    if beyond_margin:
        hard = (
            bx <= -crossing or bx >= config.pitch_length_m + crossing
            or by <= -crossing or by >= config.pitch_width_m + crossing
        )
        return DeadBallObservation(
            ("out_of_bounds",), 1.0 if hard else 0.65, False, hard,
            source=("ball_geometry",),
            validity=("coordinate_valid", "boundary_crossing" if hard else "boundary_candidate"),
            event_context="boundary_crossing",
            live_counterevidence=("nearby_team_control",) if team_observation.team else (),
            confirmable=hard,
            dead_score=1.0 if hard else 0.65,
            live_score=team_observation.confidence if team_observation.team else 0.0,
            confirmation_family="out_of_bounds",
        )

    # A restart action is the transition back to play, not a dead-ball cue.
    if frame.restart_action is not None:
        return DeadBallObservation(
            (), 0.0, source=("restart_action",), validity=("live_restart",),
            event_context="restart_action",
            live_counterevidence=("restart_action",),
            live_score=0.9,
        )
    if frame.ball_speed_mps is None:
        return DeadBallObservation(
            (), 0.0, source=("ball_motion",), validity=("ball_speed_missing",),
            event_context="live_observation",
            live_counterevidence=("team_control",) if team_observation.team else (),
            live_score=max(0.15, team_observation.confidence),
        )

    live_counterevidence = []
    if team_observation.team is not None:
        live_counterevidence.append("nearby_team_control")

    if frame.restart_context and frame.ball_speed_mps <= config.restart_ball_speed_max_mps:
        return DeadBallObservation(
            ("restart_stationary",), 0.75, source=("restart_context",),
            validity=("coordinate_valid", "stationary_ball"),
            event_context="restart_context",
            live_counterevidence=tuple(live_counterevidence),
            dead_score=0.75,
            live_score=team_observation.confidence if team_observation.team else 0.0,
            confirmation_family="restart_stationary",
        )

    if frame.ball_speed_mps > config.stationary_ball_speed_max_mps:
        return DeadBallObservation(
            (), 0.0, source=("ball_motion",), validity=("ball_moving",),
            event_context="live_motion", live_counterevidence=tuple(live_counterevidence),
            live_score=max(0.7, team_observation.confidence),
        )
    speeds = [player.speed_mps for player in frame.players if player.speed_mps is not None]
    if len(speeds) < config.min_players_for_motion:
        return DeadBallObservation(
            (), 0.0, source=("collective_motion",), validity=("insufficient_motion_tracks",),
            event_context="live_observation", live_counterevidence=tuple(live_counterevidence),
            live_score=max(0.15, team_observation.confidence),
        )
    stationary_fraction = sum(
        speed <= config.stationary_player_speed_max_mps for speed in speeds
    ) / float(len(speeds))
    if stationary_fraction >= config.stationary_player_fraction:
        return DeadBallObservation(
            ("stationary_context",), 0.55, source=("collective_motion",),
            validity=("coordinate_valid", "stationary_players"),
            event_context="motion_context", live_counterevidence=tuple(live_counterevidence),
            dead_score=0.55,
            live_score=team_observation.confidence if team_observation.team else 0.0,
            confirmation_family="stationary_context",
        )
    return DeadBallObservation(
        (), 0.0, source=("collective_motion",), validity=("players_moving",),
        event_context="live_motion", live_counterevidence=tuple(live_counterevidence),
        live_score=max(0.35, team_observation.confidence),
    )


@dataclass(frozen=True)
class RawPlayStateObservation:
    """A raw, traceable play-state observation before H/A/D/X inference."""

    frame: int
    half: int
    team_evidence: TeamObservation
    dead_ball_evidence: DeadBallObservation
    missing_frames: int
    boundary_context_age_frames: Optional[int]


def _boundary_distance(frame: FrameEvidence, config: PossessionConfig) -> Optional[float]:
    if frame.ball_xy is None:
        return None
    x, y = frame.ball_xy
    return min(x, config.pitch_length_m - x, y, config.pitch_width_m - y)


def iter_raw_play_state(
    frames: Iterable[FrameEvidence],
    config: PossessionConfig = PossessionConfig(),
) -> Iterator[RawPlayStateObservation]:
    """Yield raw cues with short boundary context and missing-ball duration.

    A near-boundary disappearance is a candidate only.  It is explicitly marked
    non-confirmable so missingness cannot become D without independent evidence.
    """
    previous_frame: Optional[int] = None
    previous_half: Optional[int] = None
    missing_frames = 0
    boundary_age: Optional[int] = None
    last_boundary_frame: Optional[int] = None
    for frame in frames:
        if previous_frame is not None and frame.frame != previous_frame + 1:
            raise ValueError("frames must be contiguous and ordered")
        if previous_half is not None and frame.half != previous_half:
            missing_frames = 0
            boundary_age = None
            last_boundary_frame = None
        previous_frame, previous_half = frame.frame, frame.half
        team = observe_team(frame, config)
        raw = observe_dead_ball(frame, team, config)
        distance = _boundary_distance(frame, config)
        if distance is not None and distance <= config.out_of_bounds_margin_m:
            last_boundary_frame = frame.frame
            boundary_age = 0
        elif last_boundary_frame is not None and frame.ball_xy is not None:
            boundary_age = frame.frame - last_boundary_frame
            if boundary_age > config.boundary_disappearance_pre_frames:
                last_boundary_frame = None
                boundary_age = None

        if frame.ball_xy is None:
            missing_frames += 1
            if (
                last_boundary_frame is not None
                and boundary_age is not None
                and missing_frames >= config.boundary_disappearance_min_missing_frames
            ):
                raw = DeadBallObservation(
                    ("near_boundary_disappearance",), 0.7, source=("visibility_gap", "boundary_context"),
                    validity=("ball_missing", "boundary_pre_context", "long_gap"),
                    event_context="boundary_disappearance",
                    live_counterevidence=("missing_ball",), confirmable=False,
                    dead_score=0.7, live_score=0.15,
                    confirmation_family="near_boundary_disappearance",
                )
        else:
            missing_frames = 0
        yield RawPlayStateObservation(
            frame.frame, frame.half, team, raw, missing_frames, boundary_age,
        )


def confirm_dead_ball(
    raw: DeadBallObservation,
    previous_family: Optional[str],
    previous_count: int,
    config: PossessionConfig,
) -> Tuple[bool, Optional[str], int]:
    """Advance one cue-specific confirmation stream.

    A family switch starts a new hypothesis; unrelated weak cues never share a
    persistence counter. Hard physical evidence confirms immediately.
    """
    if raw.hard_evidence:
        return True, None, 0
    if not raw.cues or not raw.confirmable:
        return False, None, 0
    family = raw.confirmation_family or raw.cues[0]
    count = previous_count + 1 if family == previous_family else 1
    return count >= config.deadball_confirm_frames, family, count


def finalize_dead_ball(raw: DeadBallObservation, confirmed: bool) -> DeadBallObservation:
    """Copy raw evidence into the inferred observation without losing provenance."""
    return DeadBallObservation(
        raw.cues, raw.confidence, confirmed, raw.hard_evidence,
        raw.source, raw.validity, raw.event_context, raw.live_counterevidence,
        raw.confirmable, raw.dead_score, raw.live_score, raw.confirmation_family,
    )


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
    dead_candidate_family: Optional[str] = None

    for frame in frames:
        if previous_frame is not None and frame.frame != previous_frame + 1:
            raise ValueError("frames must be contiguous and ordered")
        previous_frame = frame.frame
        if previous_half is not None and frame.half != previous_half:
            state = "X"
            missing_count = uncertain_count = candidate_count = dead_candidate_count = 0
            dead_candidate_family = None
            candidate_team = None
        previous_half = frame.half

        team_evidence = observe_team(frame, config)
        raw_deadball = observe_dead_ball(frame, team_evidence, config)
        if frame.half == 0:
            state = "X"
            missing_count = uncertain_count = candidate_count = dead_candidate_count = 0
            dead_candidate_family = None
            candidate_team = None
            yield FrameInference(
                frame.frame, frame.half, "X", team_evidence,
                finalize_dead_ball(raw_deadball, False),
            )
            continue

        confirmed_deadball, dead_candidate_family, dead_candidate_count = confirm_dead_ball(
            raw_deadball, dead_candidate_family, dead_candidate_count, config,
        )
        dead_evidence = finalize_dead_ball(raw_deadball, confirmed_deadball)
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
    return apply_micro_dead_filter(list(iter_infer_possession(frames, config)), config)


def apply_micro_dead_filter(
    results: Sequence[FrameInference], config: PossessionConfig,
) -> List[FrameInference]:
    """Apply an optional synthetic R15 duration hypothesis to confirmed D runs.

    The default is ``off``.  ``short`` and ``long`` use 1.5 s (38 frames) and
    2.0 s (50 frames) at 25 FPS respectively. Hard structural evidence is
    preserved regardless of the selected hypothesis.
    """
    if config.micro_dead_filter == "off":
        return list(results)
    minimum = (config.micro_dead_short_min_frames if config.micro_dead_filter == "short"
               else config.micro_dead_long_min_frames)
    filtered = list(results)
    index = 0
    while index < len(filtered):
        if filtered[index].label != "D":
            index += 1
            continue
        start = index
        half = filtered[index].half
        hard = False
        while index < len(filtered) and filtered[index].label == "D" and filtered[index].half == half:
            hard = hard or filtered[index].dead_ball_evidence.hard_evidence
            index += 1
        if hard or index - start >= minimum:
            continue
        previous = filtered[start - 1].label if start > 0 and filtered[start - 1].half == half else "X"
        following = filtered[index].label if index < len(filtered) and filtered[index].half == half else "X"
        replacement = previous if previous in {"H", "A"} else following
        for position in range(start, index):
            item = filtered[position]
            filtered[position] = replace(
                item, label=replacement,
                dead_ball_evidence=replace(item.dead_ball_evidence, confirmed=False),
            )
    return filtered


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
