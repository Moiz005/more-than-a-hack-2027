"""Generate deterministic E01-compatible or E02 possession candidates from local assets.

Run from the competition repository root:
    python -m starter_v4.run_e01 --evidence-mode e02 --config starter_v4/config.example.json

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

try:
    import resource
except ImportError:  # pragma: no cover - Windows has no resource module.
    resource = None

from games import DATA_DIR, GAME, asset_paths, require, source_frames
from starter_v5.features import E02Config
from starter_v5.inference import iter_infer_e02
from starter_v5.ingestion import (
    half_index_by_video_frame,
    iter_atd_frames,
    parse_atd_metadata,
    parse_smart_tagging,
)
from starter_v5.pipeline import (
    E02SummaryAccumulator,
    InferenceSummaryAccumulator,
    TagAblationAccumulator,
    iter_frame_evidence,
    restart_frame_mask,
)
from starter_v5.possession import (
    FrameEvidence,
    PlayerEvidence,
    PossessionConfig,
    iter_infer_possession,
    possession_spells,
)
from starter_v5.tag_features import TagEvidence, iter_tag_evidence


DEFAULTS = {
    "evidence_mode": "e02",
    "source": "tactical",
    "data_dir": None,
    "output": ".local-checkpoints/phase7/e03_submission.csv",
    "diagnostics": ".local-checkpoints/phase7/e03_diagnostics.json",
    "metadata": ".local-checkpoints/phase7/e03_run_metadata.json",
    "possession": {},
    "features": {},
    "tag_features": {"enabled": True},
}
ALLOWED_TOP_LEVEL = frozenset(DEFAULTS)
ALLOWED_POSSESSION = frozenset(PossessionConfig.__dataclass_fields__)
ALLOWED_FEATURES = frozenset(E02Config.__dataclass_fields__)


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
        raise ValueError("submission input must use the tactical source")
    if not isinstance(config["evidence_mode"], str) or config["evidence_mode"] not in {"e01", "e02", "e03"}:
        raise ValueError("evidence_mode must be e01, e02, or e03")
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
    features = config["features"]
    if not isinstance(features, dict):
        raise ValueError("features config must be a JSON object")
    unknown = set(features) - ALLOWED_FEATURES
    if unknown:
        raise ValueError("unknown feature config keys: {}".format(", ".join(sorted(unknown))))
    try:
        config["features"] = E02Config(**features)
    except (TypeError, ValueError) as error:
        raise ValueError("invalid feature config: {}".format(error)) from error
    if config["evidence_mode"] == "e02" and (
        abs(config["features"].pitch_length_m - config["possession"].pitch_length_m) > 1e-9
        or abs(config["features"].pitch_width_m - config["possession"].pitch_width_m) > 1e-9
    ):
        raise ValueError("feature and possession pitch dimensions must match")
    tag_features = config["tag_features"]
    if not isinstance(tag_features, dict) or set(tag_features) - {"enabled"}:
        raise ValueError("tag_features accepts only the enabled key")
    if not isinstance(tag_features.get("enabled", True), bool):
        raise ValueError("tag_features.enabled must be boolean")
    config["tag_features"] = {"enabled": tag_features.get("enabled", True)}
    return config


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _code_sha256() -> str:
    root = Path(__file__).resolve().parent
    sources = [
        ("starter_v5/ingestion.py", root / "ingestion.py"),
        ("starter_v5/possession.py", root / "possession.py"),
        ("starter_v5/pipeline.py", root / "pipeline.py"),
        ("starter_v5/features.py", root / "features.py"),
        ("starter_v5/inference.py", root / "inference.py"),
        ("starter_v5/tag_features.py", root / "tag_features.py"),
        ("starter_v5/emissions.py", root / "emissions.py"),
        ("starter_v5/run_e01.py", root / "run_e01.py"),
        ("games.py", root.parent / "games.py"),
    ]
    digest = hashlib.sha256()
    for name, path in sources:
        digest.update(name.encode("utf-8") + b"\0")
        digest.update(path.read_bytes())
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
    from starter_v5.emissions import frame_emission
    neutral = frame_emission(0, 1)
    if (neutral.home, neutral.away, neutral.dead) != (1 / 3, 1 / 3, 1 / 3) or neutral.informative:
        print("synthetic E03 emission self-check failed", file=sys.stderr)
        return 1
    print("synthetic E03 self-check passed")
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
    private_output_root = (Path(__file__).resolve().parents[1] / ".local-checkpoints" / "phase7").resolve()
    for target in (output, diagnostics_path, metadata_path):
        if not _is_under(target, private_output_root):
            raise ValueError("generated files must stay under ignored .local-checkpoints/phase7/")
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
    evidence_mode = str(config["evidence_mode"])
    feature_config = config["features"]
    if evidence_mode in {"e02", "e03"} and (
        abs(feature_config.pitch_length_m - possession_config.pitch_length_m) > 1e-9
        or abs(feature_config.pitch_width_m - possession_config.pitch_width_m) > 1e-9
    ):
        raise ValueError("feature and possession pitch dimensions must match")
    tag_rows = iter_tag_evidence(events, frame_count) if evidence_mode == "e03" and config["tag_features"]["enabled"] else None
    tags = tag_rows
    if evidence_mode in {"e02", "e03"}:
        inference = iter_infer_e02(evidence, possession_config, feature_config, tag_evidence=tags)
        accumulator = E02SummaryAccumulator(possession_config.contradiction_confidence)
    else:
        inference = iter_infer_possession(evidence, possession_config)
        accumulator = InferenceSummaryAccumulator(possession_config.contradiction_confidence)
    ablation = None
    ablation_inference = None
    if evidence_mode == "e03" and tags is not None:
        ablation = TagAblationAccumulator()
        comparison_raw = iter_atd_frames(
            Path(paths["atd_raw"]), metadata, expected_frames=frame_count, source="tactical", game=GAME
        )
        comparison_evidence = iter_frame_evidence(comparison_raw, metadata, half_mask, restart_mask)
        ablation_inference = iter_infer_e02(comparison_evidence, possession_config, feature_config)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(("frame", "label"))
            expected_frame = 0
            for result in inference:
                inference_result = result.inference if evidence_mode in {"e02", "e03"} else result
                if inference_result.frame != expected_frame:
                    raise ValueError("expected output frame {}, found {}".format(expected_frame, inference_result.frame))
                writer.writerow((inference_result.frame, inference_result.label))
                accumulator.add(result)
                if ablation_inference is not None:
                    try:
                        without_tags = next(ablation_inference)
                    except StopIteration as error:
                        raise ValueError("tag-disabled E02 comparison ended before E03") from error
                    ablation.add(result, without_tags)
                expected_frame += 1
            if expected_frame != frame_count:
                raise ValueError("expected {} inference rows, found {}".format(frame_count, expected_frame))
            if ablation_inference is not None:
                try:
                    next(ablation_inference)
                except StopIteration:
                    pass
                else:
                    raise ValueError("tag-disabled E02 comparison contains extra rows")
        os.replace(str(temporary), str(output))
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

    runtime_seconds = time.perf_counter() - started
    peak_memory_mb = None
    if resource is not None:
        peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak_memory_mb = peak_rss / (1024.0 * 1024.0) if sys.platform == "darwin" else peak_rss / 1024.0
    if evidence_mode in {"e02", "e03"}:
        report = accumulator.report(runtime_seconds, peak_memory_mb)
    else:
        report = accumulator.report(runtime_seconds)
    if evidence_mode in {"e02", "e03"}:
        emission_report = report["emissions"]
        if emission_report["frame_count"] != frame_count or emission_report["invalid_emission_frames"] != 0:
            raise ValueError("emissions must be valid and present on every tactical frame")
    if tag_rows is not None:
        from collections import Counter
        family_counts, conflict_count, overlap_count, restart_count, goal_count = Counter(), 0, 0, 0, 0
        team_counts = Counter(event.team or "UNKNOWN" for event in events)
        for row in tag_rows:
            family_counts.update(row.families)
            conflict_count += int(row.team_conflict)
            overlap_count += int(row.overlap)
            restart_count += int(row.restart_context)
            goal_count += int(row.goal_context)
        report["tag_observations"] = {
            "event_count": len(events),
            "counts_by_normalized_team": dict(sorted(team_counts.items())),
            "frames_with_tag_evidence": sum(row.active for row in tag_rows),
            "active_family_frame_counts": dict(sorted(family_counts.items())),
            "overlap_frames": overlap_count,
            "conflict_frames": conflict_count,
            "restart_context_frames": restart_count,
            "goal_context_frames": goal_count,
            "ground_truth_used": False,
        }
    if ablation is not None:
        if ablation.frame_count != frame_count:
            raise ValueError("tag ablation comparison must cover every tactical frame")
        report["tag_fusion"]["paired_e02_comparison"] = ablation.report()
    diagnostics_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_json(diagnostics_path, report)
    code_hash = _code_sha256()
    config_for_hash = {
        "source": config["source"],
        "possession": asdict(possession_config),
    }
    if evidence_mode in {"e02", "e03"}:
        config_for_hash["evidence_mode"] = evidence_mode
        config_for_hash["features"] = asdict(feature_config)
    if evidence_mode == "e03":
        config_for_hash["tag_features"] = config["tag_features"]
    config_hash = hashlib.sha256(
        json.dumps(config_for_hash, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    run_metadata = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "game_id": GAME,
        "source": "tactical",
        "evidence_mode": evidence_mode,
        "frame_count": frame_count,
        "input_identifiers": sorted(Path(paths[key]).name for key in ("atd_meta", "atd_raw", "smart_tagging")),
        "python_version": sys.version.split()[0],
        "git_revision": _git_revision(),
        "possession_config": asdict(possession_config),
        "feature_config": asdict(feature_config) if evidence_mode in {"e02", "e03"} else None,
        "tag_features": config["tag_features"] if evidence_mode == "e03" else None,
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
    parser = argparse.ArgumentParser(description="Generate E01, E02, or E03 tactical-frame candidate.")
    parser.add_argument("--evidence-mode", choices=("e01", "e02", "e03"), help="select inference evidence mode")
    parser.add_argument("--config", type=Path, help="optional strict JSON config")
    parser.add_argument("--data-dir", help="override MTAH_DATA_DIR for this run")
    parser.add_argument("--output", help="candidate CSV path under ignored .local-checkpoints/phase7/")
    parser.add_argument("--diagnostics", help="aggregate JSON diagnostics path")
    parser.add_argument("--metadata", help="local reproducibility metadata path")
    parser.add_argument("--self-check", action="store_true", help="run synthetic checks without data")
    args = parser.parse_args(argv)
    if args.self_check:
        return _synthetic_self_check()
    try:
        config = load_config(args.config)
        if args.evidence_mode is not None:
            config["evidence_mode"] = args.evidence_mode
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
