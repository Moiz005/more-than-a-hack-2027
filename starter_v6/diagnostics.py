"""Aggregate-only E04 behavior diagnostics."""
from collections import Counter

from starter_v6.intervals import intervals


def _percentile(values, percentile):
    if not values:
        return 0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((percentile / 100.0) * len(ordered) + 0.999999) - 1))
    return ordered[index]


def build_diagnostics(labels, halves, parent_labels, emission_argmax, missing_ball, runtime_seconds):
    """Summarize predictions against E03 outputs and evidence without frame rows."""
    count = len(labels)
    if any(len(values) != count for values in (halves, parent_labels, emission_argmax, missing_ball)):
        raise ValueError("diagnostic arrays must align")
    if any(label not in {"H", "A", "D", "X"} for label in labels):
        raise ValueError("invalid decoded label")

    graded_positions = [index for index, half in enumerate(halves) if half in (1, 2)]
    if any(labels[index] == "X" for index in graded_positions):
        raise ValueError("graded output cannot contain X")
    if any((labels[index] == "X") != (halves[index] == 0) for index in range(count)):
        raise ValueError("X labels must match ungraded frames")

    graded_counts = Counter(labels[index] for index in graded_positions)
    state_shares = {state: graded_counts[state] / float(len(graded_positions)) if graded_positions else 0.0
                    for state in "HAD"}
    runs = intervals(labels, halves)
    state_durations = {state: [end - start for label, _, start, end in runs if label == state]
                       for state in "HAD"}
    duration_summary = {}
    for state, values in state_durations.items():
        duration_summary[state] = {
            "count": len(values),
            "min": min(values) if values else 0,
            "median": _percentile(values, 50),
            "p90": _percentile(values, 90),
            "max": max(values) if values else 0,
            "histogram_frames": {
                "1-24": sum(1 for value in values if 1 <= value <= 24),
                "25-49": sum(1 for value in values if 25 <= value <= 49),
                "50-99": sum(1 for value in values if 50 <= value <= 99),
                "100-249": sum(1 for value in values if 100 <= value <= 249),
                "250+": sum(1 for value in values if value >= 250),
            },
        }

    transitions = Counter()
    previous = None
    for state, half, _, _ in runs:
        if previous is not None and previous[1] == half:
            transitions[previous[0] + "->" + state] += 1
        previous = (state, half)

    missing_positions = [index for index in graded_positions if missing_ball[index]]
    return {
        "frame_count": count,
        "graded_frame_count": len(graded_positions),
        "ungraded_frame_count": count - len(graded_positions),
        "half_frame_counts": {str(half): sum(value == half for value in halves) for half in (0, 1, 2)},
        "graded_counts": dict(sorted(graded_counts.items())),
        "graded_state_shares": state_shares,
        "interval_counts": dict(sorted(Counter(row[0] for row in runs).items())),
        "duration_frames": duration_summary,
        "transitions": dict(sorted(transitions.items())),
        "missing_ball_overlap": {
            "graded_missing_ball_frames": len(missing_positions),
            "missing_ball_during_H_or_A_frames": sum(labels[index] in {"H", "A"} for index in missing_positions),
            "missing_ball_during_D_frames": sum(labels[index] == "D" for index in missing_positions),
        },
        "emission_agreement": {
            "compared_graded_frames": len(graded_positions),
            "decoded_matches_emission_argmax": sum(labels[index] == emission_argmax[index] for index in graded_positions),
            "interpretation": "behavioral agreement with evidence argmax; not accuracy",
        },
        "e03_comparison": {
            "compared_frames": len(graded_positions),
            "labels_changed": sum(labels[index] != parent_labels[index] for index in graded_positions),
            "interpretation": "E04 versus E03 behavior difference; not accuracy or model superiority",
        },
        "ground_truth": {"used": False, "scores_computed": False},
        "runtime_seconds": runtime_seconds,
    }
