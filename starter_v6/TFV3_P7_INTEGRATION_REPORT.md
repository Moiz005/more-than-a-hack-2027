# TacticalFusion Phase 7 — Stage 1 / Stage 2 integration

**Status:** G7 PASS — integration and exact-V3 fallback verified.
**Scope:** Tactical ATD and tactical Smart Tagging. P4 rejected runtime homography as an independent feature. No audio or broadcast data is used.

## Integration contract

- Four strict runner presets are available through `integration_mode`:
  - `exact_v3`: new ATD ownership fusion and Stage 1 lifecycle/mask off.
  - `atd_only`: new ATD ownership fusion on; typed Stage 1 lifecycle off.
  - `tag_context_only`: typed Stage 1 lifecycle and Stage 1→Stage 2 masking on; new ATD ownership fusion off.
  - `atd_plus_tag`: both new ATD ownership fusion and typed Stage 1 lifecycle/masking on.
- Existing V3 Smart Tag evidence remains enabled in all presets. `tag_context_only` isolates the added typed restart/lifecycle role of tags, not the pre-existing E03 tag prior. The feature booleans remain independently configurable for custom runs; the owner mask requires Stage 1 lifecycle. Legacy `ownership_mode` remains supported and cannot be combined with `integration_mode`.
- The ATD+tag+homography candidate is deliberately absent: P4's source audit rejected homography as an additional independent runtime feature.
- Confirmed Stage 1 DEAD removes H/A ownership potentials. On recognized LIVE restart execution, the emission becomes owner-neutral until the existing consecutive observed-control acquisition rule accepts H or A. An independently observed LIVE recovery is passed through once the same configured support gate is met.
- Restart evidence does not choose the restarting team. Unknown/low-quality ownership remains neutral. Conflicting restart types cannot execute. Free Kick setup and motion without a confirmed DEAD interval is not accepted as an awarded restart, preserving the advantage/live possibility.
- Existing hard-state precedence, half resets, ungraded X rows, HMM boundaries, and V3-compatible presets remain available. Integration diagnostics contain aggregate play-state and reason-code counts, not frame-level match traces.

## Controlled comparisons

The named modes differ only by their documented feature switches. This phase defines executable settings; it does not compare their public-label scores or select a winner. `exact_v3` must reproduce the protected V3 output. ATD-only and typed-tag-lifecycle contributions can be ablated independently. Homography is excluded under G4.

## Verification

All fixture inputs are invented. The synthetic integration suite covers the six restart types from DEAD through LIVE to separately reacquired H control (including `acquire_frames=1` with acquisition beginning after the action frame), same-frame restart action over stale DEAD cues, Free Kick advantage ambiguity, duplicate tag evidence, contradictory restart types, confirmed-DEAD ownership masking, missing ball, half reset, and exact-mode equivalence with legacy restart context and a Smart Tag.

Using the required project virtual environment:

- Phase 7 integration suite: **15 tests passed** (including `acquire_frames=1` restart boundaries
  across all six types, prior-DEAD restart precedence, and isolated missing-ball/half-reset cases).
- Full `starter_v6` suite: **270 passed, 1 skipped**.
- `run_e04 --self-check`: passed.
- `run_e04 --synthetic-resource-check`: passed on two independent half-length synthetic streams.
- The protected baseline CSV and a fresh final `integration_mode=exact_v3` prediction CSV were **byte-for-byte identical**, each 199,319 rows, with SHA-256 `d1604474717565a460d30bdef271d4e6e9b6c088c00bec84f6ef3d97a35f74ae`. The protected V3 source already supplied `restart_frame_mask`; exact mode retains that legacy context. New typed restart/lifecycle and owner-mask behavior remains off. Earlier research exact-mode prediction CSVs were also byte-identical. Runner diagnostics now include additive aggregate integration counters, so the diagnostics artifact is not claimed byte-identical.
- Official `evaluation/validate_submission.py` passed on the protected baseline and research exact-mode output.
- The protected checkout remained clean at `9fd0277a23258a448e0863b33d646c8540070c50`.

No public-ground-truth evaluation was run. The exact-output comparison verifies fallback equivalence and output structure only; it is not an accuracy or improvement result.

No public-ground-truth scores or private labels were used. Synthetic tests establish integration behavior only; they do not measure spellF1, macroF1, match accuracy, or improvement.

## Limitations

A LIVE restart does not establish its owner. Stage 2 may remain X/neutral until enough observed control accumulates, and the offline HMM may smooth that boundary. A recognized restart action after an already-confirmed DEAD interval clears same-frame stale DEAD cues; a restart action alone cannot erase a newly observed stop. Free Kick advantage remains observationally ambiguous without referee evidence. No homography, audio, or broadcast feature is fused. Confidence and emission values are heuristic evidence potentials, not calibrated probabilities.
