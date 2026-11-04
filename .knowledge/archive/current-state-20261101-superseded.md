# Superseded handoff — 2026-11-01

Superseded on 2026-11-04 by
[`../handoffs/current-state-20261104.md`](../handoffs/current-state-20261104.md).
The active checkout and next authorized action changed; retain this record for
history only and do not use it as the session starting point.

Last reviewed: 2026-11-03.

## Start here

Project root: `local project workspace`.

Source repository: `.`.

Primary current topic:
`../topics/phase1-q1-phase2-k1-status-20261101.md`.

Latest audit decision:
`../topics/t1-q1-homography-audit-20261102.md`.

Latest Stage 1 research topic:
`../topics/stage1-stoppage-and-whistlebridge-20261103.md`.

Read the repository `AGENTS.md`, the recommended-path plan at
`.plan/gpt_plan/recommended-path-0.8/task_plan.md`, and the current topic before
changing source or selecting a candidate.

## Current architecture

```text
ATD tracking + automatic Smart Tagging + half metadata
        -> FrameEvidence / quality features
        -> restart context and raw play-state evidence
        -> Stage 1 LIVE/DEAD per-half HMM/Viterbi
        -> Stage 2 H/A decoding on LIVE segments
        -> H/A/D plus official X mask
```

The pipeline treats evidence potentials as uncalibrated evidence, not truth
probabilities. Missing ball observations do not imply DEAD. Smart Tagging is
automatic phase context; ATD provides tracking and motion observations; half
metadata comes from `games.py` tracking-derived spans.

The completed read-only T1/Q1/homography audit is on branch
`audit/t1-q1-homography-comprehensive` at commit
`64c2ad86354c9cc809dd4d211dcf17d62ddc0446`. It confirmed a T1 regression:
running/one-touch opposing receptions with constant-speed co-motion can be
suppressed because T1 requires deceleration, while Q1 can switch on the same
case. Tactical homography is parsed/aligned correctly but adds no demonstrated
information to the ATD-only runner. Phase 5 is `P5-SKIP`; no production change
or candidate promotion occurred.

## Protected references

- **B0:** inference commit `4cc7ce0165e8f530a12bc8a55a604b4730e627ac`;
  documentation reference `1712475cfcdeaa0b4e3d221186473c318bb45c9a`;
  output SHA256
  `66a680dfe10dad38fd6a76bb46d86ffb526e8d76e120fce2b7e4f6e57953a238`;
  counts H=85,064, A=70,964, D=2,829, X=40,462.
- **Q1:** opt-in `starter_v6/config.q1.quality_aware.json`; implementation
  commit `7c526ebb953e1bf538ef3b01fef50b6f51a3ab00`; documentation commit
  `0b84ce9f0c3bc91b73c4e7000aae8a1a574af7b9`; output SHA256
  `71c3fbef1e856aa5ef0d3f41cd3c88c8be2e47ce2200c23f57739acb09bdcfa0`.
  Q1 is not selected or default.
- **Frozen V3:** tag `e04-v3-g8-release` at
  `9fd0277a23258a448e0863b33d646c8540070c50`.

## Completed phases

### Phase 1 / Q1

The source audit found that quality-scaled H/A support was normalized in a way
that canceled the common quality factor. Q1 tempers H/A direction toward
neutral using bounded quality, preserves S2.1 transit handling, and leaves
Stage 1, D/X, transitions, and default behavior unchanged. Six targeted tests,
51 existing Stage 2/config tests, 318 full tests, deterministic full runs, and
submission validation passed. No public ground truth was used for selection.

### Phase 2 / K1

**Verdict: K1-NO-GO — INSUFFICIENT AUTOMATIC EVIDENCE.**

The existing architecture can represent generic pre-kickoff DEAD when valid
stationary/confirmed restart evidence exists. The supplied openings do not
provide sufficient independent evidence: the first opening has limited kickoff
context but no qualifying stationary preparation cue; the second opening lacks
kickoff context at the graded start. A tag interval alone, missingness alone,
later motion, or a hard-coded prefix is insufficient. K1-T01 through K1-T38
plus an indistinguishability control passed as synthetic feasibility tests, but
the implementation GO gate failed. No production K1 state or candidate was
created.

## Rules and limits

- Do not use public five-minute labels for tuning, ranking, or candidate
  selection.
- Do not use private labels, manual target-match annotations, frame-specific
  constants, or reconstructive match extracts.
- Do not promote Q1 or implement K1 without a separately authorized evidence
  gate.
- No independently labeled other-match set is available; possession accuracy,
  spellF1 improvement, and macroF1 superiority remain unmeasured.

Verification recorded for the audit: 442 full-suite tests; T1 49, S2.1 32,
Q1 6; self-check, synthetic-resource check, compileall, diff check, official
validators, and two byte-identical T1 runs passed. H01–H18 homography tests
executed; H06/H07 remain helper limitations. The verified B0 fallback is
inference commit `4cc7ce0165e8f530a12bc8a55a604b4730e627ac` with output SHA256
`66a680dfe10dad38fd6a76bc46d86ffb526e8d76e120fce2b7e4f6e57953a238`.

## Release posture and next authorized action

Keep B0 as the protected fallback and do not release T1 or start Phase 5.
After explicit authorization, the next action is a design/test task for a
co-motion-aware T1 predicate using matched running/one-touch positives and
stationary-defender negatives, with shadow evaluation and no public-score
tuning. Preserve all existing T1 protections and require reproducibility before
any release decision.

Stage 1 missing-stoppage research remains an observability limitation rather
than a demonstrated decoder defect. The proposed WhistleBridge local audio
experiment is not approved for production and must first pass audio/alignment,
independent other-match event-role validation, conservative stop/restart
pairing, and explicit integration gates. See the linked canonical topic.

## Provenance

Primary sources: `.plan/gpt_plan/recommended-path-0.8/task_plan.md`,
`more-than-a-hack-2027/starter_v6/STAGE2_QUALITY_EMISSIONS_INVESTIGATION.md`,
`STAGE2_QUALITY_EMISSIONS_ACCEPTANCE.md`,
`STAGE1_KICKOFF_FEASIBILITY.md`,
`more-than-a-hack-2027/starter_v6/run_e04.py`,
`starter_v6/pipeline.py`, `starter_v6/inference.py`, `starter_v6/two_stage.py`,
and `games.py`. Historical handoffs are preserved in
`../archive/g0-frozen-e04-c7.md` and `../archive/g1-starter-v6-parity.md`.
