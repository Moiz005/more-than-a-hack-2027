# Current project handoff — TacticalFusion P7 complete

Reviewed: 2026-11-04.

## Objective and status

TacticalFusion P7/G7 is complete as a synthetic engineering integration with
an exact-V3 fallback. The protected E04 V3 baseline remains commit
`9fd0277a23258a448e0863b33d646c8540070c50`; the P7 integration checkpoint is
`9ff501d18a4028f203738bb16528e686d8915bb3`.

The local plan
`.plan/gpt_plan/TacticalFusion — Kickoff-First Audio, Tracking & Event
Fusion/task_plan.md` is version 2.0 and now records **P7 COMPLETE — G7 PASS**
with P8 next. It scopes work to tactical ATD and Smart Tagging, excludes audio
and broadcast inputs, and retains the P4 decision to omit runtime homography.
Do not edit the plan during knowledge curation.

The P7 result is separately verified in the isolated worktree/report. Do not
promote the single public evaluation into an accuracy claim or use it to rank
future candidates.

## Completed work and verification

- P7 integration passed 15 focused synthetic tests; the full v6 suite passed
  270 tests with 1 skipped; self-check, synthetic resource check, and the
  official validator passed.
- Exact-V3 output remained byte-identical to the protected baseline with SHA256
  `d1604474717565a460d30bdef271d4e6e9b6c088c00bec84f6ef3d97a35f74ae`.
- A single `atd_plus_tag` public pipeline check covered 7,500 graded frames
  and 17 public possessions: macroF1 `0.7008`, spellF1 `0.4114`, transition
  F1 at ±25 frames `0.2051`, and a 1,000-bootstrap spellF1 interval
  `0.2514–0.5714`.
These are pipeline/alignment checks only, not full-match accuracy. The public
run used one candidate only and was not used for tuning, comparison, ranking,
or selection.

## Release behavior to carry forward

- E04 uses tactical ATD plus automatic Smart Tagging. ATD IDs are sequential
  one-based and map to zero-based tactical frames; absent observations remain
  absent.
- Smart Tagging uses `round(seconds * 25)` and half-open intervals. It supplies
  contextual/team priors and restart context; it cannot alone force possession
  or DEAD. Parsed `Half` is unused.
- Homography is validated by tooling but is not an E04 inference input. Audio
  whistle detection is not integrated.
- P4 excluded homography from runtime inference because no independent runtime
  signal was demonstrated. P7 includes synthetic duplicate-tag coverage.
  Remaining unknown: independent accuracy and cross-modal contribution on
  admissible labeled data.

## Constraints

Follow root `AGENTS.md`: preserve the protected release, keep predictions
algorithmic and reproducible, do not hand-annotate or use private target labels,
do not tune/select on public labels, and keep licensed assets and reconstructive
derivatives local. Continue to optimize spellF1 first, with macroF1 secondary.

## Durable knowledge candidates

P7 integration semantics, exact-V3 byte equivalence, and the bounded
single-candidate public-check interpretation are durable; they are recorded in
the canonical P7 topic. Raw run paths and candidate outputs remain local-only.

## Exact next step

Proceed to the authorized P8 synthetic adversarial tests and ablations only
after checking the current plan/status. Preserve exact V3 as the fallback;
keep any candidate selection separate from public metrics and require explicit
owner authorization for promotion or submission.

## Provenance

File-based provenance only; Graphify was not used for this curation. Sources
read directly were the local v2.0 plan P7/G7 records, isolated
`TFV3_P7_INTEGRATION_REPORT.md`, root `memory.md`, and the ignored public
evaluation scoreboard and per-candidate JSON report. Relevant source
locations include `starter_v6/run_e04.py`,
`starter_v6/tests/test_phase7_integration.py`,
`evaluation/run_evaluation.py`, and
`evaluation/possession_metrics.py`. No restricted data, frame-level
annotations, or candidate outputs are included.
