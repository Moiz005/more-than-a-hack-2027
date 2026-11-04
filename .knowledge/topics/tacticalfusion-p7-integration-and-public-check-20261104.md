# TacticalFusion P7 integration and single-candidate public check

Last reviewed: 2026-11-04.

## Summary

TacticalFusion Phase 7 is complete with **G7 PASS — synthetic engineering and
exact-V3 fallback verified**. The work integrates the existing Stage 1
LIVE/DEAD lifecycle with Stage 2 ownership masking and exposes four reversible
runner modes. It does not establish possession accuracy or justify replacing
the protected V3 release.

The subsequent public evaluation was a **single-candidate pipeline-correctness
check only**. It was not a comparison, tuning exercise, threshold search,
candidate ranking, or improvement claim.

## P7 integration contract

- `exact_v3`: added ATD ownership fusion and typed Stage 1 lifecycle/masking
  disabled.
- `atd_only`: added ATD ownership fusion enabled; typed lifecycle disabled.
- `tag_context_only`: typed lifecycle and Stage 1→Stage 2 masking enabled;
  added ATD ownership fusion disabled.
- `atd_plus_tag`: both additions enabled; this was the one candidate used for
  the later public pipeline check.

Existing V3 Smart Tag evidence remains present in every mode. The added typed
restart role is isolated from the pre-existing tag prior, and homography is
omitted because P4 found no independent runtime signal. Audio and broadcast
inputs are excluded.

Confirmed DEAD masks H/A ownership potentials. A recognized restart returns to
LIVE with neutral ownership until the existing consecutive observed-control
gate accepts a team. Restart evidence does not itself identify the restarting
team; unknown or low-quality ownership remains neutral. Conflicting restart
types do not execute, and Free Kick setup without confirmed DEAD remains
ambiguous.

Hard-state precedence, half resets, ungraded `X`, HMM boundaries, and the
feature-off fallback are preserved. Diagnostics contain aggregate reasons and
play-state counts only.

## Verification and fallback

The synthetic integration suite passed 15 tests; the full `starter_v6` suite
passed 270 tests with 1 skipped. E04 self-check, the synthetic resource check,
and the official submission validator passed. The fresh `exact_v3` output was
byte-identical to the protected V3 output, with SHA256
`d1604474717565a460d30bdef271d4e6e9b6c088c00bec84f6ef3d97a35f74ae`.

The protected V3 baseline is commit
`9fd0277a23258a448e0863b33d646c8540070c50`. The P7 integration checkpoint is
commit `9ff501d18a4028f203738bb16528e686d8915bb3`. New integration behavior is
reversible without modifying the pinned baseline.

## Single-candidate public pipeline check

The `atd_plus_tag` candidate alone was scored on the public slice of 7,500
graded frames covering 17 public ground-truth possessions:

- macroF1: **0.7008**
- spellF1: **0.4114**
- transition F1 at ±25 frames: **0.2051**
- 1,000-bootstrap spellF1 interval: **0.2514–0.5714**

These values establish only that the generated CSV and official scorer execute
and produce aggregate diagnostics. They do not show improvement, superiority,
generalization, or private full-match performance. No other candidate was
scored in this run, and the public labels were not used for tuning, selection,
or ranking.

## Open issues and next step

- No admissible independently labeled other-match dataset or held-out split is
  available; comparative accuracy remains unverified.
- The public check has wide uncertainty and cannot resolve the candidate
  decision.
- P8 synthetic adversarial tests and ablations are the next authorized plan
  phase; preserve exact V3 as the fallback and keep any later candidate
  decision owner-authorized.
- The active plan's header/table record P7 complete, but its older final-state
  paragraph still says P5 is next. This plan inconsistency should be reconciled
  by the planner; this knowledge topic treats the explicit P7/G7 records and
  P8 dependency as authoritative.

## Provenance

Primary sources: `starter_v6/TFV3_P7_INTEGRATION_REPORT.md`,
`local ignored public-scorer JSON report (not included)`,
`.plan/gpt_plan/TacticalFusion — Kickoff-First Audio, Tracking & Event Fusion/task_plan.md`,
and root `memory.md` P7 entries. Public-check aggregates were read from the
ignored `phase7/public_eval_out/scoreboard.csv` and its per-candidate JSON report; no raw
match assets, candidate CSV contents, frame-level traces, or reconstructive
extracts were copied here.

File-based provenance only; Graphify was not used for this curation. Sources
read directly were `starter_v6/TFV3_P7_INTEGRATION_REPORT.md`, the v2.0
TacticalFusion `task_plan.md` P7/G7 sections, root `memory.md` P7 entries,
`phase7/public_eval_out/scoreboard.csv`, and its per-candidate JSON report.
Relevant source locations include
`starter_v6/tests/test_phase7_integration.py`,
`starter_v6/run_e04.py`, `starter_v6/pipeline.py`,
`starter_v6/inference.py`, `starter_v6/hmm.py`,
`evaluation/run_evaluation.py`, and
`evaluation/possession_metrics.py`.
