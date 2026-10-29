"""Small deterministic E01 possession state machine for synthetic validation.

This initial rule-based implementation is a test subject, not a tuned competition model.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class PlayerEvidence:
    team: str
    x_m: float
    y_m: float


@dataclass(frozen=True)
class FrameEvidence:
    frame: int
    half: int
    ball_xy: Optional[Tuple[float, float]]
    players: Tuple[PlayerEvidence, ...]
    dead_ball: bool = False
    restart: bool = False


@dataclass(frozen=True)
class PossessionConfig:
    control_radius_m: float = 1.5
    acquire_frames: int = 2
    max_missing_frames: int = 2
    max_uncertain_frames: int = 2

    def __post_init__(self):
        if not math.isfinite(self.control_radius_m) or self.control_radius_m <= 0:
            raise ValueError("control_radius_m must be finite and positive")
        for name in ("acquire_frames", "max_missing_frames", "max_uncertain_frames"):
            if getattr(self, name) < 0:
                raise ValueError("{} must be non-negative".format(name))
        if self.acquire_frames < 1:
            raise ValueError("acquire_frames must be at least 1")


def validate_submission_rows(rows: Iterable[Tuple[int, str]], expected_frames: int) -> None:
    """Validate contiguous zero-based frame IDs and non-empty allowed submission labels."""
    if expected_frames < 0:
        raise ValueError("expected_frames must be non-negative")
    count = 0
    for count, row in enumerate(rows, start=1):
        if len(row) != 2:
            raise ValueError("row {} must contain frame and label".format(count - 1))
        frame, label = row
        expected = count - 1
        if int(frame) != expected:
            raise ValueError("expected frame {}, found {}".format(expected, frame))
        if label not in {"H", "A", "D", "X"}:
            raise ValueError("frame {} has empty or invalid label {!r}".format(expected, label))
    if count != expected_frames:
        raise ValueError("expected {} rows, found {}".format(expected_frames, count))


def decode_probabilities(rows: Iterable[Sequence[float]], tolerance: float = 1e-6) -> List[str]:
    """Decode normalized H/A/D probability rows; ties use fixed H, A, D order."""
    labels = ("H", "A", "D")
    decoded = []
    for index, row in enumerate(rows):
        if len(row) != 3:
            raise ValueError("emission row {} must contain H/A/D probabilities".format(index))
        values = [float(value) for value in row]
        if any(not math.isfinite(value) for value in values):
            raise ValueError("emission row {} contains a non-finite probability".format(index))
        if any(value < 0.0 or value > 1.0 for value in values):
            raise ValueError("emission row {} probabilities must be within [0, 1]".format(index))
        if abs(sum(values) - 1.0) > tolerance:
            raise ValueError("emission row {} probabilities must sum to 1".format(index))
        decoded.append(labels[max(range(3), key=lambda i: values[i])])
    return decoded


def _controlled_team(frame: FrameEvidence, radius: float) -> Optional[str]:
    if frame.ball_xy is None:
        return None
    bx, by = frame.ball_xy
    nearest = None
    nearest_team = None
    for player in frame.players:
        if player.team not in {"H", "A"}:
            raise ValueError("player team must be H or A")
        if not math.isfinite(player.x_m) or not math.isfinite(player.y_m):
            raise ValueError("player coordinates must be finite")
        distance = math.hypot(player.x_m - bx, player.y_m - by)
        if nearest is None or distance < nearest:
            nearest, nearest_team = distance, player.team
    return nearest_team if nearest is not None and nearest <= radius else None


def infer_possession(frames: Sequence[FrameEvidence], config: PossessionConfig = PossessionConfig()) -> List[str]:
    """Infer H/A/D/X with bounded missing/uncertain carry, acquisition confirmation and half reset.

    `dead_ball` is independent evidence. A restart marker alone never assigns a team.
    """
    labels: List[str] = []
    previous_half = None
    state = "X"
    missing_count = 0
    uncertain_count = 0
    candidate = None
    candidate_count = 0
    previous_frame = None
    for frame in frames:
        if frame.frame < 0 or frame.half < 0:
            raise ValueError("frame and half indexes must be non-negative")
        if previous_frame is not None and frame.frame != previous_frame + 1:
            raise ValueError("frames must be contiguous and ordered")
        previous_frame = frame.frame
        if previous_half is not None and frame.half != previous_half:
            state, missing_count, uncertain_count = "X", 0, 0
            candidate, candidate_count = None, 0
        previous_half = frame.half
        if frame.dead_ball:
            state = "D"
            missing_count = uncertain_count = 0
            candidate, candidate_count = None, 0
            labels.append(state)
            continue
        if frame.ball_xy is None:
            missing_count += 1
            candidate, candidate_count = None, 0
            if missing_count > config.max_missing_frames:
                state = "X"
            labels.append(state if state in {"H", "A"} else "X")
            continue
        if any(not math.isfinite(float(value)) for value in frame.ball_xy):
            raise ValueError("ball coordinates must be finite or absent")
        missing_count = 0
        team = _controlled_team(frame, config.control_radius_m)
        if team is None:
            uncertain_count += 1
            candidate, candidate_count = None, 0
            if uncertain_count > config.max_uncertain_frames:
                state = "X"
            labels.append(state if state in {"H", "A"} else "X")
            continue
        uncertain_count = 0
        if team == state:
            candidate, candidate_count = None, 0
            labels.append(state)
            continue
        if team == candidate:
            candidate_count += 1
        else:
            candidate, candidate_count = team, 1
        if candidate_count >= config.acquire_frames:
            state = team
            candidate, candidate_count = None, 0
        labels.append(state if state in {"H", "A"} else "X")
    return labels


def possession_spells(labels: Sequence[str]) -> List[Tuple[str, int, int]]:
    """Return inclusive (team, start_frame, end_frame) maximal H/A runs; D and X split spells."""
    spells = []
    start = 0
    while start < len(labels):
        team = labels[start]
        if team not in {"H", "A"}:
            start += 1
            continue
        end = start
        while end + 1 < len(labels) and labels[end + 1] == team:
            end += 1
        spells.append((team, start, end))
        start = end + 1
    return spells


def read_submission(path: str, expected_frames: int) -> List[str]:
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        if next(reader, None) != ["frame", "label"]:
            raise ValueError("submission header must be exactly frame,label")
        rows = list(reader)
    validate_submission_rows(rows, expected_frames)
    return [row[1] for row in rows]
