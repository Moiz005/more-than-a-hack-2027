"""Aggregate-only diagnostics for predictions and aligned evidence; never reads ground truth."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from starter_v2.possession import possession_spells


def summarize(labels: Sequence[str], ball_observed: Sequence[bool],
              confidence: Sequence[float], evidence_team: Sequence[Optional[str]],
              runtime_seconds: float, fps: float = 25.0,
              high_confidence_threshold: float = 0.9) -> Dict[str, Any]:
    n = len(labels)
    if not n or any(len(values) != n for values in (ball_observed, confidence, evidence_team)):
        raise ValueError("labels and evidence arrays must have the same non-zero length")
    if not math.isfinite(fps) or fps <= 0 or not math.isfinite(runtime_seconds) or runtime_seconds < 0:
        raise ValueError("fps must be positive and runtime_seconds must be non-negative")
    if not 0 <= high_confidence_threshold <= 1:
        raise ValueError("high_confidence_threshold must be within [0, 1]")
    allowed = {"H", "A", "D", "X"}
    if any(label not in allowed for label in labels):
        raise ValueError("predictions contain an invalid label")
    if any(not math.isfinite(float(value)) or not 0 <= float(value) <= 1 for value in confidence):
        raise ValueError("confidence values must be finite and within [0, 1]")
    if any(team not in {None, "H", "A"} for team in evidence_team):
        raise ValueError("evidence_team values must be H, A, or null")

    counts = Counter(labels)
    spells = possession_spells(labels)
    durations = sorted((end - start + 1) / fps for _, start, end in spells)

    def percentile(p):
        return durations[int(round((len(durations) - 1) * p))] if durations else 0.0

    transitions = Counter((left, right) for left, right in zip(labels, labels[1:]) if left != right)
    missing = [not bool(value) for value in ball_observed]
    possession = [label in {"H", "A"} for label in labels]
    missing_count = sum(missing)
    in_possession_count = sum(missing[i] and possession[i] for i in range(n))
    contradictions = sum(
        confidence[i] >= high_confidence_threshold
        and evidence_team[i] in {"H", "A"}
        and labels[i] in {"H", "A"}
        and labels[i] != evidence_team[i]
        for i in range(n)
    )
    return {
        "frame_count": n,
        "observations": {
            "ball_missing_frames": missing_count,
            "ball_missing_fraction": missing_count / n,
            "ball_missing_during_predicted_possession_frames": in_possession_count,
            "ball_missing_during_predicted_possession_fraction": in_possession_count / n,
        },
        "inferences": {
            "predicted_possession_count": len(spells),
            "predicted_spell_duration_seconds": {
                "min": durations[0] if durations else 0.0,
                "median": percentile(0.5),
                "p90": percentile(0.9),
                "max": durations[-1] if durations else 0.0,
            },
            "predicted_label_share": {label: counts[label] / n for label in ("H", "A", "D", "X")},
            "predicted_transitions": {"{}->{}".format(a, b): count for (a, b), count in sorted(transitions.items())},
            "runtime_seconds": runtime_seconds,
        },
        "consistency_checks": {
            "high_confidence_prediction_evidence_contradictions": contradictions,
            "evidence_threshold": high_confidence_threshold,
        },
        "ground_truth": {"used": False, "accuracy_or_score_computed": False},
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Print aggregate diagnostics for a local prediction JSON.")
    parser.add_argument("input", type=Path, help="JSON: labels, ball_observed, confidence, evidence_team, runtime_seconds")
    parser.add_argument("--fps", type=float, default=25.0)
    parser.add_argument("--high-confidence-threshold", type=float, default=0.9)
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("diagnostic input must be a JSON object")
        if "ground_truth" in payload or "labels_true" in payload:
            raise ValueError("ground truth is not accepted by diagnostics")
        result = summarize(
            payload["labels"], payload["ball_observed"], payload["confidence"],
            payload["evidence_team"], float(payload["runtime_seconds"]), args.fps,
            args.high_confidence_threshold,
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("diagnostics: {}".format(error), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
