"""Fail-closed tactical timeline and source-index contracts."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

from games import GAME, GAMES, DEFAULT_SOURCE, half_video_blocks, source_frames


TACTICAL_SOURCE = DEFAULT_SOURCE
TACTICAL_FPS = GAMES[GAME]["fps"]
TACTICAL_FRAME_COUNT = GAMES[GAME]["n_video_frames"]


@dataclass(frozen=True)
class TacticalTimeline:
    source: str
    fps: int
    frame_count: int
    half_by_frame: bytes
    half_ranges: Tuple[Tuple[int, int, int], ...]


def validate_tactical_reference(source: str, fps: int, frame_count: int) -> None:
    """Reject a non-tactical source or an unexpected reference timeline."""
    if source != TACTICAL_SOURCE:
        raise ValueError("submission timeline must use the tactical source, not {!r}".format(source))
    if fps != TACTICAL_FPS:
        raise ValueError("tactical reference must be 25 FPS, found {} FPS".format(fps))
    if frame_count != TACTICAL_FRAME_COUNT:
        raise ValueError(
            "tactical reference must contain 199319 frames, found {}".format(frame_count)
        )


def build_tactical_timeline() -> TacticalTimeline:
    """Build the immutable reference mask from the pinned games.py metadata."""
    source = TACTICAL_SOURCE
    frame_count = source_frames(source, GAME)
    fps = GAMES[GAME]["fps"]
    validate_tactical_reference(source, fps, frame_count)
    mask = bytearray(frame_count)
    ranges = []
    for half, first, last in half_video_blocks(GAME):
        if first < 0 or last >= frame_count or first > last:
            raise ValueError("graded half is outside the tactical frame range")
        if any(mask[index] for index in range(first, last + 1)):
            raise ValueError("graded half ranges overlap")
        mask[first:last + 1] = bytes([half]) * (last - first + 1)
        ranges.append((half, first, last))
    return TacticalTimeline(source, fps, frame_count, bytes(mask), tuple(ranges))


def validate_atd_frame_mapping(frame_id: int, video_frame: int) -> None:
    """Validate the one-based ATD to zero-based tactical mapping."""
    if (isinstance(frame_id, bool) or not isinstance(frame_id, int)
            or isinstance(video_frame, bool) or not isinstance(video_frame, int)):
        raise ValueError("frame_id and video_frame must be integers")
    if frame_id < 1 or video_frame < 0 or frame_id - 1 != video_frame:
        raise ValueError("ATD frame_id must equal video_frame + 1")


def seconds_to_half_open_frames(
    start_seconds: float,
    end_seconds: float,
    fps: int = TACTICAL_FPS,
    frame_count: Optional[int] = TACTICAL_FRAME_COUNT,
) -> Tuple[int, int]:
    """Convert Smart Tag seconds to a rounded, half-open tactical interval."""
    if not math.isfinite(start_seconds) or not math.isfinite(end_seconds):
        raise ValueError("Smart Tag seconds must be finite")
    if start_seconds < 0 or end_seconds < start_seconds:
        raise ValueError("Smart Tag interval must be half-open and ordered")
    if isinstance(fps, bool) or not isinstance(fps, int) or fps <= 0:
        raise ValueError("fps must be a positive integer")
    start = int(round(start_seconds * fps))
    end = int(round(end_seconds * fps))
    if frame_count is not None and (start > frame_count or end > frame_count):
        raise ValueError("Smart Tag interval exceeds the tactical frame range")
    return start, end


def validate_homography_frame_index(row_index: int, frame: int) -> None:
    """Require homography rows to use zero-based sequential frame indices."""
    if (isinstance(row_index, bool) or not isinstance(row_index, int)
            or isinstance(frame, bool) or not isinstance(frame, int)):
        raise ValueError("homography row index and frame must be integers")
    if row_index < 0 or frame != row_index:
        raise ValueError("homography frame index must be zero-based and aligned")
