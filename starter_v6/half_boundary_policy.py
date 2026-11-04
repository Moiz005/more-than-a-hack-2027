"""Pure, fail-closed half-boundary policy for HBK-01.

This layer is intentionally downstream of the existing E04 labels.  It can
only add a confirmed second-half pre-kickoff ``D`` prefix; it never changes
team ownership, first-half labels, ungraded ``X`` frames, or post-kickoff
labels.  The returned result is suitable for an audit caller to inspect before
any runner writes a submission.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Mapping, Optional, Sequence, Tuple

from starter_v6.timeline import TacticalTimeline
from starter_v6.kickoff_atd import CONFIRMED, KickoffDetectionResult


OVERLAY = "overlay"
AUDIT = "audit"
APPLIED = "APPLIED"
AUDIT_ONLY = "AUDIT_ONLY"
NO_CHANGE = "NO_CHANGE"
REJECTED = "REJECTED"
ALLOWED_LABELS = frozenset(("H", "A", "D", "X"))


@dataclass(frozen=True)
class BoundaryOverlayResult:
    """Immutable output and provenance for one boundary-policy invocation."""

    mode: str
    status: str
    reason: str
    labels: Tuple[str, ...]
    changed_frames: Tuple[int, ...]
    changed_counts: Tuple[Tuple[str, str, int], ...]
    unchanged_frame_count: int
    permitted_interval: Optional[Tuple[int, int]]
    first_half_result: Optional[KickoffDetectionResult]
    second_half_result: Optional[KickoffDetectionResult]
    preservation_assertions: Mapping[str, bool]


def _validate_timeline(timeline: TacticalTimeline) -> None:
    if not isinstance(timeline.frame_count, int) or timeline.frame_count < 1:
        raise ValueError("timeline frame_count must be a positive integer")
    if not isinstance(timeline.fps, int) or timeline.fps <= 0:
        raise ValueError("timeline fps must be a positive integer")
    if len(timeline.half_by_frame) != timeline.frame_count:
        raise ValueError("timeline half mask length does not match frame_count")

    expected = bytearray(timeline.frame_count)
    seen_halves = set()
    previous_end = -1
    for half, start, end in timeline.half_ranges:
        if half not in (1, 2) or half in seen_halves:
            raise ValueError("timeline must contain one non-overlapping range per half")
        if (isinstance(start, bool) or not isinstance(start, int)
                or isinstance(end, bool) or not isinstance(end, int)
                or start < 0 or end < start or end >= timeline.frame_count
                or start <= previous_end):
            raise ValueError("timeline half ranges must be ordered and in bounds")
        if any(expected[index] for index in range(start, end + 1)):
            raise ValueError("timeline half ranges overlap")
        expected[start:end + 1] = bytes([half]) * (end - start + 1)
        seen_halves.add(half)
        previous_end = end
    if seen_halves != {1, 2}:
        raise ValueError("timeline must define both graded halves")
    if bytes(expected) != timeline.half_by_frame:
        raise ValueError("timeline half mask disagrees with half_ranges")


def _validate_base_labels(base_labels: Sequence[str], timeline: TacticalTimeline) -> Tuple[str, ...]:
    try:
        labels = tuple(base_labels)
    except TypeError as exc:
        raise ValueError("base_labels must be a finite sequence") from exc
    if len(labels) != timeline.frame_count:
        raise ValueError("base_labels length must equal timeline frame_count")
    for frame, label in enumerate(labels):
        if label not in ALLOWED_LABELS:
            raise ValueError("invalid label {!r} at frame {}".format(label, frame))
        if timeline.half_by_frame[frame] == 0 and label != "X":
            raise ValueError("ungraded frame {} must be X".format(frame))
        if timeline.half_by_frame[frame] in (1, 2) and label == "X":
            raise ValueError("graded frame {} cannot be X".format(frame))
    return labels


def _result(
    mode: str,
    status: str,
    reason: str,
    labels: Tuple[str, ...],
    first_half_result: Optional[KickoffDetectionResult],
    second_half_result: Optional[KickoffDetectionResult],
    permitted_interval: Optional[Tuple[int, int]] = None,
) -> BoundaryOverlayResult:
    return BoundaryOverlayResult(
        mode=mode,
        status=status,
        reason=reason,
        labels=labels,
        changed_frames=(),
        changed_counts=(),
        unchanged_frame_count=len(labels),
        permitted_interval=permitted_interval,
        first_half_result=first_half_result,
        second_half_result=second_half_result,
        preservation_assertions={
            "exact_diff_support": True,
            "first_half_preserved": True,
            "outside_mask_preserved": True,
            "post_kickoff_suffix_preserved": True,
            "terminal_frames_preserved": True,
        },
    )


def _validated_kickoff_frame(
    second_half_result: Optional[KickoffDetectionResult],
    second_half_start: int,
    second_half_end: int,
) -> Tuple[Optional[int], Optional[str]]:
    if second_half_result is None:
        return None, "missing_second_half_result"
    if second_half_result.status != CONFIRMED:
        return None, "second_half_status_{}".format(second_half_result.status)
    frame = second_half_result.execution_frame
    if isinstance(frame, bool) or not isinstance(frame, int):
        return None, "missing_second_half_execution_frame"
    if frame == second_half_start:
        return None, "kickoff_at_graded_start"
    if frame < second_half_start or frame > second_half_end:
        return None, "kickoff_outside_second_half"
    return frame, None


def _assert_provenance(
    original: Tuple[str, ...],
    modified: Tuple[str, ...],
    changed_frames: Tuple[int, ...],
    second_half_start: int,
    kickoff_frame: int,
    timeline: TacticalTimeline,
) -> Mapping[str, bool]:
    exact_diff_support = tuple(
        index for index, (before, after) in enumerate(zip(original, modified))
        if before != after
    ) == changed_frames
    allowed_diff = all(second_half_start <= index < kickoff_frame for index in changed_frames)
    first_half_preserved = all(
        modified[index] == original[index]
        for half, start, end in timeline.half_ranges
        if half == 1
        for index in range(start, end + 1)
    )
    outside_mask_preserved = all(
        modified[index] == original[index]
        for index, marker in enumerate(timeline.half_by_frame)
        if marker == 0
    )
    suffix_preserved = all(
        modified[index] == original[index]
        for index in range(kickoff_frame, timeline.frame_count)
    )
    terminal_frames_preserved = all(
        modified[end] == original[end]
        for _, _, end in timeline.half_ranges
    )
    return {
        "exact_diff_support": exact_diff_support,
        "allowed_diff_support": allowed_diff,
        "first_half_preserved": first_half_preserved,
        "outside_mask_preserved": outside_mask_preserved,
        "post_kickoff_suffix_preserved": suffix_preserved,
        "terminal_frames_preserved": terminal_frames_preserved,
    }


def apply_kickoff_prefix(
    base_labels: Sequence[str],
    timeline: TacticalTimeline,
    kickoff_results: Mapping[int, Optional[KickoffDetectionResult]],
    mode: str = OVERLAY,
) -> BoundaryOverlayResult:
    """Apply or audit the confirmed second-half pre-kickoff ``D`` prefix.

    ``kickoff_results`` is keyed by half.  The first-half result is retained as
    provenance but is never used to modify labels.  In ``overlay`` mode an
    unconfirmed, ambiguous, missing, or out-of-range second-half result
    returns unchanged labels with ``REJECTED`` status; callers must refuse to
    write those labels.  The input sequence is copied and never mutated.
    """
    if mode not in (OVERLAY, AUDIT):
        raise ValueError("mode must be 'overlay' or 'audit'")
    _validate_timeline(timeline)
    labels = _validate_base_labels(base_labels, timeline)
    if not isinstance(kickoff_results, Mapping):
        raise ValueError("kickoff_results must be a mapping keyed by half")

    first_half_result = kickoff_results.get(1)
    second_half_result = kickoff_results.get(2)
    second_half_start, second_half_end = next(
        (start, end) for half, start, end in timeline.half_ranges if half == 2
    )
    kickoff_frame, rejection = _validated_kickoff_frame(
        second_half_result, second_half_start, second_half_end,
    )
    if rejection is not None:
        return _result(
            mode, REJECTED, rejection, labels,
            first_half_result, second_half_result,
        )

    permitted_interval = (second_half_start, kickoff_frame)
    if mode == AUDIT:
        return _result(
            mode, AUDIT_ONLY, "confirmed_second_half_prefix_audited", labels,
            first_half_result, second_half_result, permitted_interval,
        )

    modified = list(labels)
    for frame in range(second_half_start, kickoff_frame):
        modified[frame] = "D"
    modified_labels = tuple(modified)
    changed_frames = tuple(
        frame for frame, (before, after) in enumerate(zip(labels, modified_labels))
        if before != after
    )
    changed_counter = Counter((labels[frame], modified_labels[frame]) for frame in changed_frames)
    changed_counts = tuple(
        (old, new, count)
        for (old, new), count in sorted(changed_counter.items())
    )
    preservation = _assert_provenance(
        labels, modified_labels, changed_frames,
        second_half_start, kickoff_frame, timeline,
    )
    if not all(preservation.values()):
        raise AssertionError("kickoff prefix changed labels outside its permitted interval")
    status = APPLIED if changed_frames else NO_CHANGE
    reason = "second_half_prefix_overlaid" if changed_frames else "prefix_already_D"
    return BoundaryOverlayResult(
        mode=mode,
        status=status,
        reason=reason,
        labels=modified_labels,
        changed_frames=changed_frames,
        changed_counts=changed_counts,
        unchanged_frame_count=timeline.frame_count - len(changed_frames),
        permitted_interval=permitted_interval,
        first_half_result=first_half_result,
        second_half_result=second_half_result,
        preservation_assertions=preservation,
    )


__all__ = [
    "ALLOWED_LABELS",
    "APPLIED",
    "AUDIT",
    "AUDIT_ONLY",
    "BoundaryOverlayResult",
    "NO_CHANGE",
    "OVERLAY",
    "REJECTED",
    "apply_kickoff_prefix",
]
