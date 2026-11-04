"""Conservative, non-labeling temporal hypotheses derived from tactical ATD.

Outputs here describe support or uncertainty. They never emit possession or DEAD
labels and are intentionally not consumed by the production decoder.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Optional, Tuple

from starter_v6.features import FrameFeatures


@dataclass(frozen=True)
class AtdSignalConfig:
    pitch_length_m: float = 105.3
    pitch_width_m: float = 68.0
    control_radius_m: float = 1.5
    control_margin_m: float = 0.75
    rapid_motion_speed_mps: float = 8.0
    control_persistence_frames: int = 3
    minimum_control_quality: float = 0.6
    minimum_comotion_cosine: float = 0.35
    stationary_speed_mps: float = 0.35
    restart_motion_speed_mps: float = 1.5
    restart_motion_frames: int = 2
    restart_setup_max_age_frames: int = 75
    boundary_tolerance_m: float = 0.75

    def __post_init__(self) -> None:
        for name in ("pitch_length_m", "pitch_width_m", "control_radius_m", "control_margin_m", "rapid_motion_speed_mps", "stationary_speed_mps", "restart_motion_speed_mps", "boundary_tolerance_m"):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError("{} must be finite and positive".format(name))
        for name in ("control_persistence_frames", "restart_motion_frames", "restart_setup_max_age_frames"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError("{} must be a positive integer".format(name))
        for name in ("minimum_control_quality", "minimum_comotion_cosine"):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("{} must be finite and in [0, 1]".format(name))


@dataclass(frozen=True)
class ControlSupport:
    candidate_team: Optional[str]
    persistent_frames: int
    proximity_supported: bool
    comotion_supported: bool
    contradictory_opponent_control: bool
    confidence: float
    uncertainty: float


@dataclass(frozen=True)
class BoundaryProposal:
    candidate: bool
    boundary: Optional[str]
    confidence: float
    uncertainty: float
    reason: str


@dataclass(frozen=True)
class BallMotionEvidence:
    rapid_uncontrolled_motion: bool
    observed_speed_mps: Optional[float]
    confidence: float
    uncertainty: float
    reason: str


@dataclass(frozen=True)
class RestartMotionProposal:
    candidate: bool
    supported_motion_frames: int
    restart_context: bool
    confidence: float
    uncertainty: float
    reason: str


@dataclass(frozen=True)
class AtdSignals:
    frame: int
    half: int
    ball_position_observed: bool
    ball_position_provenance: str
    provider_speed_mps: Optional[float]
    derived_speed_mps: Optional[float]
    stationary_state: str
    control: ControlSupport
    ball_motion: BallMotionEvidence
    boundary: BoundaryProposal
    restart_motion: RestartMotionProposal


def iter_atd_signals(
    frames: Iterable[FrameFeatures], config: AtdSignalConfig = AtdSignalConfig()
) -> Tuple[AtdSignals, ...]:
    """Build bounded hypotheses using only observed tactical frames.

    Input frame features must be contiguous and ordered. Missing coordinates and
    half boundaries reset temporal support; no position or control is carried
    forward to fill a gap.
    """
    output = []
    previous: Optional[FrameFeatures] = None
    control_team: Optional[str] = None
    control_run = 0
    restart_setup_seen = False
    restart_setup_frame: Optional[int] = None
    restart_motion_run = 0
    for current in frames:
        raw = current.frame
        contiguous = previous is not None and raw.half == previous.frame.half and raw.frame == previous.frame.frame + 1
        if not contiguous:
            control_team, control_run = None, 0
            restart_setup_seen, restart_setup_frame, restart_motion_run = False, None, 0

        ball_observed = raw.ball_xy is not None
        derived_speed = current.motion.derived_ball_speed_mps
        provider_speed = current.motion.provider_ball_speed_mps
        if not ball_observed:
            stationary = "unknown_missing_ball"
        else:
            known_speeds = [value for value in (derived_speed, provider_speed) if value is not None]
            speed_conflict = current.quality.ball_speed_inconsistent
            stationary_observed = bool(known_speeds) and max(known_speeds) <= config.stationary_speed_mps
            stationary = (
                "stationary_speed_conflict" if speed_conflict else
                "stationary_setup_candidate" if raw.restart_context and stationary_observed else
                "stationary_live_or_unresolved" if stationary_observed else
                "moving_or_unresolved"
            )
        if raw.restart_context and stationary == "stationary_setup_candidate":
            restart_setup_seen = True
            restart_setup_frame = raw.frame
        if raw.ball_xy is None or not raw.restart_context:
            restart_setup_seen, restart_setup_frame = False, None

        nearest_h, nearest_a = current.spatial.nearest_home_m, current.spatial.nearest_away_m
        candidate = None
        if ball_observed and nearest_h is not None and nearest_a is not None:
            if nearest_h <= config.control_radius_m and nearest_a - nearest_h >= config.control_margin_m:
                candidate = "H"
            elif nearest_a <= config.control_radius_m and nearest_h - nearest_a >= config.control_margin_m:
                candidate = "A"
        quality_ok = current.quality.confidence_weight >= config.minimum_control_quality
        if candidate is not None and quality_ok:
            control_run = control_run + 1 if contiguous and candidate == control_team else 1
            control_team = candidate
        else:
            control_team, control_run = None, 0
        cosine = (
            current.motion.home_ball_comotion if candidate == "H" else
            current.motion.away_ball_comotion if candidate == "A" else None
        )
        comotion = cosine is not None and cosine >= config.minimum_comotion_cosine
        persistent_control = control_run >= config.control_persistence_frames
        contradictory = bool(
            nearest_h is not None and nearest_a is not None
            and nearest_h <= config.control_radius_m and nearest_a <= config.control_radius_m
        )
        control = ControlSupport(
            candidate if persistent_control and comotion and not contradictory else None,
            control_run if quality_ok else 0,
            bool(candidate and quality_ok), comotion, contradictory,
            min(1.0, current.quality.confidence_weight * (0.5 + 0.5 * min(control_run, config.control_persistence_frames) / config.control_persistence_frames))
            if candidate and quality_ok else 0.0,
            1.0 if not candidate or not quality_ok else 0.35 if persistent_control and comotion and not contradictory else 0.7,
        )

        boundary_name = None
        boundary_reason = "no_supported_boundary_transition"
        if contiguous and previous is not None and raw.ball_xy is not None and previous.frame.ball_xy is not None:
            px, py = previous.frame.ball_xy
            x, y = raw.ball_xy
            inside_before = 0.0 <= px <= config.pitch_length_m and 0.0 <= py <= config.pitch_width_m
            outside_now = (
                -config.boundary_tolerance_m <= x <= config.pitch_length_m + config.boundary_tolerance_m
                and (y < 0 or y > config.pitch_width_m)
            ) or (
                -config.boundary_tolerance_m <= y <= config.pitch_width_m + config.boundary_tolerance_m
                and (x < 0 or x > config.pitch_length_m)
            )
            clean_motion = not current.quality.implausible_ball_jump and not current.quality.ball_speed_inconsistent
            if inside_before and outside_now and clean_motion:
                boundary_name = "touchline_hypothesis" if y < 0 or y > config.pitch_width_m else "goal_line_hypothesis"
                boundary_reason = "consecutive_observed_positions_near_pitch_boundary"
        boundary = BoundaryProposal(boundary_name is not None, boundary_name, 0.35 if boundary_name else 0.0, 0.65 if boundary_name else 1.0, boundary_reason)

        rapid = bool(
            derived_speed is not None and derived_speed >= config.rapid_motion_speed_mps
            and not current.quality.implausible_ball_jump
            and not current.quality.ball_speed_inconsistent
        )
        has_near_controller = bool(
            (nearest_h is not None and nearest_h <= config.control_radius_m)
            or (nearest_a is not None and nearest_a <= config.control_radius_m)
        )
        flight_like = rapid and ball_observed and not has_near_controller
        ball_motion = BallMotionEvidence(
            flight_like, derived_speed if ball_observed else None,
            0.25 if flight_like else 0.0, 0.75 if flight_like else 1.0,
            "rapid_ball_motion_without_near_controller" if flight_like else "flight_or_loose_state_unresolved",
        )

        moving = bool(
            derived_speed is not None and derived_speed >= config.restart_motion_speed_mps
            and not current.quality.implausible_ball_jump
            and not current.quality.ball_speed_inconsistent
        )
        if raw.ball_xy is None:
            restart_motion_run = 0
        elif moving:
            restart_motion_run = restart_motion_run + 1 if contiguous else 1
        else:
            restart_motion_run = 0
        setup_recent = (
            restart_setup_seen and restart_setup_frame is not None
            and raw.frame - restart_setup_frame <= config.restart_setup_max_age_frames
        )
        restart_ok = setup_recent and raw.restart_context and restart_motion_run >= config.restart_motion_frames
        restart = RestartMotionProposal(
            restart_ok, restart_motion_run, bool(raw.restart_context),
            0.4 if restart_ok else 0.0, 0.6 if restart_ok else 1.0,
            "setup_then_persistent_motion_proposal" if restart_ok else "insufficient_context_or_temporal_motion",
        )
        output.append(AtdSignals(
            raw.frame, raw.half, ball_observed,
            "ATD_observed" if ball_observed else "ATD_missing",
            provider_speed, derived_speed, stationary, control, ball_motion, boundary, restart,
        ))
        previous = current
    return tuple(output)
