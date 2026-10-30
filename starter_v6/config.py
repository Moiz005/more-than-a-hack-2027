"""Strict E04 JSON configuration loading."""
import json
import tempfile
from pathlib import Path

from starter_v5.run_e01 import load_config as load_parent_config
from starter_v6.hmm import HMMConfig, _distribution

HMM_DEFAULTS = {
    "initial": [0.45, 0.45, 0.10],
    "transitions": [[0.98, 0.01, 0.01], [0.01, 0.98, 0.01], [0.025, 0.025, 0.95]],
    "emission_floor": 1e-12,
    "emission_weight": 1.0,
    "temperature": 1.0,
}


def load_e04_config(path=None):
    parent = load_parent_config(None)
    raw = HMM_DEFAULTS.copy()
    if path is not None:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("could not load config: {}".format(exc)) from exc
        unknown = set(data) - {"evidence_mode", "source", "data_dir", "output", "diagnostics", "metadata", "possession", "features", "tag_features", "hmm"}
        if unknown:
            raise ValueError("unknown E04 config keys: {}".format(", ".join(sorted(unknown))))
        shared = dict(data)
        shared.pop("hmm", None)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json") as temp:
            temp.write(json.dumps(shared))
            temp.flush()
            parent = load_parent_config(Path(temp.name))
        hmm = data.get("hmm", {})
        if not isinstance(hmm, dict) or set(hmm) - set(raw):
            raise ValueError("hmm config contains unknown keys or is not an object")
        raw.update(hmm)
    try:
        initial = tuple(raw["initial"])
        transitions = tuple(tuple(row) for row in raw["transitions"])
        if len(transitions) != 3:
            raise ValueError("transition matrix must have three rows")
        _distribution(initial)
        for row in transitions:
            _distribution(row)
        config = HMMConfig(initial, transitions, raw["emission_floor"], raw["emission_weight"], raw["temperature"])
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 < v < float("inf") for v in (config.emission_floor, config.emission_weight, config.temperature)) or config.emission_floor > 1:
            raise ValueError("emission floor, weight and temperature must be finite and positive")
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid HMM config: {}".format(exc)) from exc
    parent["hmm"] = config
    return parent
