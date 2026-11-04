# Phase 1/Q1 and Phase 2/K1 status

Last reviewed: 2026-11-02.

## Summary

The current implementation is the self-contained `more-than-a-hack-2027/starter_v6`
pipeline. It ingests licensed ATD tracking, automatic Smart Tagging, and half
metadata; builds `FrameEvidence`, restart context, raw play-state and live-team
evidence; fuses H/A/D evidence potentials; decodes each graded half independently
with a three-state log-space HMM/Viterbi decoder; and emits `H`, `A`, `D`, or the
official `X` mask outside graded spans. The pipeline treats emissions as
evidence potentials, not calibrated probabilities, and missing ball observations
do not imply `D`.

Current status is release-protective: keep B0 as the rollback/reference artifact,
retain Q1 only as an opt-in experimental candidate, and do not implement K1 or
select a new submission from either phase without separate authorization and
permitted evidence.

## Protected references

- **B0:** inference commit `4cc7ce0165e8f530a12bc8a55a604b4730e627ac`;
  release-documentation reference `1712475cfcdeaa0b4e3d221186473c318bb45c9a`;
  protected candidate SHA256
  `66a680dfe10dad38fd6a76bc46d86ffb526e8d76e120fce2b7e4f6e57953a238`.
  The expected artifact has header `frame,label`, 199,319 rows for frames
  `0..199318`, with H=85,064, A=70,964, D=2,829, X=40,462.
- **Q1:** `starter_v6/config.q1.quality_aware.json`, opt-in only. Two runs were
  byte-identical with SHA256
  `71c3fbef1e856aa5ef0d3f41cd3c88c8be2e47ce2200c23f57739acb09bdcfa`;
  Q1 labels were H=103,758, A=52,270, D=2,829, X=40,462. Its D/X masks
  exactly match B0; this is structural/reproducibility evidence, not accuracy.

## Completed work

### Phase 1 / Q1 — quality-aware Stage 2 emissions

The source audit reproduced a real semantic defect: `_team_evidence` scales H/A
support by observation quality, but the existing decoder normalized only
`home/(home+away)` and `away/(home+away)`, cancelling any common quality scale.
Q1 adds an opt-in quality-tempered share
`0.5 + w * (p_raw - 0.5)` using existing bounded quality semantics, with
fail-safe neutralization for missing, invalid, unresolved, implausible-jump, or
speed-inconsistent evidence. S2.1 high-speed transit handling remains intact;
Stage 1, D, X, HMM transitions, and default `existing` mode are unchanged.

Validation recorded in the acceptance report: six targeted Q1 tests, 51 existing
Stage 2/config tests, and 318 full local tests passed; both full Q1 runs passed
`evaluation/validate_submission.py` and were byte-identical. No public five-minute
truth, private labels, or manual target-match annotations were used. Q1 is not
promoted to the default or final submission.

### Phase 2 / K1 — generic kickoff or half-start DEAD feasibility

**Verdict: K1-NO-GO — INSUFFICIENT AUTOMATIC EVIDENCE.**

Kickoff evidence comes only from permitted automatic inputs: Smart Tagging,
ATD, and `games.py` half metadata. Smart Tagging contains 638 automatic events,
including two `Kick Off (Start)` and four `Kick Off (After Goal)` events. The
parser maps tactical-video seconds with `round(seconds * 25)`; kickoff intervals
are phase intervals, not exact whistle or ball-in-play timestamps. `games.py`
supplies the half boundaries/metadata used to establish the graded openings.

The opening audit found no stationary-ball observations and no qualifying
initial-DEAD evidence in either graded half: the first opening had kickoff
context but not the confirmable setup cue; the second had no kickoff context at
the graded start. A later tag cannot safely backfill an unobserved prefix, and a
tag interval alone cannot establish the exact DEAD-to-LIVE boundary.

K1-T01 through K1-T38 plus an indistinguishability control exercised the
production path. Positive synthetic controls show that the existing architecture
can represent generic pre-kickoff DEAD when required automatic observations exist;
the target opening lacks those observations. Therefore no `WAITING_FOR_KICKOFF`
state, half-specific DEAD prefix, fixed wait, or retrospective fill was added.
No K1 candidate output was created, and Q1/B0 behavior remained unchanged.

A later standalone diagnostic temporarily rewrote the published second-half
opening interval after CSV export. That diagnostic was explicitly non-compliant,
was never a candidate, and has been removed. No hardcoded kickoff interval or
experiment-only execution path remains in the active repository. Its historical
aggregate evidence is preserved in
`more-than-a-hack-2027/starter_v6/K1_PUBLISHED_KICKOFF_DIAGNOSTIC_RETIREMENT.md`.

## Validation and evidence limits

B0 compatibility reproduced the protected output hash and row/class counts.
Q1 passed its targeted, regression, deterministic-run, and structural-validator
gates. K1 passed its synthetic feasibility matrix and regression compatibility,
but failed the implementation GO gate because target-visible automatic evidence
was insufficient. No independently labeled other-match set is available in the
workspace, so possession accuracy, spellF1 improvement, and superiority of Q1 or
B0 remain unmeasured. Public five-minute labels are alignment/pipeline checks
only and must not be used for tuning, ranking, or selection.

## Unimplemented future options

The current Stage 1 missing-stoppage finding and the separate proposed
WhistleBridge audio path are recorded in [Stage 1 missing stoppages and
WhistleBridge proposal — 2026-11-03](stage1-stoppage-and-whistlebridge-20261103.md).
WhistleBridge is research-only and not approved for production; it does not
change the B0/V3 release posture or reopen the closed visual detector route.

The later read-only T1/Q1/homography audit supersedes the release posture for
the homography/video option and records the current `P5-SKIP` decision; see
[T1 / Q1 / homography audit — 2026-11-02](t1-q1-homography-audit-20261102.md).

1. **Improve ATD + Smart Tagging evidence:** only pursue a generic, independently
   observable kickoff/stoppage or possession-evidence improvement after a new
   source-backed diagnosis and synthetic acceptance gate. Do not infer a
   match-specific prefix from the known target interval or from missingness alone.
2. **Independently validated video-based evidence using homography:** prototype
   locally on invented or independently permitted video fixtures, map detections
   through quality-valid homography, and require a paired false-detection control,
   reproducibility, licensing, and runtime/resource approval before integration.
   This option is not implemented and must not use manual target-match labels or
   hosted processing of restricted assets.

## Related topics

- [E04 baseline and Phase 0–2 gates](e04-baseline-and-gates.md)
- [E04 read-only investigation handoff — 2026-10-31](e04-investigation-20261031.md)
- [Competition and data constraints](competition-and-data.md)

## Provenance

Repository sources: `.plan/gpt_plan/recommended-path-0.8/task_plan.md`;
`more-than-a-hack-2027/starter_v6/STAGE2_QUALITY_EMISSIONS_INVESTIGATION.md`;
`STAGE2_QUALITY_EMISSIONS_ACCEPTANCE.md`; `STAGE1_KICKOFF_FEASIBILITY.md`;
`STAGE1_HALF_START_INVESTIGATION.md`; `EXTERNAL_VALIDATION_FEASIBILITY.md`;
`starter_v6/README.md`; and `games.py`. Graphify basis: bounded queries for
`starter_v6 architecture Phase 1 Q1 Phase 2 K1`, `Smart Tagging ATD games.py
half metadata kickoff`, and `homography independently validated video evidence`.
Cited graph nodes include `starter_v6/run_e04.py`, `starter_v6/pipeline.py`
(`iter_frame_evidence()` and `restart_frame_mask()`),
`starter_v6/inference.py` (`iter_infer_e02()` and `_team_evidence`),
`starter_v6/hmm.py` (`decode()`), `starter/load_smart_tagging.py`,
`starter/load_atd.py`, `games.py` (`half_video_blocks()`),
`FrameEvidence`, `SmartTagEvent`, and `HomographyArrays`.
