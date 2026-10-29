"""Generate a deterministic full-length E01 candidate from local tactical assets.

Run from the competition repository root:
    python -m starter_v3.run_e01 --config starter_v3/config.example.json

The command never downloads data. Inputs are read locally and generated artifacts should remain
under ignored `.local-checkpoints/` storage.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from games import DATA_DIR, GAME, asset_paths, require, source_frames
from starter_v3.ingestion import (
    half_index_by_video_frame,
    iter_atd_frames,
    parse_atd_metadata,
    parse_smart_tagging,
)
from starter_v3.pipeline import (
    InferenceSummaryAccumulator,
    iter_frame_evidence,
    restart_frame_mask,
)
from starter_v3.possession import (
    FrameEvidence,
    PlayerEvidence,
    PossessionConfig,
    iter_infer_possession,
    possession_spells,
)


DEFAULTS = {
    "source": "tactical",
    "data_dir": None,
    "output": ".local-checkpoints/phase5/e01_submission.csv",
    "diagnostics": ".local-checkpoints/phase5/e01_diagnostics.json",
    "metadata": ".local-checkpoints/phase5/e01_run_metadata.json",
    "possession": {},
}
ALLOWED_TOP_LEVEL = frozenset(DEFAULTS)
ALLOWED_POSSESSION = frozenset(PossessionConfig.__dataclass_fields__)


def load_config(path: Optional[Path] = None) -> Dict[str, object]:
    """Load a strict JSON run config; unknown keys fail rather than being silently ignored."""
    config = dict(DEFAULTS)
    if path is not None:
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("could not load config: {}".format(error)) from error
        if not isinstance(payload, dict):
            raise ValueError("config must be a JSON object")
        unknown = set(payload) - ALLOWED_TOP_LEVEL
        if unknown:
            raise ValueError("unknown config keys: {}".format(", ".join(sorted(unknown))))
        config.update(payload)
    if config["source"] != "tactical":
        raise ValueError("E01 submission input must use the tactical source")
    for name in ("output", "diagnostics", "metadata"):
        if not isinstance(config[name], str) or not config[name].strip():
            raise ValueError("{} must be a non-empty path".format(name))
    if config["data_dir"] is not None and not isinstance(config["data_dir"], str):
        raise ValueError("data_dir must be a path string or null")
    possession = config["possession"]
    if not isinstance(possession, dict):
        raise ValueError("possession config must be a JSON object")
    unknown = set(possession) - ALLOWED_POSSESSION
    if unknown:
        raise ValueError("unknown possession config keys: {}".format(", ".join(sorted(unknown))))
    try:
        config["possession"] = PossessionConfig(**possession)
    except (TypeError, ValueError) as error:
        raise ValueError("invalid possession config: {}".format(error)) from error
    return config


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _code_sha256() -> str:
    root = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for name in ("ingestion.py", "possession.py", "pipeline.py", "run_e01.py"):
        digest.update(name.encode("utf-8") + b"\0")
        digest.update((root / name).read_bytes())
    return digest.hexdigest()


def _git_revision() -> Optional[str]:
    repo_root = Path(__file__).resolve().parents[1]
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(repo_root), stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _is_under(path: Path, parent: Path) -> bool:
    try:
        return os.path.commonpath([str(path), str(parent)]) == str(parent)
    except ValueError:
        return False


def _atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=str(path.parent),
        prefix=path.name + ".", suffix=".tmp", delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
        os.replace(str(temporary), str(path))
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _synthetic_self_check() -> int:
    """Exercise the core state semantics without opening competition data."""
    frames = [
        FrameEvidence(i, 1, (0.0, 0.0),
                      (PlayerEvidence("H", 0.25, 0.0), PlayerEvidence("A", 4.0, 0.0)))
        for i in range(3)
    ]
    frames += [
        FrameEvidence(i, 1, None, ()) for i in range(3, 5)
    ]
    frames += [
        FrameEvidence(i, 1, (0.0, 0.0),
                      (PlayerEvidence("A", 0.25, 0.0), PlayerEvidence("H", 4.0, 0.0)))
        for i in range(5, 8)
    ]
    frames.append(FrameEvidence(8, 1, (-1.0, 20.0), ()))
    frames += [
        FrameEvidence(i, 2, (0.0, 0.0),
                      (PlayerEvidence("A", 0.25, 0.0), PlayerEvidence("H", 4.0, 0.0)))
        for i in range(9, 12)
    ]
    labels = [result.label for result in iter_infer_possession(frames)]
    expected = ["X", "X", "H", "H", "H", "H", "H", "A", "D", "X", "X", "A"]
    if labels != expected:
        print("synthetic E01 self-check failed", file=sys.stderr)
        return 1
    if possession_spells(labels) != [("H", 2, 6), ("A", 7, 7), ("A", 11, 11)]:
        print("synthetic E01 spell check failed", file=sys.stderr)
        return 1
    print("synthetic E01 self-check passed")
    return 0


def run_candidate(config: Dict[str, object], data_dir_override: Optional[str] = None) -> Dict[str, object]:
    """Stream ATD into E01, write the full CSV, and save aggregate local diagnostics."""
    configured_data_dir = data_dir_override if data_dir_override is not None else config["data_dir"]
    paths = asset_paths(game=GAME, data_dir=configured_data_dir, source="tactical")
    require(["atd_meta", "atd_raw", "smart_tagging"], game=GAME,
            data_dir=configured_data_dir, source="tactical")
    frame_count = source_frames("tactical", GAME)
    output = Path(str(config["output"])).expanduser().resolve()
    diagnostics_path = Path(str(config["diagnostics"])).expanduser().resolve()
    metadata_path = Path(str(config["metadata"])).expanduser().resolve()
    configured_root = configured_data_dir or DATA_DIR
    data_root = Path(configured_root).expanduser().resolve()
    private_output_root = (Path(__file__).resolve().parents[1] / ".local-checkpoints" / "phase5").resolve()
    for target in (output, diagnostics_path, metadata_path):
        if not _is_under(target, private_output_root):
            raise ValueError("generated files must stay under ignored .local-checkpoints/phase5/")
        if _is_under(target, data_root):
            raise ValueError("generated outputs must stay outside the licensed data directory")
    if len({output, diagnostics_path, metadata_path}) != 3:
        raise ValueError("output, diagnostics, and metadata paths must be distinct")

    started = time.perf_counter()
    metadata = parse_atd_metadata(Path(paths["atd_meta"]))
    events = parse_smart_tagging(Path(paths["smart_tagging"]), expected_frames=frame_count)
    restart_mask = restart_frame_mask(events, frame_count)
    half_mask, _ = half_index_by_video_frame(frame_count)
    raw_frames = iter_atd_frames(
        Path(paths["atd_raw"]), metadata, expected_frames=frame_count, source="tactical", game=GAME
    )
    evidence = iter_frame_evidence(raw_frames, metadata, half_mask, restart_mask)
    possession_config = config["possession"]
    accumulator = InferenceSummaryAccumulator(possession_config.contradiction_confidence)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(("frame", "label"))
            expected_frame = 0
            for result in iter_infer_possession(evidence, possession_config):
                if result.frame != expected_frame:
                    raise ValueError("expected output frame {}, found {}".format(expected_frame, result.frame))
                writer.writerow((result.frame, result.label))
                accumulator.add(result)
                expected_frame += 1
            if expected_frame != frame_count:
                raise ValueError("expected {} inference rows, found {}".format(frame_count, expected_frame))
        os.replace(str(temporary), str(output))
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

    runtime_seconds = time.perf_counter() - started
    report = accumulator.report(runtime_seconds)
    diagnostics_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_json(diagnostics_path, report)
    code_hash = _code_sha256()
    config_for_hash = {
        "source": config["source"],
        "possession": asdict(possession_config),
    }
    config_hash = hashlib.sha256(
        json.dumps(config_for_hash, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    run_metadata = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "game_id": GAME,
        "source": "tactical",
        "frame_count": frame_count,
        "input_identifiers": sorted(Path(paths[key]).name for key in ("atd_meta", "atd_raw", "smart_tagging")),
        "python_version": sys.version.split()[0],
        "git_revision": _git_revision(),
        "possession_config": asdict(possession_config),
        "config_sha256": config_hash,
        "code_sha256": code_hash,
        "output_sha256": _sha256_file(output),
        "runtime_seconds": runtime_seconds,
    }
    _atomic_json(metadata_path, run_metadata)
    print("candidate: {}".format(output))
    print("diagnostics: {}".format(diagnostics_path))
    print("metadata: {}".format(metadata_path))
    print("aggregate: {} labels; {} predicted possessions; {:.2f}s".format(
        frame_count, report["inferences"]["predicted_possession_count"], runtime_seconds
    ))
    return {"output": output, "diagnostics": report, "metadata": run_metadata}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the E01 tactical-frame possession candidate.")
    parser.add_argument("--config", type=Path, help="optional strict JSON config")
    parser.add_argument("--data-dir", help="override MTAH_DATA_DIR for this run")
    parser.add_argument("--output", help="candidate CSV path under ignored .local-checkpoints/phase5/")
    parser.add_argument("--diagnostics", help="aggregate JSON diagnostics path")
    parser.add_argument("--metadata", help="local reproducibility metadata path")
    parser.add_argument("--self-check", action="store_true", help="run synthetic checks without data")
    args = parser.parse_args(argv)
    if args.self_check:
        return _synthetic_self_check()
    try:
        config = load_config(args.config)
        for argument, key in ((args.output, "output"), (args.diagnostics, "diagnostics"),
                              (args.metadata, "metadata")):
            if argument is not None:
                config[key] = argument
        run_candidate(config, data_dir_override=args.data_dir)
        return 0
    except (OSError, ValueError, KeyError) as error:
        print("ERROR: {}".format(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
