"""Three-state log-space Viterbi over normalized evidence potentials."""
import math
from dataclasses import dataclass

STATES = ("H", "A", "D")


@dataclass(frozen=True)
class HMMConfig:
    initial: tuple = (0.45, 0.45, 0.10)
    transitions: tuple = ((0.98, 0.01, 0.01), (0.01, 0.98, 0.01), (0.025, 0.025, 0.95))
    emission_floor: float = 1e-12
    emission_weight: float = 1.0
    temperature: float = 1.0


def _distribution(values):
    if len(values) != 3 or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x <= 0 for x in values):
        raise ValueError("probabilities must contain three finite positive values")
    if not math.isclose(sum(values), 1.0, abs_tol=1e-9, rel_tol=0.0):
        raise ValueError("probabilities must sum to one")
    return tuple(math.log(x) for x in values)


def decode(emissions, initial=None, transitions=None, floor=1e-12, weight=1.0, temperature=1.0, config=None):
    """Return labels and score; call independently for each contiguous half."""
    if config is not None:
        if not isinstance(config, HMMConfig):
            raise ValueError("config must be HMMConfig")
        initial, transitions = config.initial, config.transitions
        floor, weight, temperature = config.emission_floor, config.emission_weight, config.temperature
    if initial is None or transitions is None:
        raise ValueError("initial and transitions are required")
    if any(not isinstance(x, (int, float)) or isinstance(x, bool) or not math.isfinite(x) or x <= 0 for x in (floor, weight, temperature)) or floor > 1:
        raise ValueError("floor, weight and temperature must be finite and positive")
    prior = _distribution(initial)
    if len(transitions) != 3:
        raise ValueError("transition matrix must have three rows")
    transition = tuple(_distribution(row) for row in transitions)
    back = []
    scores = None
    for emission in emissions:
        values = (emission.home, emission.away, emission.dead)
        if any(not math.isfinite(x) or not 0 <= x <= 1 for x in values) or not math.isclose(sum(values), 1, abs_tol=1e-9, rel_tol=0):
            raise ValueError("invalid emission")
        likelihood = [weight * math.log(max(x, floor)) / temperature for x in values]
        if not all(math.isfinite(x) for x in likelihood):
            raise ValueError("non-finite emission potential")
        if scores is None:
            scores = [prior[i] + likelihood[i] for i in range(3)]
            continue
        predecessors = [max(range(3), key=lambda j: scores[j] + transition[j][i]) for i in range(3)]
        scores = [scores[predecessors[i]] + transition[predecessors[i]][i] + likelihood[i] for i in range(3)]
        if not all(math.isfinite(x) for x in scores):
            raise ValueError("non-finite path score")
        back.append(predecessors)
    if scores is None:
        return [], 0.0
    state = max(range(3), key=scores.__getitem__)
    score = scores[state]
    path = [state]
    for predecessors in reversed(back):
        state = predecessors[state]
        path.append(state)
    return [STATES[i] for i in reversed(path)], score
