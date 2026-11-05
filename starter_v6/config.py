"""Strict E04 JSON configuration loading."""
import json
import tempfile
from dataclasses import replace
from pathlib import Path

from starter_v6.run_e01 import load_config as load_parent_config
from starter_v6.hmm import HMMConfig, _distribution

HMM_DEFAULTS = {
    "initial": [0.45, 0.45, 0.10],
    "transitions": [[0.98, 0.01, 0.01], [0.01, 0.98, 0.01], [0.025, 0.025, 0.95]],
    "emission_floor": 1e-12,
    "emission_weight": 1.0,
    "temperature": 1.0,
}
OWNERSHIP_MODES = {
    "v3_exact": (False, True),
    "atd_control": (True, False),
    "atd_control_plus_context": (True, True),
}
INTEGRATION_MODES = {
    # Incremental switches: V3's existing tag context remains available in all modes.
    "exact_v3": (False, False, False),
    "atd_only": (True, False, False),
    "tag_context_only": (False, True, True),
    "atd_plus_tag": (True, True, True),
    "stage1_then_stage2": (True, True, True),
}
INTEGRATION_OWNERSHIP_MODES = {
    "exact_v3": "v3_exact",
    "atd_only": "atd_control_plus_context",
    "tag_context_only": "v3_exact",
    "atd_plus_tag": "atd_control_plus_context",
    "stage1_then_stage2": "atd_control_plus_context",
}


def load_e04_config(path=None):
    parent = load_parent_config(None)
    raw = HMM_DEFAULTS.copy()
    ownership_mode = None
    integration_mode = None
    if path is not None:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("could not load config: {}".format(exc)) from exc
        if not isinstance(data, dict):
            raise ValueError("E04 config must be a JSON object")
        unknown = set(data) - {"evidence_mode", "source", "data_dir", "output", "diagnostics", "metadata", "possession", "features", "tag_features", "hmm", "ownership_mode", "integration_mode"}
        if unknown:
            raise ValueError("unknown E04 config keys: {}".format(", ".join(sorted(unknown))))
        if "integration_mode" in data:
            integration_mode = data["integration_mode"]
            if (not isinstance(integration_mode, str)
                    or integration_mode not in INTEGRATION_MODES):
                raise ValueError("integration_mode must be one of: {}".format(
                    ", ".join(INTEGRATION_MODES),
                ))
        if "ownership_mode" in data:
            ownership_mode = data["ownership_mode"]
            if not isinstance(ownership_mode, str) or ownership_mode not in OWNERSHIP_MODES:
                raise ValueError("ownership_mode must be one of: {}".format(", ".join(OWNERSHIP_MODES)))
        if integration_mode is not None and ownership_mode is not None:
            raise ValueError("integration_mode and ownership_mode cannot both be set")
        shared = dict(data)
        shared.pop("hmm", None)
        shared.pop("ownership_mode", None)
        shared.pop("integration_mode", None)
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
    if ownership_mode is not None:
        atd_enabled, context_enabled = OWNERSHIP_MODES[ownership_mode]
        parent["features"] = replace(
            parent["features"], atd_signal_fusion_enabled=atd_enabled,
        )
        parent["tag_features"] = {"enabled": context_enabled}
    if integration_mode is not None:
        atd_enabled, stage1_enabled, stage2_mask_enabled = INTEGRATION_MODES[integration_mode]
        parent["features"] = replace(
            parent["features"],
            atd_signal_fusion_enabled=atd_enabled,
            stage1_lifecycle_enabled=stage1_enabled,
            stage1_stage2_fusion_enabled=stage2_mask_enabled,
        )
        # Smart Tag team priors are part of the V3 baseline in every controlled mode;
        # this switch isolates the new typed Stage 1 tag/lifecycle contribution.
        parent["tag_features"] = {"enabled": True}
    parent["ownership_mode"] = (
        ownership_mode or INTEGRATION_OWNERSHIP_MODES.get(integration_mode, "custom")
    )
    parent["integration_mode"] = integration_mode or "custom"
    return parent
