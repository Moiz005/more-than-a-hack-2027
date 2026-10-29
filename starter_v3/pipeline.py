"""Adapters and aggregate-only diagnostics for the local E01 pipeline."""

from __future__ import annotations

import math
from collections import Counter
from statistics import median
from typing import Dict, Iterable, Iterator

from starter_v3.ingestion import ATDFrame, ATDMetadata, SmartTagEvent
from starter_v3.possession import FrameEvidence, FrameInference, PlayerEvidence


RESTART_TYPES = frozenset({
    "throw-in", "corner kick", "goal kick", "free kick",
    "kick off (after goal)", "kick off (start)",
})


def restart_frame_mask(events: Iterable[SmartTagEvent], frame_count: int) -> bytearray:
    """Mark set-piece restart context, not possession labels, on half-open tag intervals."""
    if frame_count < 0:
        raise ValueError("frame_count must be non-negative")
    mask = bytearray(frame_count)
    for event in events:
        if event.start_frame < 0 or event.end_frame < event.start_frame or event.end_frame > frame_count:
            raise ValueError("Smart Tag interval is outside the frame timeline")
        code = " ".join(event.code.casefold().split())
        tag_type = " ".join((event.tags.get("Type") or "").casefold().split())
        if code != "set pieces" or tag_type not in RESTART_TYPES:
            continue
        mask[event.start_frame:event.end_frame] = b"\x01" * (event.end_frame - event.start_frame)
    return mask


def frame_evidence_from_atd(
    raw: ATDFrame,
    metadata: ATDMetadata,
    half: int,
    restart_context: bool,
) -> FrameEvidence:
    """Convert one aligned ATD row; absent coordinates never become physical (0, 0)."""
    if raw.frame_id != raw.video_frame + 1:
        raise ValueError("ATD frame_id must be video_frame + 1")
    if len(raw.players) != len(metadata.slots):
        raise ValueError("ATD player slot count does not match metadata")
    if half not in {0, 1, 2}:
        raise ValueError("half must be 0, 1, or 2")
    players = []
    for slot, observation in zip(metadata.slots, raw.players):
        if not observation.valid:
            continue
        if not math.isfinite(observation.x_m) or not math.isfinite(observation.y_m):
            raise ValueError("valid player coordinates must be finite")
        speed = observation.speed_mps if observation.speed_valid else None
        players.append(PlayerEvidence(slot.team, observation.x_m, observation.y_m, speed))
    if raw.ball.valid:
        if not math.isfinite(raw.ball.x_m) or not math.isfinite(raw.ball.y_m):
            raise ValueError("valid ball coordinates must be finite")
        ball_xy = (raw.ball.x_m, raw.ball.y_m)
        ball_speed = raw.ball.speed_mps if raw.ball.speed_valid else None
    else:
        ball_xy, ball_speed = None, None
    return FrameEvidence(
        frame=raw.video_frame,
        half=half,
        ball_xy=ball_xy,
        players=tuple(players),
        ball_speed_mps=ball_speed,
        restart_context=restart_context,
    )


def iter_frame_evidence(
    raw_frames: Iterable[ATDFrame],
    metadata: ATDMetadata,
    half_by_frame: bytearray,
    restart_mask: bytearray,
) -> Iterator[FrameEvidence]:
    """Adapt every tactical row in strict 0-based order without materializing ATD arrays."""
    if len(half_by_frame) != len(restart_mask):
        raise ValueError("half and restart masks must have the same frame count")
    expected = 0
    for raw in raw_frames:
        if raw.video_frame != expected:
            raise ValueError("expected video_frame {}, found {}".format(expected, raw.video_frame))
        if raw.frame_id != expected + 1:
            raise ValueError("expected frame_id {}, found {}".format(expected + 1, raw.frame_id))
        yield frame_evidence_from_atd(
            raw, metadata, half_by_frame[expected], bool(restart_mask[expected])
        )
        expected += 1
    if expected != len(half_by_frame):
        raise ValueError("expected {} tactical rows, found {}".format(len(half_by_frame), expected))


class InferenceSummaryAccumulator:
    """Incrementally collect diagnostics so full-match inference stays streaming."""

    def __init__(self, contradiction_confidence: float = 0.8) -> None:
        if not math.isfinite(contradiction_confidence) or not 0 <= contradiction_confidence <= 1:
            raise ValueError("contradiction_confidence must be in [0, 1]")
        self.contradiction_confidence = contradiction_confidence
        self.label_counts = Counter()
        self.transitions = Counter()
        self.durations = []
        self.cue_frames = Counter()
        self.observed = self.missing_possession = self.contradictions = 0
        self.confirmed_deadball_frames = self.frame_count = 0
        self.previous_label = None
        self.spell_team = None
        self.spell_length = 0

    def add(self, result: FrameInference) -> None:
        if result.label not in {"H", "A", "D", "X"}:
            raise ValueError("inference has an invalid label")
        self.frame_count += 1
        label = result.label
        self.label_counts[label] += 1
        if self.previous_label is not None and self.previous_label != label:
            self.transitions[self.previous_label + "->" + label] += 1
        self.previous_label = label
        if label in {"H", "A"}:
            if self.spell_team == label:
                self.spell_length += 1
            else:
                if self.spell_length:
                    self.durations.append(self.spell_length)
                self.spell_team, self.spell_length = label, 1
        elif self.spell_length:
            self.durations.append(self.spell_length)
            self.spell_team, self.spell_length = None, 0
        self.observed += int(result.team_evidence.ball_observed)
        self.missing_possession += int(label in {"H", "A"} and not result.team_evidence.ball_observed)
        self.contradictions += int(
            result.team_evidence.team is not None
            and result.team_evidence.confidence >= self.contradiction_confidence
            and label in {"H", "A", "D"}
            and label != result.team_evidence.team
        )
        self.cue_frames.update(result.dead_ball_evidence.cues)
        self.confirmed_deadball_frames += int(result.dead_ball_evidence.confirmed)

    def report(self, runtime_seconds: float) -> Dict[str, object]:
        """Build a non-reconstructive aggregate report without ground-truth fields."""
        if not math.isfinite(runtime_seconds) or runtime_seconds < 0:
            raise ValueError("runtime_seconds must be finite and non-negative")
        durations = list(self.durations)
        if self.spell_length:
            durations.append(self.spell_length)
        durations_sorted = sorted(durations)
        q90 = (
            durations_sorted[min(len(durations_sorted) - 1, int(0.9 * len(durations_sorted)))]
            if durations_sorted else 0
        )
        frame_count = self.frame_count
        return {
            "frame_count": frame_count,
            "observations": {
                "ball_observed_frames": self.observed,
                "ball_missing_frames": frame_count - self.observed,
                "ball_missing_during_predicted_possession_frames": self.missing_possession,
                "dead_ball_evidence_cue_frames": dict(sorted(self.cue_frames.items())),
                "confirmed_dead_ball_frames": self.confirmed_deadball_frames,
            },
            "inferences": {
                "predicted_label_counts": {label: self.label_counts.get(label, 0) for label in "HADX"},
                "predicted_label_share": {
                    label: (self.label_counts.get(label, 0) / float(frame_count) if frame_count else 0.0)
                    for label in "HADX"
                },
                "predicted_possession_count": len(durations),
                "possession_duration_frames": {
                    "min": min(durations) if durations else 0,
                    "median": median(durations) if durations else 0,
                    "p90": q90,
                    "max": max(durations) if durations else 0,
                },
                "transitions": dict(sorted(self.transitions.items())),
                "runtime_seconds": runtime_seconds,
            },
            "consistency_checks": {
                "high_confidence_prediction_evidence_contradictions": self.contradictions,
                "confidence_threshold": self.contradiction_confidence,
                "interpretation": "model evidence consistency only; not ground-truth accuracy",
            },
            "ground_truth": {"used": False, "accuracy_or_score_computed": False},
        }


def summarize_inferences(
    results: Iterable[FrameInference],
    runtime_seconds: float,
    contradiction_confidence: float = 0.8,
) -> Dict[str, object]:
    """Summarize predictions and evidence without accepting or computing ground truth."""
    accumulator = InferenceSummaryAccumulator(contradiction_confidence)
    for result in results:
        accumulator.add(result)
    return accumulator.report(runtime_seconds)
