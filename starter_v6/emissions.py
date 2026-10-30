"""Validated per-frame H/A/D evidence scores for downstream temporal inference."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Iterator


@dataclass(frozen=True)
class FrameEmission:
    frame: int
    half: int
    home: float
    away: float
    dead: float
    informative: bool

    def __post_init__(self) -> None:
        if isinstance(self.frame, bool) or not isinstance(self.frame, int) or self.frame < 0:
            raise ValueError("frame must be a non-negative integer")
        if isinstance(self.half, bool) or self.half not in {0, 1, 2}:
            raise ValueError("half must be 0, 1, or 2")
        values = (self.home, self.away, self.dead)
        if any(not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or not 0.0 <= value <= 1.0 for value in values):
            raise ValueError("emission probabilities must be finite and in [0, 1]")
        if not math.isclose(sum(values), 1.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("emission probabilities must sum to 1")
        if not isinstance(self.informative, bool):
            raise ValueError("informative must be boolean")


def frame_emission(frame: int, half: int, *, home: float = 0.0, away: float = 0.0,
                   dead: float = 0.0, informative: bool = False) -> FrameEmission:
    """Normalize non-negative evidence; total absence yields neutral uninformative scores."""
    values = (float(home), float(away), float(dead))
    if any(not math.isfinite(value) or value < 0.0 for value in values):
        raise ValueError("emission evidence must be finite and non-negative")
    total = sum(values)
    if total == 0.0:
        return FrameEmission(frame, half, 1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0, False)
    return FrameEmission(frame, half, *(value / total for value in values), informative)


def validate_emission_stream(emissions: Iterable[FrameEmission], expected_frames: int) -> Iterator[FrameEmission]:
    """Require exactly one sequential, half-labeled emission per zero-based frame."""
    if isinstance(expected_frames, bool) or expected_frames < 0:
        raise ValueError("expected_frames must be non-negative")
    count = 0
    for expected, emission in enumerate(emissions):
        if emission.frame != expected:
            raise ValueError("expected emission frame {}, found {}".format(expected, emission.frame))
        yield emission
        count += 1
    if count != expected_frames:
        raise ValueError("expected {} emissions, found {}".format(expected_frames, count))
