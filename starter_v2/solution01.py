"""Foundation CLI for Solution 01; no competition inference is implemented yet.

Examples, run from the repository root::

    python starter_v2/solution01.py --self-check
    python starter_v2/solution01.py --check-inputs
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from games import DEFAULT_SOURCE, require  # noqa: E402
from starter_v2.provenance import (  # noqa: E402
    DEFAULT_SEED,
    experiment_metadata,
    set_random_seed,
    sha256_file,
    write_metadata,
)


VALID_LABELS = {"H", "A", "D", "X"}
ASSETS_BY_SOURCE = {
    "tactical": ("video", "atd_meta", "atd_raw", "homography", "smart_tagging"),
    "broadcast": ("video", "atd_meta", "atd_raw", "homography"),
}


def validate_synthetic_labels(labels: Iterable[str], expected_frames: int) -> None:
    """Validate the synthetic smoke fixture's frame count and output label alphabet."""
    values = list(labels)
    if len(values) != expected_frames:
        raise ValueError("fixture frame count does not match its labels")
    invalid = sorted(set(values) - VALID_LABELS)
    if invalid:
        raise ValueError("fixture contains unsupported labels: {}".format(invalid))


def run_self_check(metadata_path: Optional[Path] = None, seed: int = DEFAULT_SEED) -> dict:
    fixture_path = Path(__file__).parent / "fixtures" / "synthetic_smoke.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    if fixture.get("kind") != "synthetic_only":
        raise ValueError("refusing fixture not marked synthetic_only")
    validate_synthetic_labels(fixture["labels"], int(fixture["frame_count"]))

    seed = int(seed)
    set_random_seed(seed)
    metadata = experiment_metadata(
        input_ids=["synthetic.smoke_fixture"],
        seed=seed,
        input_sha256={"synthetic.smoke_fixture": sha256_file(fixture_path)},
    )
    if metadata_path is not None:
        write_metadata(metadata_path, metadata)
    return {
        "status": "ok",
        "fixture_kind": fixture["kind"],
        "frame_count": fixture["frame_count"],
        "metadata_written": str(metadata_path) if metadata_path else None,
    }


def check_inputs(source: str, data_dir: Optional[str] = None) -> List[str]:
    """Check that all local assets exist; this function never downloads or substitutes data."""
    selected_dir = data_dir or os.environ.get("MTAH_DATA_DIR")
    paths = require(list(ASSETS_BY_SOURCE[source]), source=source, data_dir=selected_dir)
    return ["{}.{}".format(source, name) for name in ASSETS_BY_SOURCE[source]]


def load_config(path: Optional[Path]) -> Dict[str, Any]:
    """Load optional JSON config; reject unknown keys and invalid values."""
    if path is None:
        return {}
    config_path = Path(path)
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("invalid config JSON in {}: {}".format(config_path, error))
    if not isinstance(config, dict):
        raise ValueError("config must be a JSON object")
    unknown = sorted(set(config) - {"source", "data_dir", "seed"})
    if unknown:
        raise ValueError("unknown config key(s): {}".format(", ".join(unknown)))
    if "source" in config and (
        not isinstance(config["source"], str) or config["source"] not in ASSETS_BY_SOURCE
    ):
        raise ValueError("config source must be tactical or broadcast")
    if "data_dir" in config and config["data_dir"] is not None and not isinstance(config["data_dir"], str):
        raise ValueError("config data_dir must be a path string or null")
    if "seed" in config and (not isinstance(config["seed"], int) or isinstance(config["seed"], bool)):
        raise ValueError("config seed must be an integer")
    return config


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--self-check", action="store_true", help="run only the synthetic fixture")
    modes.add_argument("--check-inputs", action="store_true", help="verify local asset presence")
    parser.add_argument("--config", type=Path, help="optional JSON config file")
    parser.add_argument("--source", choices=sorted(ASSETS_BY_SOURCE))
    parser.add_argument("--data-dir", help="asset root; overrides config and MTAH_DATA_DIR")
    parser.add_argument("--seed", type=int, help="random seed; overrides the config value")
    parser.add_argument("--metadata-out", type=Path, help="optional JSON path for self-check metadata")
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
        source = args.source or config.get("source", DEFAULT_SOURCE)
        seed = args.seed if args.seed is not None else config.get("seed", DEFAULT_SEED)
        data_dir = args.data_dir or os.environ.get("MTAH_DATA_DIR") or config.get("data_dir")
        if args.self_check:
            result = run_self_check(args.metadata_out, seed)
        else:
            if args.metadata_out:
                parser.error("--metadata-out is only valid with --self-check")
            result = {"status": "ok", "source": source,
                      "available_input_ids": check_inputs(source, data_dir)}
    except (OSError, ValueError, KeyError) as error:
        print("Solution 01: {}".format(error), file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
