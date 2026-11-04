# HBK-01 half-boundary runner

This is an isolated, opt-in experiment layer on top of the verified
`starter_v6.run_e04` runner. It does not copy the E04 data loaders, possession
inference, HMM, or restart detector.

All inputs are tactical. The command never downloads data. Licensed match
assets and frame-specific diagnostics must remain local under the ignored
`.local-checkpoints/` tree.

## Modes

- `off`: run the canonical E04 parent and copy its CSV bytes unchanged.
- `audit`: run E04 and report both opening-kickoff tag windows, ATD detector
  statuses, timestamps, aggregate ATD evidence, and the hypothetical
  second-half prefix. No submission CSV is written. Diagnostics include only
  aggregate, non-reconstructive evidence counts; they do not export frame rows.
- `overlay`: run E04 and write a modified CSV when the second-half ATD detector
  returns `CONFIRMED`, `ESTIMATED_FRAME`, or a frame-resolvable
  `BOUNDED_INTERVAL`; the policy changes only
  `[second_half_graded_start, detector_frame)` to `D`.

The detector treats a short missing-ball interval as a bounded execution
interval only when subsequent motion is corroborated. The policy is
algorithmic rather than a one-to-one legal-event map: an estimated frame or
bounded interval can contribute a reproducible prefix boundary when it resolves
to a frame. Ambiguous, missing, and frame-less evidence remains rejected.
Player proximity, center-circle occupancy, and player motion are supporting
evidence and cannot create a frame by themselves.

When persistent plausible ball motion occurs inside the five-second Smart Tag
interval but strict centre setup is unavailable, audit mode reports
`ESTIMATED_FRAME` with `best_estimate_frame` and a video-relative timestamp.
That estimate is now an opt-in algorithmic input to the overlay policy; it is
not claimed to be a perfect legal kickoff annotation.

Audit mode covers both supported kickoff Smart Tag types: opening `Kick Off
(Start)` and post-goal `Kick Off (After Goal)`. Every eligible event receives
its own event-indexed detection record. Only the two opening results feed the
existing half-boundary policy; post-goal detections remain informational until
a separate restart-possession policy is justified.

The first-half result is diagnostic only. A rejected, ambiguous, or frame-less
second-half result leaves the parent labels unchanged and causes `overlay` to
exit with an error without writing the requested submission.

## Invocation

Run from the repository root with a unique run ID:

```bash
python -m starter_v6.run_half_boundaries --config starter_v6/config.hbk01.example.json \
  --mode off --run-id off-001
python -m starter_v6.run_half_boundaries --config starter_v6/config.hbk01.example.json \
  --mode audit --run-id audit-001
python -m starter_v6.run_half_boundaries --config starter_v6/config.hbk01.example.json \
  --mode overlay --run-id overlay-001
```

Artifacts are written to `.local-checkpoints/hbk01/<run-id>/` and are refused
if they already exist unless `--overwrite` is explicitly supplied. The config's
`output`, `diagnostics`, and `metadata` values are filenames or subpaths below
that run directory. `parent_config` is resolved from the repository root and
must be a tactical E04 configuration.

Use `--data-dir <path>` to point at locally available licensed assets. If the
assets are absent, the runner reports the missing local inputs and does not
download replacements. `--self-check` exercises the policy plumbing with
invented data and requires no match assets.

The metadata captures the parent commit/config hash, HBK-01 config/source
hashes, tactical input identifiers, runtime, Python version, selected mode,
and output hash. These records are local provenance, not accuracy evidence.

## Phase 8 historical release status

As of 2026-11-05, HBK-01 is **GO only as an isolated engineering experiment**
and **NO-GO for overlay promotion**. The canonical source is on
`experiment/e04-v3-visual-possession` at commit
`03c9245cc45edfc25561d5a7cf9f14b19e622584`. The real tactical `off` output was
byte-identical to E04 and passed the official structural validator. The audit
found one eligible opening kickoff candidate per half, but both ATD detectors
returned `INSUFFICIENT_EVIDENCE`; overlay therefore exited safely without a
submission. No private metric improvement is verified.

The complete evidence, ablation table, limitations, exact local run IDs, and
fallback command are in
[`HBK-01_IMPLEMENTATION_REPORT.md`](HBK-01_IMPLEMENTATION_REPORT.md). Keep
generated outputs and diagnostics under ignored `.local-checkpoints/` paths;
do not commit licensed assets or frame-specific reports.
