"""Sequential Stage 1 state routing and Stage 2 live ownership decoding."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Dict, Iterable, Optional, Tuple

from starter_v6.emissions import FrameEmission
from starter_v6.hmm import HMMConfig, _distribution


@dataclass(frozen=True)
class PlayStateDecision:
    frame: int
    half: int
    state: str
    reason: str
    confidence: float
    evidence_groups: Tuple[str, ...]
    quality_flags: Tuple[str, ...]
    owner: Optional[str] = None

    def __post_init__(self):
        if isinstance(self.frame, bool) or not isinstance(self.frame, int) or self.frame < 0:
            raise ValueError("frame must be a non-negative integer")
        if self.half not in (0, 1, 2):
            raise ValueError("half must be 0, 1, or 2")
        if self.state not in {"LIVE", "DEAD", "UNGRADED"}:
            raise ValueError("state must be LIVE, DEAD, or UNGRADED")
        if (self.half == 0) != (self.state == "UNGRADED"):
            raise ValueError("UNGRADED state must match the official half mask")
        if self.state != "LIVE" and self.owner is not None:
            raise ValueError("DEAD and UNGRADED decisions cannot carry Stage 2 ownership")
        if self.owner is not None:
            raise ValueError("Stage 1 decisions cannot carry Stage 2 ownership")
        if self.owner not in (None, "H", "A", "UNKNOWN"):
            raise ValueError("owner must be H, A, UNKNOWN, or absent")
        if (not isinstance(self.reason, str) or not self.reason
                or isinstance(self.confidence, bool)
                or not isinstance(self.confidence, (int, float))
                or not math.isfinite(self.confidence)
                or not 0.0 <= self.confidence <= 1.0):
            raise ValueError("reason and bounded confidence are required")
        if not isinstance(self.evidence_groups, tuple) or not isinstance(self.quality_flags, tuple):
            raise ValueError("evidence groups and quality flags must be tuples")


def run_live_ownership(rows: Iterable[Tuple[int, FrameEmission, bool]],
                       config: HMMConfig):
    """Decode ownership on contiguous LIVE graded rows only; boundaries reset state.

    Rows are (half, emission, is_live). Emissions remain the existing H/A evidence
    potentials. The decoder derives its two-state transition/initial priors from
    the configured three-state HMM without introducing new tuned parameters.
    """
    if not isinstance(config, HMMConfig):
        raise ValueError("config must be HMMConfig")
    init = _distribution(config.initial)
    trans = tuple(_distribution(row) for row in config.transitions)
    initial_ha = (init[0], init[1])
    transitions_ha = ((trans[0][0], trans[0][1]), (trans[1][0], trans[1][1]))
    initial_norm = max(initial_ha)
    initial_ha = tuple(v - initial_norm for v in initial_ha)
    transitions_ha = tuple(tuple(v - max(row[:2]) for v in row[:2]) for row in transitions_ha)

    labels: Dict[int, str] = {}
    stats = {"live_segments": 0, "stage2_frames": 0}
    segment = []
    previous_frame = None
    previous_half = None

    def flush():
        if not segment:
            return
        stats["live_segments"] += 1
        scores = [initial_ha[i] + config.emission_weight * math.log(
            max((segment[0][1].home, segment[0][1].away)[i], config.emission_floor)
        ) / config.temperature for i in range(2)]
        backs = []
        for _, emission, _ in segment[1:]:
            values = (emission.home, emission.away)
            prevs = [max(range(2), key=lambda j: scores[j] + transitions_ha[j][i]) for i in range(2)]
            scores = [scores[prevs[i]] + transitions_ha[prevs[i]][i] + config.emission_weight *
                      math.log(max(values[i], config.emission_floor)) / config.temperature
                      for i in range(2)]
            backs.append(prevs)
        state = max(range(2), key=scores.__getitem__)
        path = [state]
        for prevs in reversed(backs):
            state = prevs[state]
            path.append(state)
        for (frame, _, _), state in zip(segment, reversed(path)):
            labels[frame] = ("H", "A")[state]
        stats["stage2_frames"] += len(segment)
        segment.clear()

    for half, emission, is_live in rows:
        if not isinstance(emission, FrameEmission):
            raise ValueError("each Stage 2 row must contain a FrameEmission")
        if isinstance(half, bool) or half not in (1, 2) or emission.half != half:
            raise ValueError("Stage 2 rows must be graded and match the emission half")
        if not isinstance(is_live, bool):
            raise ValueError("is_live must be boolean")
        if previous_frame is not None and emission.frame <= previous_frame:
            raise ValueError("frame rows must be strictly ordered")
        if previous_frame is not None and emission.frame != previous_frame + 1:
            flush()
        if previous_half is not None and half != previous_half:
            flush()
        if not is_live or half == 0:
            flush()
        else:
            segment.append((emission.frame, emission, True))
        previous_frame, previous_half = emission.frame, half
    flush()
    return labels, stats


def compose_labels(states, ownership):
    if any(i >= len(states) for i in ownership):
        raise ValueError("ownership frame lies outside state sequence")
    if any(label not in {"H", "A"} for label in ownership.values()):
        raise ValueError("Stage 2 ownership labels must be H or A")
    live_frames = {frame for frame, state in enumerate(states) if state == "LIVE"}
    if set(ownership) != live_frames:
        raise ValueError("Stage 2 ownership must cover exactly the Stage 1 LIVE frames")
    result = []
    for frame, state in enumerate(states):
        if state == "UNGRADED":
            result.append("X")
        elif state == "DEAD":
            result.append("D")
        elif state == "LIVE":
            label = ownership.get(frame)
            if label not in {"H", "A"}:
                raise ValueError("every LIVE frame must receive H/A ownership")
            result.append(label)
        else:
            raise ValueError("unknown Stage 1 state")
    return result
