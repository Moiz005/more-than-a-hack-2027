# E04 baseline and Phase 0–2 gates

Last reviewed: 2026-11-04.

## Summary

`starter_v6/` is E04, forked from E03 `starter_v5/`. The authoritative
reproducible baseline is E04_C7, frozen as the full-tree tag `e04-c7-frozen`
at commit `7aa2f1b44b9db015a89d61fef797ebe83b4dadd2`. The frozen candidate and
all post-G0/G1 parity candidates contain 199,319 rows and have SHA256
`865c45993fff24c670912d6861fd37d4df3f2f90a0418690fb7cd7c7a75b9ceb`.

This is a reproducibility, format, isolation, and testability baseline. It is
not evidence of possession accuracy or superiority.

## G0 — frozen E04_C7 baseline

- G0 is complete. The tag covers the entire executed historical dependency
  tree (`starter_v6 → starter_v5 → starter_v4`), not only the v6 directory.
- Preserved and regenerated full candidates match byte-for-byte and both pass
  the official structural submission validator.
- The public/synthetic baseline suite ran 83 tests and passed. The
  data-dependent local Smart Tagging inventory test was not counted in that
  result because its authorized local input was unavailable in the G0 run.
- E04 self-check and synthetic-resource checks passed. Protected `starter/`,
  `starter_v4/`, `starter_v5/`, and `evaluation/` were unchanged at the G0
  audit.

Primary evidence: `more-than-a-hack-2027/.local-checkpoints/phase0/e04_c7_frozen_20261030/G0_REPORT.md`,
`CHECKOUT.md`, `RUNBOOK.md`, `SHA256SUMS`, and `provenance/`.

## G1 — self-contained v6 parity

G1 is complete and behavior-preserving. The E04 runner and tests resolve local
`starter_v6` modules only; runtime isolation found no legacy `starter_v4` or
`starter_v5` modules. The transitive project-source manifest contains 16
executed Python files, and dependency versions are recorded separately.

Frozen synthetic emissions and labels match exactly. The current-commit
full-input output is byte-identical to E04_C7 and passes structural validation.
The original 83 tests plus four Phase 1 tests passed (87 selected tests); full
discovery including the authorized local inventory test passed 88 tests.

Commits: `d1410c459f1569c5d4ff8ca27d37a359362f11c6` (runtime isolation) and
`71c593d53768cf18cb6cb6664b137030dc1e07bc` (v6-local parity harness).

Primary evidence: `more-than-a-hack-2027/.local-checkpoints/phase1/G1_REPORT.md`,
`PHASE1_REPORT.md`, `verification_g1/`, `verification_committed/`,
`G1_IMPORT_GRAPH.txt`, and the source manifest.

## G2 — synthetic integration and trace harness

G2 is complete as a testability gate; it did not change prediction behavior.
Commit `ee42a001a04bf97c91968829cd14d9830a0d8560` adds an asset-free,
deterministic harness that traces invented evidence through raw cues, cue
quality, play-state confirmation, live-team evidence, H/A/D emissions, HMM /
Viterbi labels, and spell boundaries.

The final trace artifact is
`more-than-a-hack-2027/.local-checkpoints/phase2/synthetic_trace_all_v2.json`:
10 fixtures and 44 traced frames. It covers every proposed rule ID R01–R15,
explicit 25 FPS timing hypotheses, counterfactuals, restart families,
boundary/jitter, missing-ball live play and gap recovery, goalkeeper-live
play, conflicting tags, short stops, halftime, and second-half pre-kickoff.

The harness intentionally records characterization signals rather than hiding
known behavior. The final trace identifies four pre-Phase-2 signals:

- `baseline_raw_restart_suppressed_by_team_gate`
- `baseline_dead_confirmation_uses_mixed_cue_counter`
- `gap_evidence_not_encoded_in_hmm_emission`
- `baseline_confirmed_dead_emission_is_one_hot`

These are diagnosis targets, not fixes or match-label findings. The full Phase
2 suite passed 97 tests. No licensed match asset or public ground truth is
required by the harness.

Primary evidence: `more-than-a-hack-2027/.local-checkpoints/phase2/PHASE2_REPORT.md`,
`synthetic_trace_all_v2.json`, and `starter_v6/synthetic.py`,
`trace_synthetic.py`, and `tests/test_synthetic_integration.py`.

## Constraints and unresolved gaps

- Do not tune, select, or rank approaches using the public five-minute truth;
  no independent full-match labels establish accuracy.
- Do not manually correct match frames, use external private labels, or place
  licensed assets, frame-level extracts, candidate predictions, or credentials
  in `.knowledge/` or commits.
- E04 emissions are evidence potentials, not calibrated probabilities. The
  configured transition prior suppresses one- and two-frame opposing blips;
  the synthetic three-frame controlled turnover is retained. The right
  duration for genuine short control remains unresolved.
- G2 failure signals are characterized but not repaired. Boundary matching,
  dead-ball recall, and any full-match accuracy claim remain open.

The latest read-only synthetic investigation is recorded in
[E04 read-only investigation handoff — 2026-10-31](e04-investigation-20261031.md).
It adds source/configuration diagnosis only; it does not supersede the frozen
release, change the selected candidate, or establish target-match behavior.

## Current release posture

The 2026-11-02 [T1 / Q1 / homography audit](t1-q1-homography-audit-20261102.md)
is the current decision layer for post-Phase-2 work. It supersedes the
historical next-step wording below: T1 remains unreleased, B0 remains the
protected fallback, and Phase 5 is skipped. The only authorized follow-up is a
separate design/test task for a co-motion-aware T1 predicate; it must remain in
shadow evaluation until its existing protections and reproducibility gates
pass. No public-score tuning or production change is authorized by the audit.

## Pinned V3 release input contract — 2026-11-04

The active release checkout is detached and clean at verified pre-WhistleBridge
E04 V3 commit `9fd0277a23258a448e0863b33d646c8540070c50`. On this release,
E04 uses tactical ATD and automatic Smart Tagging: ATD record IDs are
one-based and map to zero-based tactical frames; missing observations remain
missing. Smart Tagging seconds map with `round(seconds * 25)` to half-open
intervals and provide contextual/team priors and restart context, but cannot
alone force possession or DEAD. Parsed `Half` tags are unused. Homography is
validated by tooling but is not consumed by E04 inference. Audio whistle
detection is not integrated.

A fresh deterministic run on the pinned checkout passed official submission
validation (199,319 rows, frames `0..199318`) and public-only pipeline
evaluation over 7,500 graded frames: macroF1 `0.686522`, spellF1 `0.475000`.
Candidate SHA256 is
`d1604474717565a460d30bdef271d4e6e9b6c088c00bec84f6ef3d97a35f74ae`, matching
the release artifact. This confirms pipeline/alignment behavior only. Public
labels are not evidence for full-match accuracy and must not be used to tune,
rank, or select approaches.

Open design questions for future authorized work: whether homography supplies
useful independent evidence beyond ATD, and how to prevent correlated ATD,
Smart Tagging, and homography signals from being counted as independent votes.

Provenance: user-provided fresh-run record for commit
`9fd0277a23258a448e0863b33d646c8540070c50`; run output under
`more-than-a-hack-2027/.local-checkpoints/rollback_confirmation/run1/` and
scoreboard under its `public_evaluation/scoreboard.csv`; pinned release
artifact SHA256 above. Graphify query vocabulary: `E04 ATD Smart Tagging
homography audio whistle release`; graph nodes `starter_v6/inference.py`,
`starter/load_atd.py`, `starter/load_smart_tagging.py`, and `HomographyArrays`
in `starter_v2/ingestion.py`. Exact release/run details are handoff evidence;
the input semantics and correlation cautions are durable.

## Historical Phase 0–2 next step

Before changing behavior, create a separately authorized improvement
diagnosis/plan naming permitted evidence sources, behavioral hypotheses,
synthetic acceptance contracts, and reproducibility gates. Keep the frozen tag
and current self-contained `starter_v6/` baseline as references. If a new
algorithm is authorized, use a distinct versioned directory or explicitly
authorized post-freeze workflow and preserve the baseline; do not tune against
the public five-minute labels. The next planned technical phase is independent
raw play-state extraction, with no heuristic accepted until it has a failing
synthetic acceptance test. The 2026-10-31 handoff supplied candidate diagnosis
targets but intentionally made no strategy decision. This historical guidance
is retained for Phase 0–2 context; the current release posture is defined
above.

## Provenance

Repository evidence: root `memory.md`, `AGENTS.md`,
`.plan/gpt_plan/implementation-plan-v2/task_plan.md`, the G0/G1/G2 checkpoint
reports above, and commits `7aa2f1b`, `d1410c4`, `71c593d`, `ee42a00`.
Graphify query terms: `E04_C7 frozen baseline starter_v6 parity Phase 2
synthetic harness trace G0 G1 G2`, plus `T1 Q1 homography audit release
posture B0 Phase 5`. Cited graph nodes include
`starter_v6/synthetic.py` (`more-than-a-hack-2027/starter_v6/synthetic.py:L1`),
`trace_fixture()` (`.../synthetic.py:L329`), `decode()`
(`.../hmm.py:L25`), `iter_frame_evidence()`
(`.../pipeline.py:L74`), the Phase 2 integration test module
(`.../tests/test_synthetic_integration.py:L1`), `HomographyArrays`
(`starter_v2/ingestion.py:L109`), and `iter_infer_e02()`
(`starter_v6/inference.py:L222`). The current-posture update is grounded in
`starter_v6/T1_Q1_HOMOGRAPHY_COMPREHENSIVE_AUDIT.md` and
`T1_HOMOGRAPHY_NEXT_STEP_DECISION.md`, audited at commit
`64c2ad86354c9cc809dd4d211dcf17d62ddc0446`.
