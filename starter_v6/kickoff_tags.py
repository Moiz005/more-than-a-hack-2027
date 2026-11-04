"""Smart Tagging context extraction for HBK-01 opening kickoffs.

This module only identifies bounded search context. It never emits submission
labels, infers a legal LIVE/DEAD transition, or chooses a kickoff execution
frame. ATD quality and motion confirmation belong to the later detector phase.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

from starter_v6.ingestion import SmartTagEvent
from starter_v6.timeline import TacticalTimeline, build_tactical_timeline


SET_PIECES_CODE = "set pieces"
OPENING_KICKOFF_TYPE = "kick off (start)"
CANDIDATE_AVAILABLE = "CANDIDATE_AVAILABLE"
AMBIGUOUS = "AMBIGUOUS"
MISSING_TAG = "MISSING_TAG"
DEFAULT_SEARCH_MARGIN_BEFORE_FRAMES = 25
DEFAULT_SEARCH_MARGIN_AFTER_FRAMES = 75


def _normalize(value: Optional[object]) -> str:
    return " ".join(str(value or "").casefold().split())


def _half_number(value: Optional[object]) -> Optional[int]:
    normalized = _normalize(value)
    if normalized in {"1", "1st", "first", "1st half", "first half"}:
        return 1
    if normalized in {"2", "2nd", "second", "2nd half", "second half"}:
        return 2
    return None


def _valid_margin(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("{} must be a non-negative integer".format(name))


def _valid_raw_seconds(start: object, end: object) -> bool:
    return (
        isinstance(start, (int, float)) and not isinstance(start, bool)
        and isinstance(end, (int, float)) and not isinstance(end, bool)
        and math.isfinite(float(start)) and math.isfinite(float(end))
        and float(start) >= 0.0 and float(end) >= float(start)
    )


def _valid_frames(start: object, end: object, frame_count: int) -> bool:
    return (
        isinstance(start, int) and not isinstance(start, bool)
        and isinstance(end, int) and not isinstance(end, bool)
        and 0 <= start < end <= frame_count
    )


def _intersects_half(start_frame: int, end_frame: int, half_start: int, half_end: int) -> bool:
    """Test a half-open tag interval against an inclusive graded range."""
    return start_frame <= half_end and end_frame > half_start


@dataclass(frozen=True)
class KickoffTagCandidate:
    """Auditable representation of one Smart Tag event considered by HBK-01."""

    event_index: int
    source: str
    code: str
    type_value: Optional[str]
    team_value: Optional[str]
    half_value: Optional[str]
    half: Optional[int]
    raw_start_seconds: object
    raw_end_seconds: object
    start_frame: Optional[int]
    end_frame: Optional[int]
    search_start_frame: Optional[int]
    search_end_frame: Optional[int]
    eligible: bool
    selection_explanation: str
    warnings: Tuple[str, ...] = ()


@dataclass(frozen=True)
class KickoffTagInventory:
    """All preserved records plus conservative per-half candidate accessors."""

    records: Tuple[KickoffTagCandidate, ...]
    frame_count: int
    half_ranges: Tuple[Tuple[int, int, int], ...]

    def candidates_for_half(self, half: int) -> Tuple[KickoffTagCandidate, ...]:
        return tuple(record for record in self.records
                     if record.eligible and record.half == half)

    def status_for_half(self, half: int) -> str:
        count = len(self.candidates_for_half(half))
        if count == 0:
            return MISSING_TAG
        if count > 1:
            return AMBIGUOUS
        return CANDIDATE_AVAILABLE

    def selected_candidate(self, half: int) -> Optional[KickoffTagCandidate]:
        """Return a candidate only when extraction leaves exactly one option."""
        candidates = self.candidates_for_half(half)
        return candidates[0] if len(candidates) == 1 else None


def extract_opening_kickoff_candidates(
    events: Iterable[SmartTagEvent],
    timeline: Optional[TacticalTimeline] = None,
    search_margin_before_frames: int = DEFAULT_SEARCH_MARGIN_BEFORE_FRAMES,
    search_margin_after_frames: int = DEFAULT_SEARCH_MARGIN_AFTER_FRAMES,
) -> KickoffTagInventory:
    """Extract opening-kickoff search context without selecting execution.

    Exact matching is limited to code SET PIECES and Type Kick Off (Start),
    after case/whitespace normalization. Every input event is retained in the
    returned inventory so excluded, malformed, duplicate, and wrong-half
    records remain visible to an audit. Search bounds are half-open and are
    clipped to the source frame count.
    """
    _valid_margin(search_margin_before_frames, "search_margin_before_frames")
    _valid_margin(search_margin_after_frames, "search_margin_after_frames")
    active_timeline = timeline or build_tactical_timeline()
    frame_count = active_timeline.frame_count
    half_ranges = tuple(active_timeline.half_ranges)
    ranges_by_half: Dict[int, Tuple[int, int]] = {
        half: (start, end) for half, start, end in half_ranges
    }
    records: List[KickoffTagCandidate] = []

    for event_index, event in enumerate(events):
        tags: Mapping[str, object] = event.tags if isinstance(event.tags, Mapping) else {}
        type_value = tags.get("Type")
        team_value = tags.get("Team")
        half_value = tags.get("Half")
        half = _half_number(half_value)
        warnings: List[str] = []
        eligible = True
        explanation = "opening kickoff candidate"

        normalized_code = _normalize(event.code)
        normalized_type = _normalize(type_value)
        if normalized_code != SET_PIECES_CODE:
            eligible = False
            explanation = "excluded: code is not SET PIECES"
        elif normalized_type != OPENING_KICKOFF_TYPE:
            eligible = False
            explanation = "excluded: Type is not Kick Off (Start)"

        raw_start = event.start_s
        raw_end = event.end_s
        start_frame = event.start_frame
        end_frame = event.end_frame
        if not _valid_raw_seconds(raw_start, raw_end):
            warnings.append("invalid_raw_seconds")
            eligible = False
            explanation = "rejected: invalid raw Smart Tag seconds"
        if not _valid_frames(start_frame, end_frame, frame_count):
            warnings.append("invalid_frame_bounds")
            eligible = False
            explanation = "rejected: invalid Smart Tag frame bounds"

        search_start: Optional[int] = None
        search_end: Optional[int] = None
        if _valid_frames(start_frame, end_frame, frame_count):
            search_start = max(0, start_frame - search_margin_before_frames)
            search_end = min(frame_count, end_frame + search_margin_after_frames)

        if eligible and half is None:
            warnings.append("missing_half" if half_value is None else "invalid_half")
            eligible = False
            explanation = "rejected: missing or unrecognized Half value"

        if eligible and half not in ranges_by_half:
            warnings.append("invalid_half")
            eligible = False
            explanation = "rejected: Half is not present in the timeline"

        if eligible:
            half_start, half_end = ranges_by_half[half]
            if not _intersects_half(start_frame, end_frame, half_start, half_end):
                warnings.append("does not intersect claimed half")
                eligible = False
                explanation = "rejected: tag interval does not intersect claimed half"

        records.append(KickoffTagCandidate(
            event_index=event_index,
            source="smart_tagging",
            code=str(event.code),
            type_value=type_value if isinstance(type_value, str) else None,
            team_value=team_value if isinstance(team_value, str) else None,
            half_value=half_value if isinstance(half_value, str) else None,
            half=half,
            raw_start_seconds=raw_start,
            raw_end_seconds=raw_end,
            start_frame=start_frame if isinstance(start_frame, int) else None,
            end_frame=end_frame if isinstance(end_frame, int) else None,
            search_start_frame=search_start,
            search_end_frame=search_end,
            eligible=eligible,
            selection_explanation=explanation,
            warnings=tuple(warnings),
        ))

    return KickoffTagInventory(tuple(records), frame_count, half_ranges)


__all__ = [
    "AMBIGUOUS",
    "CANDIDATE_AVAILABLE",
    "DEFAULT_SEARCH_MARGIN_AFTER_FRAMES",
    "DEFAULT_SEARCH_MARGIN_BEFORE_FRAMES",
    "KickoffTagCandidate",
    "KickoffTagInventory",
    "MISSING_TAG",
    "extract_opening_kickoff_candidates",
]
