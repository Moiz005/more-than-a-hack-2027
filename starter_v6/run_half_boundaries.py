"""Run the HBK-01 boundary experiment around the verified E04 runner.

The wrapper never reimplements possession inference.  It invokes
``starter_v6.run_e04`` into a private temporary baseline, optionally detects
opening-kickoff execution from tactical ATD/Smart Tag inputs, and applies the
pure Phase 4 policy only when explicitly requested in ``overlay`` mode.

Run from the repository root with a unique local run directory, for example::

    python -m starter_v6.run_half_boundaries --config starter_v6/config.hbk01.example.json \
        --run-id audit-001

The command never downloads data.  Licensed inputs and generated artifacts
remain local under ``.local-checkpoints/hbk01/<run-id>/``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import platform
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from games import GAME, asset_paths
from starter_v6 import run_e04
from starter_v6.ingestion import (
    iter_atd_frames,
    parse_atd_metadata,
    parse_smart_tagging,
)
from starter_v6.provenance import (
    dependency_manifest,
    file_sha256,
    runtime_source_files,
    source_manifest,
    source_sha256,
)
from starter_v6.timeline import build_tactical_timeline, validate_tactical_reference
from starter_v6.half_boundary_policy import (
    AUDIT,
    BoundaryOverlayResult,
    OVERLAY,
    REJECTED,
    apply_kickoff_prefix,
)
from starter_v6.kickoff_atd import (
    CONFIRMED,
    KickoffATDConfig,
    KickoffDetectionResult,
    detect_kickoff_execution,
)
from starter_v6.kickoff_tags import (
    MISSING_TAG,
    KickoffTagCandidate,
    extract_opening_kickoff_candidates,
)


MODES = ("off", "audit", "overlay")
DEFAULT_CHECKPOINT_ROOT = ".local-checkpoints/hbk01"
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
POST_KICKOFF_AUDIT_FRAMES = 250  # fixed 10-second diagnostic window at 25 FPS

DEFAULTS = {
    "parent_config": "starter_v6/config.example.json",
    "mode": "audit",
    "source": "tactical",
    "data_dir": None,
    "run_id": "manual-run",
    "output": "submission.csv",
    "diagnostics": "diagnostics.json",
    "metadata": "run_metadata.json",
    "detector": {},
}
ALLOWED_KEYS = frozenset(DEFAULTS)


def _validate_config(config: Mapping[str, object]) -> Dict[str, object]:
    values = dict(config)
    unknown = set(values) - ALLOWED_KEYS
    if unknown:
        raise ValueError("unknown HBK-01 config keys: {}".format(", ".join(sorted(unknown))))
    if values.get("source") != "tactical":
        raise ValueError("HBK-01 source must be tactical")
    if values.get("mode") not in MODES:
        raise ValueError("mode must be one of: {}".format(", ".join(MODES)))
    run_id = values.get("run_id")
    if not isinstance(run_id, str) or not RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError("run_id must contain only letters, digits, '.', '_' and '-'")
    if values.get("data_dir") is not None and not isinstance(values["data_dir"], str):
        raise ValueError("data_dir must be a path string or null")
    if not isinstance(values.get("parent_config"), str) or not values["parent_config"].strip():
        raise ValueError("parent_config must be a non-empty path")
    for name in ("output", "diagnostics", "metadata"):
        if not isinstance(values.get(name), str) or not values[name].strip():
            raise ValueError("{} must be a non-empty path".format(name))
    if len({values["output"], values["diagnostics"], values["metadata"]}) != 3:
        raise ValueError("output, diagnostics, and metadata must be distinct")
    detector = values.get("detector")
    if isinstance(detector, KickoffATDConfig):
        values["detector"] = detector
    else:
        if not isinstance(detector, dict):
            raise ValueError("detector config must be a JSON object")
        try:
            values["detector"] = KickoffATDConfig(**detector)
        except (TypeError, ValueError) as error:
            raise ValueError("invalid detector config: {}".format(error)) from error
    return values


def load_hbk_config(path: Optional[Path] = None) -> Dict[str, object]:
    """Load the separate, strict HBK-01 configuration schema."""
    values = dict(DEFAULTS)
    if path is not None:
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("could not load HBK-01 config: {}".format(error)) from error
        if not isinstance(payload, dict):
            raise ValueError("HBK-01 config must be a JSON object")
        values.update(payload)
    return _validate_config(values)


def _config_for_json(config: Mapping[str, object]) -> Dict[str, object]:
    return {
        key: asdict(value) if is_dataclass(value) else value
        for key, value in config.items()
    }


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _resolve_run_targets(
    project_root: Path,
    config: Mapping[str, object],
    checkpoint_root: str = DEFAULT_CHECKPOINT_ROOT,
    overwrite: bool = False,
    require_output: bool = True,
) -> Tuple[Path, Path, Path]:
    """Resolve all artifacts below one run directory and enforce no clobbering."""
    root = (project_root / checkpoint_root).resolve()
    run_root = (root / str(config["run_id"])).resolve()
    if not _is_relative_to(run_root, root) or run_root == root:
        raise ValueError("run_id must resolve below the checkpoint root")
    raw_targets = [Path(str(config[name])) for name in ("output", "diagnostics", "metadata")]
    targets = tuple(
        (item if item.is_absolute() else run_root / item).resolve()
        for item in raw_targets
    )
    if len(set(targets)) != 3 or any(not _is_relative_to(target, run_root) for target in targets):
        raise ValueError("all artifacts must be distinct paths below the run directory")
    for index, target in enumerate(targets):
        if target.exists() and (require_output or index != 0) and not overwrite:
            raise ValueError("refusing to overwrite existing HBK-01 artifact: {}".format(target))
    return targets


def _atomic_write_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_bytes(value)
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _submission_bytes(labels: Sequence[str]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(("frame", "label"))
    writer.writerows(enumerate(labels))
    return buffer.getvalue().encode("utf-8")


def _read_submission(path: Path, expected_count: int) -> Tuple[str, ...]:
    labels: List[str] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        if next(reader, None) != ["frame", "label"]:
            raise ValueError("parent E04 output has an invalid header")
        for expected_frame, row in enumerate(reader):
            if len(row) != 2 or row[0] != str(expected_frame) or row[1] not in {"H", "A", "D", "X"}:
                raise ValueError("parent E04 output is not an ordered valid submission")
            labels.append(row[1])
    if len(labels) != expected_count:
        raise ValueError("parent E04 output has {} rows, expected {}".format(len(labels), expected_count))
    return tuple(labels)


def _parent_config_path(project_root: Path, config: Mapping[str, object]) -> Path:
    path = Path(str(config["parent_config"]))
    if not path.is_absolute():
        path = project_root / path
    path = path.resolve()
    if not path.is_file():
        raise ValueError("parent E04 config does not exist: {}".format(path))
    return path


def _run_parent(
    project_root: Path,
    parent_config_path: Path,
    data_dir: Optional[str],
    temporary_root: Path,
) -> Tuple[bytes, Tuple[str, ...], Mapping[str, object], Dict[str, Path]]:
    """Run the canonical E04 entrypoint into an isolated temporary directory."""
    temporary_root.mkdir(parents=True, exist_ok=True)
    parent_output = temporary_root / "parent_submission.csv"
    parent_diagnostics = temporary_root / "parent_diagnostics.json"
    parent_metadata = temporary_root / "parent_metadata.json"
    arguments = [
        "--config", str(parent_config_path),
        "--output", str(parent_output),
        "--diagnostics", str(parent_diagnostics),
        "--metadata", str(parent_metadata),
        "--checkpoint-root", str(temporary_root),
    ]
    if data_dir is not None:
        arguments.extend(("--data-dir", data_dir))
    exit_code = run_e04.main(arguments)
    if exit_code != 0:
        raise RuntimeError("starter_v6.run_e04 failed with exit code {}".format(exit_code))
    timeline = build_tactical_timeline()
    raw_bytes = parent_output.read_bytes()
    labels = _read_submission(parent_output, timeline.frame_count)
    parent_metadata_value = json.loads(parent_metadata.read_text(encoding="utf-8"))
    paths = asset_paths(game=GAME, data_dir=data_dir, source="tactical")
    return raw_bytes, labels, parent_metadata_value, {key: Path(value) for key, value in paths.items()}


def _missing_detection(status: str, reasons: Sequence[str]) -> KickoffDetectionResult:
    return KickoffDetectionResult(
        status=status,
        execution_frame=None,
        video_timestamp_seconds=None,
        reasons=tuple(dict.fromkeys(reasons)),
        candidates=(),
        evaluated_frames=0,
    )


def _candidate_frames(
    atd_path: Path,
    metadata: object,
    expected_frames: int,
    candidate: KickoffTagCandidate,
) -> Iterable[object]:
    for frame in iter_atd_frames(
        atd_path, metadata, expected_frames=expected_frames,
        source="tactical", game=GAME,
    ):
        if frame.video_frame >= candidate.search_end_frame:
            break
        if frame.video_frame >= candidate.search_start_frame:
            yield frame


def _detect_opening_kickoffs(
    paths: Mapping[str, Path],
    timeline: object,
    detector_config: KickoffATDConfig,
) -> Tuple[Mapping[int, KickoffDetectionResult], object]:
    metadata = parse_atd_metadata(paths["atd_meta"])
    events = parse_smart_tagging(paths["smart_tagging"], expected_frames=timeline.frame_count)
    inventory = extract_opening_kickoff_candidates(events, timeline=timeline)
    results: Dict[int, KickoffDetectionResult] = {}
    for half in (1, 2):
        candidates = inventory.candidates_for_half(half)
        if len(candidates) != 1:
            status = AMBIGUOUS if len(candidates) > 1 else MISSING_TAG
            results[half] = _missing_detection(status, (
                "tag_status_{}".format(inventory.status_for_half(half)),
            ))
            continue
        candidate = candidates[0]
        results[half] = detect_kickoff_execution(
            _candidate_frames(paths["atd_raw"], metadata, timeline.frame_count, candidate),
            metadata, candidate, timeline=timeline, config=detector_config,
        )
    return results, inventory


def _candidate_dict(candidate: KickoffTagCandidate) -> Dict[str, object]:
    return {
        "event_index": candidate.event_index,
        "source": candidate.source,
        "code": candidate.code,
        "type": candidate.type_value,
        "team": candidate.team_value,
        "half_value": candidate.half_value,
        "half": candidate.half,
        "raw_start_seconds": candidate.raw_start_seconds,
        "raw_end_seconds": candidate.raw_end_seconds,
        "start_frame": candidate.start_frame,
        "end_frame": candidate.end_frame,
        "search_start_frame": candidate.search_start_frame,
        "search_end_frame": candidate.search_end_frame,
        "eligible": candidate.eligible,
        "selection_explanation": candidate.selection_explanation,
        "warnings": list(candidate.warnings),
    }


def _detection_dict(result: KickoffDetectionResult) -> Dict[str, object]:
    return {
        "status": result.status,
        "evidence_state": result.evidence_state,
        "execution_frame": result.execution_frame,
        "video_timestamp_seconds": result.video_timestamp_seconds,
        "execution_interval": list(result.execution_interval) if result.execution_interval is not None else None,
        "reasons": list(result.reasons),
        "evaluated_frames": result.evaluated_frames,
        "evidence_trace": result.trace.as_dict() if result.trace is not None else None,
        "candidates": [
            {
                "execution_frame": item.execution_frame,
                "displacement_m": item.displacement_m,
                "derived_speed_mps": item.derived_speed_mps,
                "provider_speed_mps": item.provider_speed_mps,
                "evidence": list(item.evidence),
            }
            for item in result.candidates
        ],
    }


def _policy_dict(policy: Optional[BoundaryOverlayResult]) -> Dict[str, object]:
    if policy is None:
        return {"status": "NOT_RUN"}
    return {
        "mode": policy.mode,
        "status": policy.status,
        "reason": policy.reason,
        "permitted_interval": policy.permitted_interval,
        "changed_frames": list(policy.changed_frames),
        "changed_counts": [list(item) for item in policy.changed_counts],
        "unchanged_frame_count": policy.unchanged_frame_count,
        "preservation_assertions": dict(policy.preservation_assertions),
    }


def _half_summary(results: Mapping[int, KickoffDetectionResult], half: int) -> Dict[str, object]:
    result = results[half]
    return _detection_dict(result)


def _post_kickoff_dead_count(
    labels: Sequence[str],
    timeline: object,
    result: KickoffDetectionResult,
) -> Optional[int]:
    if result.status != CONFIRMED or result.execution_frame is None:
        return None
    second_end = next(end for half, _, end in timeline.half_ranges if half == 2)
    stop = min(second_end + 1, result.execution_frame + POST_KICKOFF_AUDIT_FRAMES)
    return sum(label == "D" for label in labels[result.execution_frame:stop])


def synthetic_self_check() -> str:
    """Exercise config-independent runner/policy plumbing without match assets."""
    from starter_v6.timeline import TacticalTimeline

    mask = bytearray(12)
    mask[1:4] = bytes([1]) * 3
    mask[7:11] = bytes([2]) * 4
    timeline = TacticalTimeline("tactical", 25, 12, bytes(mask), ((1, 1, 3), (2, 7, 10)))
    labels = ("X", "H", "H", "D", "X", "X", "X", "A", "A", "D", "H", "X")
    confirmed = _missing_detection(CONFIRMED, ())
    confirmed = KickoffDetectionResult(
        status=CONFIRMED, execution_frame=9, video_timestamp_seconds=9 / 25.0,
        reasons=("synthetic",), candidates=(), evaluated_frames=0,
    )
    policy = apply_kickoff_prefix(labels, timeline, {2: confirmed}, mode=OVERLAY)
    if policy.status != "APPLIED" or policy.labels[7:11] != ("D", "D", "D", "H"):
        raise ValueError("synthetic HBK-01 runner self-check failed")
    return "passed"


def _run(config: Mapping[str, object], config_path: Optional[Path], checkpoint_root: str,
         overwrite: bool, project_root: Path) -> int:
    started = time.perf_counter()
    config = _validate_config(config)
    mode = str(config["mode"])
    targets = _resolve_run_targets(
        project_root, config, checkpoint_root=checkpoint_root,
        overwrite=overwrite, require_output=mode != "audit",
    )
    parent_path = _parent_config_path(project_root, config)
    parent_config = run_e04.load_e04_config(parent_path)
    if parent_config.get("source") != "tactical":
        raise ValueError("parent E04 config must use the tactical source")
    data_dir = config["data_dir"] if config["data_dir"] is not None else parent_config.get("data_dir")
    if data_dir is not None and not isinstance(data_dir, str):
        raise ValueError("effective data_dir must be a path string or null")
    run_root = targets[0].parent
    output_bytes: Optional[bytes] = None
    parent_labels: Tuple[str, ...]
    final_labels: Tuple[str, ...]
    parent_metadata: Mapping[str, object]
    paths: Mapping[str, Path]
    results: Mapping[int, KickoffDetectionResult] = {}
    inventory = None
    policy = None
    warnings: List[str] = []
    parent_output_sha256 = None

    run_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".parent-", dir=str(run_root)) as temporary:
        parent_bytes, parent_labels, parent_metadata, paths = _run_parent(
            project_root, parent_path, data_dir, Path(temporary),
        )
        parent_output_sha256 = hashlib.sha256(parent_bytes).hexdigest()
        timeline = build_tactical_timeline()
        validate_tactical_reference(timeline.source, timeline.fps, timeline.frame_count)
        if mode == "off":
            final_labels = parent_labels
            output_bytes = parent_bytes
        else:
            results, inventory = _detect_opening_kickoffs(
                paths, timeline, config["detector"],
            )
            policy = apply_kickoff_prefix(
                parent_labels, timeline, results, mode=AUDIT if mode == "audit" else OVERLAY,
            )
            final_labels = policy.labels
            if mode == "overlay" and policy.status != REJECTED:
                output_bytes = _submission_bytes(final_labels)
            elif mode == "overlay":
                warnings.append("overlay_not_written_unconfirmed_kickoff")

    if output_bytes is not None:
        _atomic_write_bytes(targets[0], output_bytes)

    elapsed = time.perf_counter() - started
    second_result = results.get(2)
    first_result = results.get(1)
    changed_counter = Counter(
        (before, after)
        for before, after in zip(parent_labels, final_labels)
        if before != after
    )
    changed_frames = tuple(
        index for index, (before, after) in enumerate(zip(parent_labels, final_labels))
        if before != after
    )
    report = {
        "experiment": "HBK-01",
        "mode": mode,
        "timeline": {
            "source": timeline.source,
            "fps": timeline.fps,
            "frame_count": timeline.frame_count,
            "half_ranges": [list(item) for item in timeline.half_ranges],
        },
        "parent_output_sha256": parent_output_sha256,
        "candidates": [
            _candidate_dict(item) for item in (inventory.records if inventory is not None else ())
        ],
        "detectors": {
            str(half): _half_summary(results, half) for half in sorted(results)
        },
        "k1": _detection_dict(first_result) if first_result is not None and first_result.status == CONFIRMED else None,
        "k2": _detection_dict(second_result) if second_result is not None and second_result.status == CONFIRMED else None,
        "hypothetical_second_half_prefix": policy.permitted_interval if policy is not None else None,
        "boundary_policy": _policy_dict(policy),
        "old_label_counts": dict(sorted(Counter(parent_labels).items())),
        "new_label_counts": dict(sorted(Counter(final_labels).items())),
        "changed_frames": list(changed_frames),
        "changed_frame_count": len(changed_frames),
        "changed_counts": [list(key) + [count] for key, count in sorted(changed_counter.items())],
        "post_kickoff_D_count_250_frames": (
            _post_kickoff_dead_count(final_labels, timeline, second_result)
            if second_result is not None else None
        ),
        "warnings": warnings,
        "parent_metadata": {
            "output_sha256": parent_metadata.get("output_sha256"),
            "git_revision": parent_metadata.get("git_revision"),
            "config_sha256": parent_metadata.get("config_sha256"),
        },
        "local_only": True,
        "ground_truth_used": False,
        "runtime_seconds": elapsed,
    }
    from starter_v6.provenance import atomic_write_text
    atomic_write_text(targets[1], json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")

    source_files = runtime_source_files(project_root)
    input_identifiers = {
        key: {"filename": path.name, "sha256": file_sha256(path)}
        for key, path in paths.items()
        if key in {"atd_meta", "atd_raw", "smart_tagging"} and path.is_file()
    }
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=str(project_root), text=True,
    ).strip()
    provenance = {
        "experiment": "HBK-01",
        "mode": mode,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_revision": revision,
        "git_worktree_dirty": bool(
            subprocess.check_output(["git", "status", "--porcelain"], cwd=str(project_root), text=True).strip()
        ),
        "parent": "starter_v6.run_e04",
        "parent_config": str(parent_path.relative_to(project_root)),
        "parent_config_sha256": file_sha256(parent_path),
        "hbk_config": str(config_path.relative_to(project_root)) if config_path is not None else None,
        "hbk_config_sha256": file_sha256(config_path) if config_path is not None else None,
        "effective_config": _config_for_json(config),
        "source_sha256": source_sha256(source_files, project_root),
        "source_manifest": source_manifest(source_files, project_root),
        "dependency_manifest": dependency_manifest(),
        "input_identifiers": input_identifiers,
        "output_sha256": file_sha256(targets[0]) if targets[0].exists() else None,
        "run_paths": {
            "output": str(targets[0].relative_to(project_root)),
            "diagnostics": str(targets[1].relative_to(project_root)),
            "metadata": str(targets[2].relative_to(project_root)),
        },
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "runtime_seconds": elapsed,
        "frame_count": timeline.frame_count,
        "local_only": True,
        "ground_truth_used": False,
    }
    atomic_write_text(targets[2], json.dumps(provenance, indent=2, sort_keys=True, allow_nan=False) + "\n")
    if mode == "overlay" and policy is not None and policy.status == REJECTED:
        print("ERROR: overlay rejected: {}".format(policy.reason), file=sys.stderr)
        return 2
    print("HBK-01 {} complete; diagnostics written to {}".format(mode, targets[1]))
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("starter_v6/config.hbk01.example.json"))
    parser.add_argument("--mode", choices=MODES)
    parser.add_argument("--run-id")
    parser.add_argument("--data-dir")
    parser.add_argument("--output")
    parser.add_argument("--diagnostics")
    parser.add_argument("--metadata")
    parser.add_argument("--checkpoint-root", default=DEFAULT_CHECKPOINT_ROOT)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args(argv)
    if args.self_check:
        try:
            print("HBK-01 self-check {}".format(synthetic_self_check()))
            return 0
        except (OSError, ValueError) as error:
            print("ERROR: {}".format(error), file=sys.stderr)
            return 2
    try:
        config = load_hbk_config(args.config)
        overrides = {
            "mode": args.mode,
            "run_id": args.run_id,
            "data_dir": args.data_dir,
            "output": args.output,
            "diagnostics": args.diagnostics,
            "metadata": args.metadata,
        }
        config.update({key: value for key, value in overrides.items() if value is not None})
        project_root = Path(__file__).resolve().parents[1]
        return _run(config, args.config.resolve(), args.checkpoint_root, args.overwrite, project_root)
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.CalledProcessError) as error:
        print("ERROR: {}".format(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
