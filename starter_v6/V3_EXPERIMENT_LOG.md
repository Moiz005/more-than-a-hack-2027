# v3 experiment tracking

Copy this template for future experiments; do not populate results before execution.

- Experiment ID / objective:
- Starting Git commit / ending Git commit:
- Configuration path / SHA256 / effective configuration:
- Executed source manifest / SHA256 / dependency manifest:
- Files changed:
- Test commands / actual passed / failed / skipped / expected failures:
- Expected versus actual synthetic behavior:
- Enabled/disabled causal comparison:
- HMM arithmetic / import isolation:
- Local aggregate diagnostics (no reconstructive outputs):
- Official validator command / result / row count:
- Output path / SHA256 / repeat SHA256:
- Lawful held-out other-game metrics (or not run):
- Known regressions / limitations:
- Rollback command:
- Gate decision: GO / NO-GO / BLOCKED / SKIPPED

## Phase 0 preservation record

Baseline: `d24d5ae7b02488807ab7167494496c93152bbafa`, annotated tag
`e04-v3-phase0-persistence-baseline` (entire repository tree).
The baseline has 148 passing tests. The two added characterization tests preserve
`DDDHHDDDD` and explicitly mark desired `DDDHHHHHH` as an expected failure.
No production code or configuration is changed in Phase 0.

Local evidence directory: `.local-checkpoints/v3/phase0/d24d5ae_verified/`.
It contains a complete-history Git bundle, copied configuration, historical run
metadata, new independent run metadata/CSVs, private input fingerprints, logs,
and a baseline runbook. Keep these artifacts local and ignored.

Restore the exact baseline entire tree (after saving any current work):
`git switch --detach e04-v3-phase0-persistence-baseline`.
If the repository is lost, `git clone <local-baseline.bundle> <new-directory>`
then detach at that tag. Licensed inputs and the Python environment are separate.

Known cause: runtime adapter consumption is internal to
`RuntimeRestartActionDetector`; only a one-frame action reaches the observer.
Later stationary frames under the same context generate `restart_stationary`,
confirm on the next frame, and produce D again. Persistence does not cause this:
the defect reproduces without missing observations. Phase 1 should distinguish
consumed old context from genuinely new independent stoppage evidence.

## V3.1 — Consume old restart preparation context

- Objective: suppress only stale restart_stationary after delivery.
- Starting commit: 7ceba8b3f248ac9d39a06b5145a1d4b3fea46601.
- Rollback: git switch --detach e04-v3-phase0-persistence-baseline.
- Design: append default-false restart_context_consumed to FrameEvidence.
  RuntimeRestartActionDetector exposes its existing action-emitted state on all
  following frames, including missing observations. The observer gates only
  restart_stationary; boundary and collective motion remain active.
- Mask identity: overlapping/contiguous events form one uninterrupted context.
  No per-event identity is invented. A tag gap or half change rearms context.
  A new event inside an uninterrupted run cannot rearm from the tag alone;
  independent physical evidence remains available. Missed delivery does not
  consume context. Raw FrameEvidence callers default to historical behavior.
- Tests: exact fixture now DDDHHHHHH versus protected DDDHHDDDD. An archived-tag
  causal oracle checks cues, confirmation, emissions, labels, unchanged H/A
  evidence and independent boundary control. Lifecycle tests cover overlapping,
  merged/contiguous masks, repeated events after gaps, missing/reliability cases,
  collective cues and halftime. The expected-failure marker is removed.
- Unchanged: H/A/gap ownership, boundary/restart thresholds, persistence policy,
  tag-mask interpretation, fusion, HMM and micro-D defaults. No dependencies.
- Verification commands: .venv/bin/python -B -m unittest discover -s
  starter_v6/tests -p 'test*.py'; .venv/bin/python -B -m
  starter_v6.run_e04 --self-check. Full results and local run metadata are
  recorded under .local-checkpoints/v3/phase1/context_consumption/.
- Limitation: no held-out other-game accuracy measurement or public-truth use.
- Implementation/end-of-algorithm commit: 3804387f6ef501869507de441cfe909ac17ca627.
- Actual full discovery: 158 passed, 0 failed, 0 expected failures, 0 skipped.
  This includes HMM exhaustive/path arithmetic, import isolation, 14 persistence
  tests and the new archived-baseline causal comparison. E04 self-check passed.
- Two clean post-commit local runs passed the official validator: 199319 rows,
  frame 0..199318. Both CSV hashes:
  e501d82f0fb15650761e7d594cea35999166e89e54122e3392c4a052615b4763.
- Phase 0 hash: 7596d3908f16dec3fee299ffa6538d9184a1d9ddcbd24fbb3f0e3265820583b0.
  Output changed at 573 labels. D frames 9268 -> 8830; D runs 83 -> 72.
  These unlabeled aggregates do not establish accuracy improvement.
- Source/config hashes, dependency manifest and exact run paths are in each
  run's metadata.json; configuration bytes and all HMM parameters are unchanged.
- G1.1-G1.5: GO. Phase 2 is not implemented. New independent events inside
  uninterrupted masks still require independent physical evidence.
