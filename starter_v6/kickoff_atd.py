"""Quality-aware tactical ATD kickoff-execution detection for HBK-01.

The detector is deliberately narrow: Smart Tagging supplies only a bounded
search context, while this module requires a reliable centre setup followed by
consecutive, physically plausible observed ball motion. It never emits
submission labels or converts kickoff context into team possession.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

from starter_v6.ingestion import ATDFrame, ATDMetadata, Observation
from starter_v6.timeline import TacticalTimeline, validate_atd_frame_mapping
from starter_v6.kickoff_tags import KickoffTagCandidate, MISSING_TAG


CONFIRMED = "CONFIRMED"
AMBIGUOUS = "AMBIGUOUS"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
INVALID_ALIGNMENT = "INVALID_ALIGNMENT"


@dataclass(frozen=True)
class KickoffATDConfig:
    """Untuned, physically motivated detector hypotheses.

    Distances are metres and speeds are metres per second. The defaults are
    engineering hypotheses for synthetic testing, not values selected from
    the supplied match or its public labels.
    """

    fps: int = 25
    centre_setup_radius_m: float = 2.5
    stationary_jitter_m: float = 0.20
    stationary_max_speed_mps: float = 0.75
    stable_preparation_frames: int = 3
    min_movement_displacement_m: float = 0.20
    max_movement_speed_mps: float = 35.0
    max_provider_speed_error_mps: float = 12.0
    movement_confirmation_frames: int = 2
    nearby_player_radius_m: float = 3.0
    max_confirmed_candidates: int = 8

    def __post_init__(self) -> None:
        if isinstance(self.fps, bool) or not isinstance(self.fps, int) or self.fps <= 0:
            raise ValueError("fps must be a positive integer")
        for name in (
            "centre_setup_radius_m", "stationary_jitter_m",
            "stationary_max_speed_mps", "min_movement_displacement_m",
            "max_movement_speed_mps", "max_provider_speed_error_mps",
            "nearby_player_radius_m",
        ):
            value = getattr(self, name)
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or value <= 0):
                raise ValueError("{} must be finite and positive".format(name))
        for name in ("stable_preparation_frames", "movement_confirmation_frames", "max_confirmed_candidates"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError("{} must be a positive integer".format(name))
        if self.max_movement_speed_mps < self.min_movement_displacement_m * self.fps:
            raise ValueError("max_movement_speed_mps is below one-frame minimum movement")


@dataclass(frozen=True)
class KickoffExecutionCandidate:
    """One candidate start frame and its local quality evidence."""

    execution_frame: int
    displacement_m: float
    derived_speed_mps: float
    provider_speed_mps: Optional[float]
    evidence: Tuple[str, ...]


@dataclass(frozen=True)
class KickoffDetectionResult:
    """Auditable detector result; execution is present only when unambiguous."""

    status: str
    execution_frame: Optional[int]
    video_timestamp_seconds: Optional[float]
    reasons: Tuple[str, ...]
    candidates: Tuple[KickoffExecutionCandidate, ...]
    evaluated_frames: int


def distance_to_centre_m(ball: Observation, metadata: ATDMetadata) -> Optional[float]:
    """Return metric distance from an observed ball position to pitch centre."""
    if not ball.valid:
        return None
    if not all(math.isfinite(value) for value in (ball.x_m, ball.y_m)):
        return None
    centre_x = metadata.pitch_length_m / 2.0
    centre_y = metadata.pitch_width_m / 2.0
    return math.hypot(ball.x_m - centre_x, ball.y_m - centre_y)


def _valid_pitch_dimensions(metadata: ATDMetadata) -> bool:
    return (
        math.isfinite(metadata.pitch_length_m) and metadata.pitch_length_m > 0
        and math.isfinite(metadata.pitch_width_m) and metadata.pitch_width_m > 0
    )


def _observed_ball(ball: Observation, metadata: ATDMetadata) -> Tuple[Optional[Tuple[float, float]], bool]:
    """Return metric coordinates and whether a finite position is invalid."""
    if not ball.valid:
        return None, False
    if not all(math.isfinite(value) for value in (ball.x_m, ball.y_m)):
        return None, True
    if not (0.0 <= ball.x_m <= metadata.pitch_length_m
            and 0.0 <= ball.y_m <= metadata.pitch_width_m):
        return None, True
    return (ball.x_m, ball.y_m), False


def _nearby_player(frame: ATDFrame, ball_xy: Tuple[float, float], metadata: ATDMetadata,
                   radius_m: float) -> bool:
    for observation in frame.players:
        if not observation.valid:
            continue
        if not all(math.isfinite(value) for value in (observation.x_m, observation.y_m)):
            continue
        if math.hypot(observation.x_m - ball_xy[0], observation.y_m - ball_xy[1]) <= radius_m:
            return True
    return False


def _result(status: str, reasons: Sequence[str], candidates: Sequence[KickoffExecutionCandidate],
            evaluated_frames: int, fps: int) -> KickoffDetectionResult:
    unique_reasons = tuple(dict.fromkeys(reasons))
    ordered_candidates = tuple(candidates)
    execution_frame = ordered_candidates[0].execution_frame if status == CONFIRMED else None
    timestamp = execution_frame / float(fps) if execution_frame is not None else None
    return KickoffDetectionResult(
        status=status,
        execution_frame=execution_frame,
        video_timestamp_seconds=timestamp,
        reasons=unique_reasons,
        candidates=ordered_candidates,
        evaluated_frames=evaluated_frames,
    )


def detect_kickoff_execution(
    frames: Iterable[ATDFrame],
    metadata: ATDMetadata,
    candidate: KickoffTagCandidate,
    timeline: Optional[TacticalTimeline] = None,
    config: KickoffATDConfig = KickoffATDConfig(),
) -> KickoffDetectionResult:
    """Detect the first credible kick inside one bounded tag search window.

    The input is consumed in order and raw ATD frames are never modified. The
    evaluator requires the complete contiguous search window from the strict
    ATD iterator; a skipped row is an alignment failure, not an interpolated
    velocity. Missing ball observations reset preparation and motion state.
    """
    if not _valid_pitch_dimensions(metadata):
        return _result(INVALID_ALIGNMENT, ("invalid_pitch_dimensions",), (), 0, config.fps)
    if not candidate.eligible:
        return _result(MISSING_TAG, tuple(candidate.warnings) or ("candidate_not_eligible",), (), 0, config.fps)
    if candidate.half not in {1, 2} or candidate.search_start_frame is None or candidate.search_end_frame is None:
        return _result(INVALID_ALIGNMENT, ("invalid_alignment",), (), 0, config.fps)
    search_start = candidate.search_start_frame
    search_end = candidate.search_end_frame
    if search_start < 0 or search_end <= search_start:
        return _result(INVALID_ALIGNMENT, ("invalid_alignment",), (), 0, config.fps)
    if timeline is not None:
        if search_end > timeline.frame_count or len(timeline.half_by_frame) != timeline.frame_count:
            return _result(INVALID_ALIGNMENT, ("invalid_alignment",), (), 0, config.fps)

    reasons: List[str] = []
    candidates: List[KickoffExecutionCandidate] = []
    evaluated = 0
    first_evaluated: Optional[int] = None
    previous_evaluated: Optional[int] = None
    previous_xy: Optional[Tuple[float, float]] = None
    previous_frame: Optional[ATDFrame] = None
    stable_positions: List[Tuple[int, Tuple[float, float]]] = []
    pending_frame: Optional[int] = None
    pending_run = 0
    pending_evidence: Tuple[str, ...] = ()
    pending_displacement: Optional[float] = None
    pending_speed: Optional[float] = None
    pending_provider_speed: Optional[float] = None

    for raw in frames:
        try:
            validate_atd_frame_mapping(raw.frame_id, raw.video_frame)
        except ValueError:
            return _result(INVALID_ALIGNMENT, reasons + ["invalid_alignment"], candidates, evaluated, config.fps)
        frame_number = raw.video_frame
        if frame_number < search_start:
            continue
        if frame_number >= search_end:
            break
        if first_evaluated is None:
            first_evaluated = frame_number
            if frame_number != search_start:
                return _result(INVALID_ALIGNMENT, reasons + ["invalid_alignment"], candidates, evaluated, config.fps)
        elif frame_number != previous_evaluated + 1:
            return _result(INVALID_ALIGNMENT, reasons + ["invalid_alignment"], candidates, evaluated, config.fps)
        if timeline is not None:
            marker = timeline.half_by_frame[frame_number]
            if marker not in {0, candidate.half}:
                return _result(INVALID_ALIGNMENT, reasons + ["invalid_alignment"], candidates, evaluated, config.fps)

        evaluated += 1
        ball_xy, invalid_position = _observed_ball(raw.ball, metadata)
        if ball_xy is None:
            if invalid_position:
                reasons.append("quality_rejected_jump")
            else:
                reasons.append("ball_missing")
            stable_positions = []
            pending_frame = None
            pending_run = 0
            pending_evidence = ()
            previous_xy = None
            previous_frame = raw
            previous_evaluated = frame_number
            continue

        consecutive = (
            previous_evaluated is not None and frame_number == previous_evaluated + 1
            and previous_xy is not None and previous_frame is not None
        )
        displacement = math.hypot(ball_xy[0] - previous_xy[0], ball_xy[1] - previous_xy[1]) if consecutive else None
        derived_speed = displacement * config.fps if displacement is not None else None
        provider_speed = raw.ball.speed_mps if raw.ball.speed_valid and math.isfinite(raw.ball.speed_mps) else None
        plausible_motion = bool(
            displacement is not None
            and config.min_movement_displacement_m <= displacement
            and derived_speed is not None
            and derived_speed <= config.max_movement_speed_mps
        )
        if plausible_motion and provider_speed is not None:
            if abs(provider_speed - derived_speed) > config.max_provider_speed_error_mps:
                plausible_motion = False
                reasons.append("quality_rejected_jump")
                reasons.append("ball_speed_contradiction")
        elif displacement is not None and derived_speed > config.max_movement_speed_mps:
            reasons.append("quality_rejected_jump")

        prepared_before = len(stable_positions) >= config.stable_preparation_frames
        if pending_frame is not None:
            if plausible_motion:
                pending_run += 1
                if pending_run >= config.movement_confirmation_frames:
                    candidates.append(KickoffExecutionCandidate(
                        execution_frame=pending_frame,
                        displacement_m=float(pending_displacement),
                        derived_speed_mps=float(pending_speed),
                        provider_speed_mps=pending_provider_speed,
                        evidence=pending_evidence,
                    ))
                    reasons.extend(pending_evidence)
                    if len(candidates) >= config.max_confirmed_candidates:
                        reasons.append("multiple_motion_candidates")
                        return _result(AMBIGUOUS, reasons, candidates, evaluated, config.fps)
                    pending_frame = None
                    pending_run = 0
                    pending_evidence = ()
                    pending_displacement = None
                    pending_speed = None
                    pending_provider_speed = None
                    stable_positions = []
            else:
                pending_frame = None
                pending_run = 0
                pending_evidence = ()
                pending_displacement = None
                pending_speed = None
                pending_provider_speed = None
                stable_positions = []

        if pending_frame is None and plausible_motion and prepared_before:
            evidence = ["consecutive_ball_motion"]
            if any(
                math.hypot(player.x_m - ball_xy[0], player.y_m - ball_xy[1]) <= config.nearby_player_radius_m
                for player in raw.players if player.valid
            ):
                evidence.append("nearby_player")
            if config.movement_confirmation_frames == 1:
                candidates.append(KickoffExecutionCandidate(
                    execution_frame=frame_number,
                    displacement_m=float(displacement),
                    derived_speed_mps=float(derived_speed),
                    provider_speed_mps=provider_speed,
                    evidence=tuple(evidence),
                ))
                reasons.extend(evidence)
                stable_positions = []
            else:
                pending_frame = frame_number
                pending_run = 1
                pending_evidence = tuple(evidence)
                pending_displacement = displacement
                pending_speed = derived_speed
                pending_provider_speed = provider_speed

        distance = distance_to_centre_m(raw.ball, metadata)
        stationary = bool(
            distance is not None and distance <= config.centre_setup_radius_m
            and (not consecutive or displacement is None or displacement <= config.stationary_jitter_m)
            and (provider_speed is None or provider_speed <= config.stationary_max_speed_mps)
        )
        if stationary and pending_frame is None:
            if consecutive and stable_positions and stable_positions[-1][0] == frame_number - 1:
                stable_positions.append((frame_number, ball_xy))
            else:
                stable_positions = [(frame_number, ball_xy)]
            reasons.append("centre_setup")
            if len(stable_positions) >= config.stable_preparation_frames:
                reasons.append("stationary_preparation")
        elif pending_frame is None:
            stable_positions = []

        previous_xy = ball_xy
        previous_frame = raw
        previous_evaluated = frame_number

    if len(candidates) > 1:
        reasons.append("multiple_motion_candidates")
        return _result(AMBIGUOUS, reasons, candidates, evaluated, config.fps)
    if len(candidates) == 1:
        return _result(CONFIRMED, reasons, candidates, evaluated, config.fps)
    if not reasons:
        reasons.append("insufficient_evidence")
    return _result(INSUFFICIENT_EVIDENCE, reasons, candidates, evaluated, config.fps)


__all__ = [
    "AMBIGUOUS",
    "CONFIRMED",
    "INSUFFICIENT_EVIDENCE",
    "INVALID_ALIGNMENT",
    "KickoffATDConfig",
    "KickoffDetectionResult",
    "KickoffExecutionCandidate",
    "distance_to_centre_m",
    "detect_kickoff_execution",
]
