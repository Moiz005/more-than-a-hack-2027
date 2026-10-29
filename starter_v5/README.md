# Solution 01 E03 — Weak, type-aware Smart Tagging evidence

`starter_v5/` is forked from E02 `starter_v4/` (parent commit `0b82303`). It preserves E01/E02 code paths and adds Smart Tagging frame evidence. The organizer `starter/`, `evaluation/`, E01 `starter_v3/`, and E02 `starter_v4/` are separate and unchanged.

## Evidence and state behavior

- Spatial features include per-team nearest and top-k distances, distance margin, local density, contested-ball context, and pitch-boundary distance. Distances use metric coordinates only for valid observations.
- Near-duplicate positions within a team are collapsed for top-k and density calculations. Track-slot numbers are carried only as row-level observation IDs; they are not player identities.
- Motion features include observed-ball displacement, robust team-centroid movement, track-reported team speed medians, and ball/team co-motion when both vectors are available. Missing inputs keep their masks and yield `None` rather than fabricated zeroes.
- Observation-quality flags cover missing ball, low player coverage, one-team visibility, duplicate positions, implausible ball jumps, speed/displacement mismatch, visible-slot population changes, and out-of-bounds locations. Raw positions are not overwritten; confidence weights are clipped to `[0, 1]`.
- During a short missing-ball gap, the last observed ball position is used only as a historical spatial anchor for player-motion evidence. It is never treated as the current ball location. E02 backfills a turnover into that gap only after repeated opposing-team movement/density support, adequate observation quality, and consecutive opposing control evidence after recovery. Weak proximity alone does not switch the state. Long or poor-quality gaps expire to `X`.
- Dead-ball evidence remains separate. A missing ball alone does not create `D`; `H → D → H` remains two possession spells. Temporal state resets at each half boundary.

Smart Tagging is converted to half-open tactical-frame intervals using the existing parser's 25 FPS conversion. Known Barcelona and Athletic/Atletic Club tags normalize to H/A; N/A and unsupported team values remain unknown. Correlated active tags are capped at one weak team prior per side, and simultaneous H/A priors are flagged and neutralized. Defensive phase codes remain context only. Set-piece types and goals provide context; neither an interval nor a tag alone forces D or a possession switch. A team prior only resolves a close, observed-ball geometry case when the nearest team agrees with the prior; it cannot create control without valid observed geometry. High-confidence contradictory geometry remains dominant.

Each E02/E03 inference result also carries a validated H/A/D evidence emission. Values are finite, bounded, and normalized; when the team evidence is unknown and there is no confirmed dead ball, the emission is neutral and marked uninformative. `X` remains a decoder/submission abstention label, not an emission state. Full-run diagnostics require one valid emission on every tactical frame and count informative, uninformative, and invalid vectors.

When E03 tags are enabled, the runner also performs a paired stream against E02 inference on the same ATD frames and the same possession/feature configuration, with `tag_evidence` omitted. Aggregate diagnostics count frames where team evidence confidence, team evidence, emission argmax, or final label differs. The comparison stores no frame-level records and uses no ground truth; it measures implementation effects only. Smart Tagging event/team totals are included as aggregate counts. The local inventory regression test skips when licensed data is absent and reports no event-level content.

The model is deterministic and rule based. Synthetic tests establish behavior contracts, not match accuracy. Paired differences and identical E02/E03 output hashes are diagnostic facts, not evidence that E03 is better or worse. Public labels were not used for tuning or ranking.

## Commands

Run from `more-than-a-hack-2027/` with the existing `.venv`:

```bash
.venv/bin/python -m unittest discover -s starter_v5/tests -p 'test_*.py'
.venv/bin/python -m starter_v5.run_e03 --help
.venv/bin/python -m starter_v5.run_e03 --self-check
.venv/bin/python -m starter_v5.run_e03 --evidence-mode e02 --config starter_v5/config.example.json --output .local-checkpoints/phase7/e02_compat.csv --diagnostics .local-checkpoints/phase7/e02_compat_diagnostics.json --metadata .local-checkpoints/phase7/e02_compat_metadata.json
.venv/bin/python -m starter_v5.run_e03 --evidence-mode e03 --config starter_v5/config.example.json --output .local-checkpoints/phase7/e03_candidate.csv --diagnostics .local-checkpoints/phase7/e03_diagnostics.json --metadata .local-checkpoints/phase7/e03_metadata.json
.venv/bin/python evaluation/validate_submission.py .local-checkpoints/phase7/e03_candidate.csv
.venv/bin/python evaluation/validate_submission.py .local-checkpoints/phase6/e02_candidate.csv
```

`--evidence-mode e01` uses the original E01 state logic and is intended to reproduce the recorded E01 CSV byte-for-byte. `--evidence-mode e02` enables the features and gap policy. Every threshold lives in `config.example.json`; unknown config keys fail.

Input data must already be available locally under `data/`, `MTAH_DATA_DIR`, or `--data-dir`. The CLI never downloads or substitutes match assets. It writes only below ignored `.local-checkpoints/phase7/`, outside the licensed data directory. Diagnostics contain aggregates, configuration/source hashes, output hash, runtime, and peak memory where available; they do not contain frame rows or coordinates.
