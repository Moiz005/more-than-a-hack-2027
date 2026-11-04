# TacticalFusion P4 — Homography value decision

## Decision

**G4 PASS — OMIT RUNTIME HOMOGRAPHY FEATURE.** Keep homography available for
camera/pixel projection diagnostics only. Do not add it to Stage 1, Stage 2,
`FrameEvidence`, `FrameFeatures`, emissions, or submission generation.

The reason is evidential, not a claim that the transform is unusable: the
inference path has pitch-normalized ATD points but no independent image-space
ball/player observation to compare against their projections. Projecting an ATD
point and unprojecting it returns the same point, including a corrupted point.
The transform therefore cannot add independent possession, boundary-crossing,
last-touch, or restart evidence by itself.

## P4.1 — pinned source and data contract

Reconfirmed the protected checkout at `9fd0277a23258a448e0863b33d646c8540070c50`
and its clean worktree. In that source:

- `ingestion.load_homography_arrays()` reads one row per frame, validates
  sequential zero-based frame indices, row-major `h00..h22`, finite matrix
  values when `valid=1`, and rejects finite negative reprojection errors. The
  parser itself permits non-finite error values; the supplied tactical file
  was separately verified to have finite errors throughout.
- `HOMOGRAPHY_MAPPING_DIRECTION` is
  `normalized_pitch_xy_to_video_pixel_xy`. `starter_v6/load_homography.py`
  exposes `project()` and inverse-based `unproject()` helpers.
- `ingestion.build_data_quality_report()` is the only runtime-tree consumer,
  for aggregate data inventory. `run_e04.py`, `iter_infer_e02()`, and
  `FrameEvidence` do not consume homography values.
- `contracts.ObservationQuality` has optional homography-validity/error fields,
  but no E04 adapter populates them and no inference code consumes them.
- ATD normalized coordinates are scaled directly by pitch dimensions
  (105.3 × 68.0 m) for proximity, motion, and pitch-boundary geometry. That
  path does not require a camera transform.

The authorized tactical homography parsed as **199,319 rows**, frame **0** to
**199,318**, all marked valid. The parser found no non-finite valid matrices;
NumPy found no matrices whose computed determinant was exactly zero. No
condition-number or near-singularity threshold was evaluated, so this is not a
full matrix-conditioning audit. Reprojection error was finite throughout:
median **0.239246**, p99 **4.807635**, maximum **5.475548**. Mapping direction
was normalized pitch XY → video pixels. These are aggregate calibration
diagnostics; no matrix rows, projected coordinates, or video-derived extracts
are included here.

Reproduce those aggregates locally (prints only counts/summary statistics):

```sh
PYTHONPATH=. /Users/moiz/Desktop/Metrica-Sports-Hackathon/more-than-a-hack-2027/.venv/bin/python -c '
from pathlib import Path
import numpy as np
from games import GAME, asset_paths
from starter_v6.ingestion import load_homography_arrays
p = asset_paths(game=GAME, data_dir="/Users/moiz/Desktop/Metrica-Sports-Hackathon/more-than-a-hack-2027/data", source="tactical")["homography"]
h = load_homography_arrays(Path(p), expected_frames=199319)
m = np.frombuffer(h.matrices, dtype="d").reshape((-1, 3, 3))
e = np.frombuffer(h.reprojection_error, dtype="d")
v = np.frombuffer(h.valid, dtype="B").astype(bool)
d = np.linalg.det(m[v]); e = e[v]
print(len(h.frame_indices), h.frame_indices[0], h.frame_indices[-1], int(v.sum()), int((~v).sum()), h.mapping_direction)
print(int((~np.isfinite(m[v])).any(axis=(1, 2)).sum()), int((d == 0).sum()), int((~np.isfinite(e)).sum()))
print(float(np.median(e)), float(np.percentile(e, 99)), float(np.max(e)))
'
```

## P4.2–P4.3 — independent-information and possible-use audit

| Possible use | Evidence available in the current inference path | Decision |
|---|---|---|
| Camera/pixel geometry sanity | The transform and its reprojection error are available; no independent pixel observation is emitted by E04 | Keep as offline/debug projection only |
| Geometric valid-area mask | ATD points are already in pitch coordinates; there is no framewise image-space visibility mask consumed by E04 | Omit from inference |
| Reproducible projection diagnostics | `project()`, `unproject()`, and pitch-corner utilities exist | Retain as diagnostic tools; they do not change labels |
| Independent image consistency | No permitted machine-produced pixel observation is paired with ATD in the current model; projecting ATD itself would be circular | No adapter justified |

The tactical video is the reference source, but merely having its pixels does
not create a second observation for the current inference code. No manual
frame-specific correction or new detector was introduced for this audit.

## P4.5–P4.7 — safeguards and spatial semantics

No runtime adapter was justified, so no projection API or runtime data schema
was changed. If an independent pixel observation is introduced in a separately
authorized task, its adapter must first fail closed on invalid/missing matrices,
non-finite or near-zero projective denominators, singular/ill-conditioned
matrices, out-of-image results, and invalid reprojection-error values. The
existing convenience projection functions are not promoted as a validated
inference boundary.

Goal-line and touchline hypotheses remain based on direct ATD pitch
coordinates, as tested in `tests/test_atd_signals.py` and the P4 synthetic
fixtures. Center, touchline, and corner restart placements are included as
spatial counterfactuals; only the existing generic restart-context flag is
available, so no restart-type legality is asserted. A planar homography cannot
establish whole-ball crossing, legal restart timing, last-touch team, or
physical ball height.

## P4.6–P4.8 — synthetic ablation

Added `tests/test_homography_value.py` using synthetic matrices, calibration
landmarks, quality metadata and generated ATD fixtures. A corrupted synthetic
matrix translation increases reprojection residual from 0 to 12 pixels while
the ATD quality fields remain unchanged, demonstrating a distinct, traceable
*calibration-fit* signal. That matrix-quality metadata is not populated or
consumed in E04 and does not measure ATD tracking-coordinate error.
The inference ablation is deliberately limited to the only candidate operation
without an independent observation: ATD→pixel→pitch round trip. It checks matrix
direction/inversion and shows a deliberately corrupted ATD point remains
corrupted after the round trip.

| Synthetic case | Independent H observation? | Inference / proposal decision changes after round trip? |
|---|---:|---:|
| Controlled possession | No | 0 |
| Missing ball | No | 0 |
| Touchline and goal-line hypotheses | No | 0 |
| Center restart placement | No | 0 |
| Touchline restart placement | No | 0 |
| Corner restart placement | No | 0 |

This is a round-trip invariance counterfactual, not an ablation of an
independent image-derived feature and not a match-accuracy experiment. Matrix
validity and reprojection error describe the transform's own availability/fit;
there is no evidence in this pipeline that they measure ATD position error or
improve possession decisions. No broader `ATD+H` inference feature was built
because no source-supported independent candidate exists.

## Gate outcome and reproduction

- P4.1–P4.4: pinned source, format/direction, independent-information test,
  possible uses, and direct ATD metric geometry documented.
- P4.5: adapter-specific safeguards recorded as a future prerequisite; no
  adapter added because P4.9 selects omission.
- P4.6: synthetic independent calibration landmarks show a corrupted matrix
  raises reprojection error while ATD quality is unchanged. This measures
  homography fit only; no such metadata reaches inference or validates ATD
  coordinates.
- P4.7–P4.8: direct-pitch goal-line/touchline and center/touchline/corner
  restart-context counterfactuals preserve decisions after the proposed
  transform round trip; this does not claim type-specific restart legality.
- P4.9: **OMIT RUNTIME HOMOGRAPHY FEATURE**.
- P4.10: evaluated; not applicable after the P4.9 rejection.
- P4.11: focused and full regression suites run; plan and project memory updated.

Focused command:

```sh
/Users/moiz/Desktop/Metrica-Sports-Hackathon/more-than-a-hack-2027/.venv/bin/python -m unittest starter_v6.tests.test_homography_value -v
/Users/moiz/Desktop/Metrica-Sports-Hackathon/more-than-a-hack-2027/.venv/bin/python -m unittest discover -s starter_v6/tests -p 'test_*.py'
```

Results: focused Phase 4 tests **4 passed**; full v6 suite **228 passed, 1
skipped**. `git diff --check` passed. No inference/runtime source changed, so
the previous full tactical output remains unchanged.

The full-suite command is the second command above:
`python -m unittest discover -s starter_v6/tests -p 'test_*.py'`.
The 228-pass / 1-skip result is from that run in the approved project venv.

No accuracy or metric improvement is claimed. Reopen runtime integration only
if a permitted, independent image-space observation becomes available and a
new synthetic ablation demonstrates a distinct, trustworthy inference use.
