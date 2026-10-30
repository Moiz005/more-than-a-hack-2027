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

## V3.3 — Boundary coordinate reliability

- Start/rollback: bd757b493180a96b39d2c57e5901829d4d507b87.
- Signal: existing features.quality.implausible_ball_jump only. A supplied-speed
  mismatch alone does not suppress structural boundary evidence. No thresholds
  or configuration settings changed.
- Interface: optional default-true boundary_coordinate_reliable argument on
  observe_dead_ball and StatefulDeadBallDetector.observe; production E02 passes
  the feature-derived flag. Legacy raw helper callers retain their defaults.
- Reliable boundary branch is unchanged. Rejected boundary coordinates fall
  through to the existing non-boundary cues. If no independent D cue exists,
  emit non-confirmable uncertainty (D=1/3, live=2/3), not hard D. Coordinate
  rejection also prevents seeding boundary-disappearance history. Reliable
  subsequent observations can establish D immediately under existing rules.
- Existing non-boundary code was extracted into _observe_nonboundary_dead_ball
  without changing its thresholds or logic. Collective/restart cues remain
  available when the boundary observation is unreliable.
- Causal protected-Phase-1 oracle: isolated jump HDH -> HHH; boundary D=1 -> 1/3;
  confirmation true -> false. Reliable crossing remains HDH and one-hot D.
  Later consistent boundary evidence confirms and can seed persistence.
- Actual full suite: 166 passed; 0 failed/expected failures/skipped. E04
  self-check passed. Includes HMM, import isolation, persistence and Phase 1.
- Fixture correction: three legacy boundary-positive assertions used impossible
  >10 m coordinate jumps. Their invented approach trajectories were corrected
  to remain within the existing jump threshold, retaining their D expectations.
- Exact changed functions/files: inference.iter_infer_e02; possession.
  observe_dead_ball, _observe_nonboundary_dead_ball, StatefulDeadBallDetector.
  observe; tests/test_boundary_quality.py, test_production_dead_ball_integration.py,
  test_v3_context_consumption.py; this experiment log.
- Full local runs: distinct ignored .local-checkpoints/v3/phase3/boundary_quality/
  run1 and run2. Each metadata.json records config/source/dependency hashes.
- Risks: true abrupt crossings may be delayed; consecutive observations can be
  mutually consistent yet wrong; no jump test is available across missing/half
  boundaries. Independent low-motion evidence can still establish D under its
  unchanged rules. No claim of real spellF1 improvement or public-GT use.
