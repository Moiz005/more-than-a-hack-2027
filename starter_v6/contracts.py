"""Typed, source-aware evidence contracts for the TacticalFusion pipeline.

These are internal contracts. They deliberately do not add submission labels:
the public output remains H/A/D/X, while uncertainty and restart ownership stay
explicit inside the inference pipeline.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


class EvidenceSource(str, Enum):
    ATD = "ATD"
    TAG = "TAG"
    HOMOGRAPHY = "HOMOGRAPHY"
    TEMPORAL = "TEMPORAL"


class PlayState(str, Enum):
    LIVE = "LIVE"
    DEAD = "DEAD"
    UNKNOWN = "UNKNOWN"


class PossibleOwner(str, Enum):
    HOME = "H"
    AWAY = "A"
    UNKNOWN = "UNKNOWN"


class RestartType(str, Enum):
    THROW_IN = "Throw-in"
    CORNER_KICK = "Corner Kick"
    GOAL_KICK = "Goal Kick"
    FREE_KICK = "Free Kick"
    KICK_OFF_AFTER_GOAL = "Kick Off (After Goal)"
    KICK_OFF_START = "Kick Off (Start)"


class RestartPhase(str, Enum):
    UNKNOWN = "UNKNOWN"
    POSSIBILITY = "POSSIBILITY"
    PREPARATION = "PREPARATION"
    EXECUTION = "EXECUTION"
    LIVE_RECOVERED = "LIVE_RECOVERED"


@dataclass(frozen=True)
class FrameReference:
    """Exactly one zero-based frame or one half-open frame interval."""

    frame: Optional[int] = None
    interval: Optional[Tuple[int, int]] = None

    def __post_init__(self) -> None:
        if (self.frame is None) == (self.interval is None):
            raise ValueError("reference must contain exactly one frame or interval")
        if self.frame is not None:
            if isinstance(self.frame, bool) or not isinstance(self.frame, int) or self.frame < 0:
                raise ValueError("frame reference must be a non-negative integer")
            return
        interval = self.interval
        if (not isinstance(interval, tuple) or len(interval) != 2
                or any(isinstance(value, bool) or not isinstance(value, int) for value in interval)
                or interval[0] < 0 or interval[0] >= interval[1]):
            raise ValueError("interval reference must be a non-empty half-open interval")


@dataclass(frozen=True)
class ObservationQuality:
    """Quality and missingness metadata for one observation boundary."""

    observed: bool
    missing: bool
    finite_coordinate: bool
    valid_coordinate: bool
    time_gap_frames: Optional[int] = None
    plausible_speed: Optional[bool] = None
    jump_flag: bool = False
    player_coverage: Optional[int] = None
    homography_valid: Optional[bool] = None
    homography_reprojection_error: Optional[float] = None
    provenance: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.observed, bool) or not isinstance(self.missing, bool):
            raise ValueError("observed and missing must be booleans")
        if self.observed and self.missing:
            raise ValueError("observed and missing cannot both be true")
        if self.missing and (self.finite_coordinate or self.valid_coordinate):
            raise ValueError("missing observations cannot have valid coordinates")
        if self.time_gap_frames is not None and (
            isinstance(self.time_gap_frames, bool)
            or not isinstance(self.time_gap_frames, int)
            or self.time_gap_frames < 0
        ):
            raise ValueError("time_gap_frames must be a non-negative integer or None")
        if self.player_coverage is not None and (
            isinstance(self.player_coverage, bool)
            or not isinstance(self.player_coverage, int)
            or self.player_coverage < 0
        ):
            raise ValueError("player_coverage must be a non-negative integer or None")
        if self.homography_reprojection_error is not None and (
            not math.isfinite(self.homography_reprojection_error)
            or self.homography_reprojection_error < 0
        ):
            raise ValueError("homography_reprojection_error must be finite and non-negative")


@dataclass(frozen=True)
class Evidence:
    """One signed, quality-weighted observation with dependency provenance."""

    reference: FrameReference
    source: EvidenceSource
    value: float
    sign: int
    meaning: str
    quality: float
    missing: bool
    uncertainty: float
    dependency_group: str

    def __post_init__(self) -> None:
        if not isinstance(self.reference, FrameReference):
            raise ValueError("reference must be a FrameReference")
        if not isinstance(self.source, EvidenceSource):
            raise ValueError("source must be an EvidenceSource")
        if not math.isfinite(self.value):
            raise ValueError("evidence value must be finite")
        if self.sign not in {-1, 0, 1}:
            raise ValueError("evidence sign must be -1, 0, or 1")
        if not self.meaning or not self.meaning.strip():
            raise ValueError("evidence meaning is required")
        for name, value in (("quality", self.quality), ("uncertainty", self.uncertainty)):
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError("{} must be in [0, 1]".format(name))
        if not isinstance(self.missing, bool):
            raise ValueError("evidence missing must be boolean")
        if not self.dependency_group or not self.dependency_group.strip():
            raise ValueError("dependency_group is required")


@dataclass(frozen=True)
class RestartHypothesis:
    """Internal restart lifecycle hypothesis; never a submission label."""

    reference: FrameReference
    play_state: PlayState
    restart_type: Optional[RestartType]
    possible_owner: PossibleOwner
    phase: RestartPhase
    confidence: float
    uncertainty: float
    dependency_groups: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.reference, FrameReference):
            raise ValueError("reference must be a FrameReference")
        if not isinstance(self.play_state, PlayState):
            raise ValueError("play_state must be a PlayState")
        if self.restart_type is not None and not isinstance(self.restart_type, RestartType):
            raise ValueError("restart_type must be a RestartType or None")
        if not isinstance(self.possible_owner, PossibleOwner):
            raise ValueError("possible_owner must be a PossibleOwner")
        if not isinstance(self.phase, RestartPhase):
            raise ValueError("phase must be a RestartPhase")
        for name, value in (("confidence", self.confidence), ("uncertainty", self.uncertainty)):
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError("{} must be in [0, 1]".format(name))
        if any(not group or not group.strip() for group in self.dependency_groups):
            raise ValueError("dependency groups must be non-empty strings")
