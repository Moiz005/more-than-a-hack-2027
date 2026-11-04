# Stage 1 missing stoppages and WhistleBridge proposal — 2026-11-03

## Current finding

Stage 1 can remain LIVE through a genuine legal stoppage when the ball exit,
referee decision, or exact restart onset is not represented by an independent,
temporally precise observation. This is an observability limit, not a
demonstrated hard-DEAD propagation, restart-lifecycle, HMM, or final-label
assembly defect.

The current tracking/Smart Tagging evidence can handle quality-valid boundary
crossings, confirmed stoppage cues, supported restart occupancy, and credible
LIVE recovery. It cannot safely infer the earlier DEAD onset in the ambiguous
pattern:

`LIVE observation → missing or near-boundary interval → later restart setup`

Missing ball, Smart Tag intervals, collective stillness, or later restart
delivery/reappearance do not independently identify the whistle or first legal
DEAD frame. The existing contract therefore avoids fabricating `D`.

## Research status and protected behavior

- `STAGE1-EVIDENCE-INSUFFICIENT` remains the current research decision.
- O1 offline multi-cue segmentation is `NO-GO`; a new decoder cannot recover an
  unobservable onset.
- S1.10 hard-DEAD accounting is reconciled: all graded hard-boundary frames
  reach DEAD; the apparent count discrepancy is timeline scope and semantic
  set difference, not lost evidence.
- V2-A/V2-A.1 visual ball detection is closed `NO-GO` and remains paused.
- No production inference, configuration, release dependency, candidate CSV,
  or X-mask behavior was changed by these investigations.
- Protected V3 remains the release reference; B0 and repaired S2.10 remain
  preserved fallbacks/references. No possession accuracy or private `spellF1`
  claim is established.

## WhistleBridge proposal

`WhistleBridge` (plan `WB-S1-AUDIO-2026-11`) is a proposed, local-only audio
experiment. Its hypothesis is that an independently detected, audible referee
stoppage whistle may add timing evidence missing from ATD and Smart Tagging.
This is not verified: audio usability, referee-whistle identity, stop-versus-
restart role, onset precision, and downstream benefit all remain open.

The proposal treats four problems separately:

1. audio whistle candidate detection;
2. referee/stoppage/restart/unsupported role classification;
3. pairing a validated stop event with a compatible restart or LIVE recovery;
4. constructing a bounded DEAD interval without backdating the onset.

A whistle alone must not seed hard DEAD. The proposed evidence contract
requires a validated stoppage-role event plus compatible lifecycle evidence,
keeps onset at or after the independently detected event, preserves existing
hard-DEAD evidence, rejects ambiguous/duplicate/unpaired events, and uses the
existing Stage 1 interface and Viterbi decoder if integration is eventually
authorized.

## Gates and constraints

The plan is **PROPOSED — NOT APPROVED FOR PRODUCTION**. It requires, in order:

- local audio-stream, codec, PTS/priming, and tactical-frame alignment checks;
- a reproducible detector with synthetic timing and acoustic controls;
- independently labeled other-match audio for whistle and stop/restart-role
  validation, including false-positive/hour and onset uncertainty;
- conservative lifecycle/pairing tests before any Stage 1 use;
- explicit authorization for an off-by-default integration whose disabled mode
  is byte-identical to the protected baseline.

Target-match audio, if ever inspected, must be processed locally with
aggregate-only reporting. No manual target-match whistle timestamps, public
five-minute tuning, private labels, arbitrary frame constants, hosted audio,
or reconstructive extracts are permitted. The proposal cannot guarantee full
stoppage recall and cannot claim improved possession scores from added `D`
frames or proxy counts.

## Open gaps

- The local tactical MP4 audio stream and its event-level alignment have not
  yet been verified for usable referee-whistle information.
- No independently labeled other-match whistle/role evaluation source is
  recorded as available; without one, the plan must stop as validation-blocked.
- Detector thresholds, model/weight choice, role classification, timing
  uncertainty, false-positive risk, and coverage are unvalidated.
- No WhistleBridge implementation, Stage 1 integration, candidate output, or
  release decision exists. V3 remains unchanged and must not be delayed by
  research.

## Related topics

- [Phase 1/Q1 and Phase 2/K1 status](phase1-q1-phase2-k1-status-20261101.md)
- [E04 baseline and Phase 0–2 gates](e04-baseline-and-gates.md)
- [E04 read-only investigation handoff](e04-investigation-20261031.md)
- [T1 / Q1 / homography audit](t1-q1-homography-audit-20261102.md)
- [Competition and data constraints](competition-and-data.md)

## Provenance

Primary sources: `.plan/gpt_plan/Audio-Anchored-Stoppage-Detection-for-Stage-1/task_plan.md`,
`more-than-a-hack-2027/starter_v6/STAGE1_MISSING_STOPPAGE_RESEARCH.md`,
`STAGE1_OFFLINE_SEGMENTATION_INVESTIGATION.md`,
`S1_10_HARD_DEAD_EVIDENCE_ACCOUNTING_AUDIT.md`,
`RELEASE_READINESS_MANIFEST.md`, and `V2_NOGO_RELEASE_FALLBACK_CLOSEOUT.md`.
Graphify basis: bounded query terms `Stage 1 missing stoppage`, `offline DEAD
segmentation`, `whistle`, and `restart lifecycle`; cited nodes include
`iter_frame_evidence()` (`starter_v6/pipeline.py:L159`),
`observe_dead_ball()` (`starter_v6/possession.py:L205`),
`iter_infer_e02()` (`starter_v6/inference.py:L227`),
`decode_play_state()` (`starter_v6/two_stage.py:L249`), and
`FrameEvidence` (`starter_v6/possession.py:L25`). The existing graph predates
the 2026-11-03 WhistleBridge plan, so proposal-specific claims are sourced
directly from that plan and are explicitly marked proposed.

Reviewed: 2026-11-03.
