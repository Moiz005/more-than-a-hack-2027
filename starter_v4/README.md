# Solution 01 E02 — Team geometry, motion, and observation quality

`starter_v4/` is a separate fork of E01 in `starter_v3/`. It keeps the E01 path selectable and adds E02 team-level geometry, masked motion features, observation-quality weighting, and a conservative missing-ball turnover gate. The organizer `starter/`, evaluation scripts, and E01 parent remain unchanged.

## Evidence and state behavior

- Spatial features include per-team nearest and top-k distances, distance margin, local density, contested-ball context, and pitch-boundary distance. Distances use metric coordinates only for valid observations.
- Near-duplicate positions within a team are collapsed for top-k and density calculations. Track-slot numbers are carried only as row-level observation IDs; they are not player identities.
- Motion features include observed-ball displacement, robust team-centroid movement, track-reported team speed medians, and ball/team co-motion when both vectors are available. Missing inputs keep their masks and yield `None` rather than fabricated zeroes.
- Observation-quality flags cover missing ball, low player coverage, one-team visibility, duplicate positions, implausible ball jumps, speed/displacement mismatch, visible-slot population changes, and out-of-bounds locations. Raw positions are not overwritten; confidence weights are clipped to `[0, 1]`.
- During a short missing-ball gap, the last observed ball position is used only as a historical spatial anchor for player-motion evidence. It is never treated as the current ball location. E02 backfills a turnover into that gap only after repeated opposing-team movement/density support, adequate observation quality, and consecutive opposing control evidence after recovery. Weak proximity alone does not switch the state. Long or poor-quality gaps expire to `X`.
- Dead-ball evidence remains separate. A missing ball alone does not create `D`; `H → D → H` remains two possession spells. Temporal state resets at each half boundary.

These are deterministic heuristic features, not a learned model. Their synthetic tests establish behavior only; no accuracy gain or superiority over E01 or the organizer baseline has been established. Public labels are not used for threshold selection or candidate ranking.

## Commands

Run from `more-than-a-hack-2027/` with the existing `.venv`:

```bash
.venv/bin/python -m unittest discover -s starter_v4/tests -p 'test_*.py'
.venv/bin/python -m starter_v4.run_e01 --help
.venv/bin/python -m starter_v4.run_e01 --self-check
.venv/bin/python -m starter_v4.run_e01 --evidence-mode e01 --config starter_v4/config.example.json --output .local-checkpoints/phase6/e01_compat.csv --diagnostics .local-checkpoints/phase6/e01_compat_diagnostics.json --metadata .local-checkpoints/phase6/e01_compat_metadata.json
.venv/bin/python -m starter_v4.run_e01 --evidence-mode e02 --config starter_v4/config.example.json --output .local-checkpoints/phase6/e02_candidate.csv --diagnostics .local-checkpoints/phase6/e02_diagnostics.json --metadata .local-checkpoints/phase6/e02_metadata.json
.venv/bin/python evaluation/validate_submission.py .local-checkpoints/phase6/e02_candidate.csv
```

`--evidence-mode e01` uses the original E01 state logic and is intended to reproduce the recorded E01 CSV byte-for-byte. `--evidence-mode e02` enables the features and gap policy. Every threshold lives in `config.example.json`; unknown config keys fail.

Input data must already be available locally under `data/`, `MTAH_DATA_DIR`, or `--data-dir`. The CLI never downloads or substitutes match assets. It writes only below ignored `.local-checkpoints/phase6/`, outside the licensed data directory. Diagnostics include aggregates, configuration/source hashes, output hash, runtime, and peak memory where the platform exposes it; they do not contain frame rows or coordinates.
