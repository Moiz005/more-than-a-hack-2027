# T1 / Q1 / homography audit — 2026-11-02

## Summary and release decision

The completed audit is read-only and made no production inference, default-configuration, evaluator, or candidate-CSV changes. Its durable conclusions are:

- **T1:** `T1-REGRESSION — CORRECTABLE DEFECT REPRODUCED`. The event-aware predicate suppresses a distinguishable running/one-touch opposing reception when the receiver co-moves with the ball at nearly constant speed because support requires a measured ball-speed drop. A matched stationary-defender negative remains suppressed, so this is a missing positive evidence mode, not an indistinguishable history.
- **Q1/T1:** `INTERACTION-ISSUE-CONFIRMED`. Q1 can switch on the same constant-speed co-motion case; T1 neutralizes that switch. The issue is the T1 semantic gate, not numerical double attenuation.
- **Homography:** `HOMOGRAPHY-CURRENTLY-CORRECT` for tactical parsing, alignment, and existing metric-coordinate use; `HOMOGRAPHY-NO-INCREMENTAL-VALUE-DEMONSTRATED` for the current ATD-only runner; future image-based use is a separate `HOMOGRAPHY-VIDEO-DEPENDENT-OPPORTUNITY`.
- **Phase 5:** `P5-SKIP` for the current deadline window. The confirmed defect is not missing-ball-dependent, and no validated detector, labels, or packaged weights exist.

T1 is not promoted. Model development is frozen pending explicit authorization for a separate co-motion-aware T1 repair design/test task. B0 remains the protected fallback.

## Current architecture

```text
ATD tracking + automatic Smart Tagging + half metadata
  -> normalized ATD coordinates -> metric observations/features
  -> nearest/top-k/density/contest/motion/quality evidence
  -> raw play-state and live-team evidence
  -> H/A/D evidence potentials
  -> independent per-half log-space HMM/Viterbi
  -> H/A/D labels plus official X outside graded spans
```

The E04 runtime is self-contained in `starter_v6`: `games.py` selects inputs and half spans; `ingestion.py`, `features.py`, `possession.py`, `tag_features.py`, `inference.py`, and `pipeline.py` build evidence; `two_stage.py`/`hmm.py` decode; `run_e04.py` emits the submission. Evidence potentials are not calibrated probabilities. Missing ball does not imply `D`; HMM state does not cross half or `X` boundaries. T1 is an optional Stage 2 ownership-evidence policy and leaves Stage 1, D, X, and HMM transitions unchanged.

## Homography findings

Tactical homography has 199,319 contiguous zero-based rows, all valid and finite, with reprojection error retained as a quality field. The current ATD path already converts normalized coordinates to metres once before distance calculations; projecting to pixels and back would be redundant. Broadcast homography is not a safe substitute: it has a separate unsynchronized timeline, invalid spans, and a one-row tracking/video discrepancy.

The synthetic matrix audit H01–H18 passed except H06/H07, which remain helper limitations: near-singular inversion and zero projective denominator are not explicitly guarded. These are not demonstrated possession defects in the unused production path. Homography cannot recover a missing or airborne ball without an independent image observation and planar-validity/association guards.

## Verification and evidence limits

Recorded audit verification: full suite **442 passed**; T1 **49**, S2.1 **32**, and Q1 **6** passed; Stage 1/K1/O1 and half/X tests passed; E04 self-check, synthetic-resource check, compileall, `git diff --check`, B0/Q1/C01/T1 official validators, and two byte-identical T1 runs passed. Homography H01–H18 executed with H06/H07 recorded as limitations. No public score, public five-minute truth, private truth, manual target annotation, target frame list, or external match labels were used. Accuracy, spellF1, and macroF1 remain unmeasured.

## Protected provenance

- Audit branch: `audit/t1-q1-homography-comprehensive`.
- Audit commit: `64c2ad86354c9cc809dd4d211dcf17d62ddc0446` (`docs: audit T1 Q1 and homography robustness`).
- B0 inference: `4cc7ce0165e8f530a12bc8a55a604b4730e627ac`; verified protected output SHA256 `66a680dfe10dad38fd6a76bc46d86ffb526e8d76e120fce2b7e4f6e57953a238`, with 199,319 rows and H/A/D/X counts `85,064/70,964/2,829/40,462`.
- Q1 output SHA256: `71c3fbef1e856aa5ef0d3f41cd3c88c8be2e47ce2200c23f57739acb09bdcfa0`; T1 output SHA256: `22d35760d8bd651277600f891cfc1189938377ef839325fcf2e27048a6db8ebd`. B0 is the rollback reference, not T1.

## Authorized next action

Only after explicit user authorization: design and test a co-motion-aware T1 predicate using matched running/one-touch positives and stationary-defender negatives, without public-score tuning. Keep it in shadow evaluation until existing T1 protections, short recoveries, symmetry, missingness, and no-unsupported-change controls all pass. Do not start Phase 5 or release T1 automatically.

## Provenance

Primary source: `more-than-a-hack-2027/starter_v6/T1_Q1_HOMOGRAPHY_COMPREHENSIVE_AUDIT.md` and `T1_HOMOGRAPHY_NEXT_STEP_DECISION.md`, audited at graph/source revision `64c2ad86354c9cc809dd4d211dcf17d62ddc0446`. Graphify basis: bounded queries for `T1 constant-speed co-motion regression`, `homography audit Phase 5 video evidence`, and `provenance branch commit B0 fallback Q1`; cited nodes include `starter_v6/tests/test_phase5_ownership.py`, `starter_v2/ingestion.py:HomographyArrays`, `starter_v6/pipeline.py:iter_frame_evidence`, `starter_v6/inference.py:iter_infer_e02`, `starter_v6/hmm.py:decode`, `starter_v6/provenance.py`, and `games.py:video_to_id`.

Reviewed: 2026-11-02.
