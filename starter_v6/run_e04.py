"""E04 offline decoder over the E03 evidence stream; outputs are local only."""
import argparse
import csv
import json
import math
import platform
import resource
import sys
import time
import subprocess
from pathlib import Path
from types import SimpleNamespace

from games import GAME, asset_paths, require, source_frames
from starter_v5.ingestion import half_index_by_video_frame, iter_atd_frames, parse_atd_metadata, parse_smart_tagging
from starter_v5.inference import iter_infer_e02
from starter_v5.pipeline import iter_frame_evidence, restart_frame_mask
from starter_v6.config import load_e04_config
from starter_v5.tag_features import iter_tag_evidence
from starter_v6.hmm import decode
from starter_v6.diagnostics import build_diagnostics
from starter_v6.provenance import atomic_write_text, config_sha256, effective_config, file_sha256, source_sha256
from starter_v6.hmm import HMMConfig


def synthetic_self_check():
    """Run semantic H-D-H and half-reset checks without loading competition assets."""
    cfg = HMMConfig(
        initial=(0.98, 0.01, 0.01),
        transitions=((0.97, 0.01, 0.02), (0.01, 0.97, 0.02), (0.01, 0.01, 0.98)),
    )
    values = [(0.98, 0.01, 0.01)] * 3 + [(0.01, 0.01, 0.98)] * 2 + [(0.98, 0.01, 0.01)] * 3
    emissions = [SimpleNamespace(home=h, away=a, dead=d) for h, a, d in values]
    labels, score = decode(emissions, config=cfg)
    if labels != ["H"] * 3 + ["D"] * 2 + ["H"] * 3 or not math.isfinite(score):
        raise ValueError("synthetic semantic check failed")
    return labels


def synthetic_resource_check():
    """Decode the full graded-frame count as two generated, independent halves."""
    started = time.perf_counter()
    total = 0
    signatures = []
    neutral = HMMConfig()
    for length in (79467, 79390):
        stream = (SimpleNamespace(home=1 / 3, away=1 / 3, dead=1 / 3) for _ in range(length))
        labels, score = decode(stream, config=neutral)
        if len(labels) != length or not all(label == "H" for label in labels) or not math.isfinite(score):
            raise ValueError("synthetic full-half resource check failed")
        signatures.append((labels[0], labels[-1], len(labels)))
        total += len(labels)
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_mb = peak / (1024.0 * 1024.0) if sys.platform == "darwin" else peak / 1024.0
    return {"graded_equivalent_frames": total, "independent_halves": len(signatures),
            "deterministic_state_counts": {"H": total, "A": 0, "D": 0},
            "runtime_seconds": time.perf_counter() - started, "peak_memory_mb": peak_mb}



def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--data-dir')
    parser.add_argument('--output')
    parser.add_argument('--diagnostics')
    parser.add_argument('--metadata')
    parser.add_argument('--self-check', action='store_true', help='run synthetic semantic checks without competition data')
    parser.add_argument('--synthetic-resource-check', action='store_true', help='decode a full graded-length synthetic sequence')
    args = parser.parse_args(argv)
    try:
        if args.self_check:
            synthetic_self_check()
            print('synthetic E04 self-check passed')
            return 0
        if args.synthetic_resource_check:
            print(json.dumps(synthetic_resource_check(), sort_keys=True))
            return 0
        started = time.perf_counter()
        config = load_e04_config(args.config)
        output_path = args.output or config["output"]
        diagnostics_path = args.diagnostics or config["diagnostics"]
        metadata_path = args.metadata or config["metadata"]
        data_dir = args.data_dir or config['data_dir']
        paths = asset_paths(game=GAME, data_dir=data_dir, source='tactical')
        require(['atd_meta', 'atd_raw', 'smart_tagging'], game=GAME, data_dir=data_dir, source='tactical')
        count = source_frames('tactical', GAME)
        metadata = parse_atd_metadata(Path(paths['atd_meta']))
        events = parse_smart_tagging(Path(paths['smart_tagging']), expected_frames=count)
        halves, _ = half_index_by_video_frame(count)
        raw = iter_atd_frames(Path(paths['atd_raw']), metadata, expected_frames=count, source='tactical', game=GAME)
        evidence = iter_frame_evidence(raw, metadata, halves, restart_frame_mask(events, count))
        tags = iter_tag_evidence(events, count) if config['tag_features']['enabled'] else None
        stream = iter_infer_e02(evidence, config['possession'], config['features'], tag_evidence=tags)
        labels = ['X'] * count
        parent_labels = ['X'] * count
        emission_argmax = ['X'] * count
        missing_ball = [False] * count
        current_half = None
        current_start = None
        current_emissions = []
        seen_halves = set()

        def flush_half():
            nonlocal current_half, current_start, current_emissions
            if current_half is None:
                return
            if not current_emissions:
                raise ValueError('graded half has no emissions')
            decoded, _ = decode(current_emissions, config=config["hmm"])
            if len(decoded) != len(current_emissions):
                raise ValueError('decoded half length does not match emissions')
            for offset, label in enumerate(decoded):
                labels[current_start + offset] = label
            current_half = None
            current_start = None
            current_emissions = []

        processed = 0
        for index, result in enumerate(stream):
            emission = result.emission
            if index >= count or emission.frame != index or emission.half != halves[index]:
                raise ValueError('misaligned emission stream')
            processed = index + 1
            parent_labels[index] = result.inference.label
            emission_values = (emission.home, emission.away, emission.dead)
            emission_argmax[index] = ('H', 'A', 'D')[max(range(3), key=emission_values.__getitem__)]
            missing_ball[index] = result.features.quality.ball_missing
            if emission.half == 0:
                flush_half()
                continue
            if current_half != emission.half:
                flush_half()
                if emission.half in seen_halves:
                    raise ValueError('graded half appears in multiple disjoint blocks')
                seen_halves.add(emission.half)
                current_half = emission.half
                current_start = index
            if index != current_start + len(current_emissions):
                raise ValueError('half must be a contiguous block')
            current_emissions.append(emission)
        flush_half()
        if processed != count:
            raise ValueError('incomplete emission stream')
        if seen_halves != {1, 2}:
            raise ValueError('both official graded halves must be present')
        root = (Path(__file__).resolve().parents[1] / '.local-checkpoints/phase8').resolve()
        targets = [Path(value).resolve() for value in (output_path, diagnostics_path, metadata_path)]
        if len(set(targets)) != 3 or any(root not in target.parents for target in targets):
            raise ValueError('outputs must be distinct paths under .local-checkpoints/phase8')
        for target in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
        csv_path = targets[0].with_name(targets[0].name + '.tmp')
        with csv_path.open('w', encoding='utf-8', newline='') as handle:
            writer = csv.writer(handle, lineterminator='\n')
            writer.writerow(('frame', 'label'))
            writer.writerows(enumerate(labels))
        csv_path.replace(targets[0])
        report = build_diagnostics(
            labels, halves, parent_labels, emission_argmax, missing_ball,
            runtime_seconds=time.perf_counter() - started,
        )
        atomic_write_text(targets[1], json.dumps(report, indent=2, sort_keys=True) + '\n')
        runtime = time.perf_counter() - started
        project_root = Path(__file__).resolve().parents[1]
        source_files = [project_root / "games.py"]
        for package in (project_root / "starter_v5", project_root / "starter_v6"):
            source_files.extend(package.rglob("*.py"))
        source_files = [path for path in source_files if "__pycache__" not in path.parts]
        input_identifiers = {
            key: {"filename": Path(paths[key]).name, "sha256": file_sha256(paths[key])}
            for key in ("atd_meta", "atd_raw", "smart_tagging")
        }
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(project_root), text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=str(project_root), text=True).strip())
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak_mb = peak / (1024.0 * 1024.0) if sys.platform == "darwin" else peak / 1024.0
        resolved_config = effective_config(config)
        resolved_config.update({
            "output": str(targets[0].relative_to(project_root)),
            "diagnostics": str(targets[1].relative_to(project_root)),
            "metadata": str(targets[2].relative_to(project_root)),
        })
        provenance = {
            "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "output_sha256": file_sha256(targets[0]),
            "code_sha256": source_sha256(source_files),
            "config_sha256": config_sha256(config),
            "config_file_sha256": file_sha256(args.config) if args.config else None,
            "effective_config": resolved_config,
            "run_paths": {
                "output": str(targets[0].relative_to(project_root)),
                "diagnostics": str(targets[1].relative_to(project_root)),
                "metadata": str(targets[2].relative_to(project_root)),
            },
            "input_identifiers": input_identifiers,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "git_revision": revision,
            "git_worktree_dirty": dirty,
            "parent": "starter_v5",
            "frame_count": count,
            "runtime_seconds": runtime,
            "peak_memory_mb": peak_mb,
            "ground_truth_used": False,
            "local_only": True,
        }
        atomic_write_text(targets[2], json.dumps(provenance, indent=2, sort_keys=True, allow_nan=False) + '\n')
        print('E04 candidate written; {} frames'.format(count))
        return 0
    except (OSError, ValueError, KeyError) as error:
        print('ERROR: {}'.format(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
