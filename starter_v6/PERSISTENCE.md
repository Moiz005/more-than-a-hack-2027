# Bounded confirmed-stoppage persistence

Parent/rollback: `24e7d0146ec3d9493ed318d72dde6bee130f58ec`.

The production E04 runner already feeds `iter_infer_e02()` through
`StatefulDeadBallDetector`. Previously, missing coordinates caused
`observe_dead_ball()` to return no D cue, clearing confirmation and producing
H/A/D = (0.5, 0.5, 0), even immediately after a confirmed stoppage.

## Policy

`possession.deadball_persistence_frames` is an optional non-negative integer,
default 25. Zero restores previous behavior. This additive setting is captured
by existing effective-config and provenance serialization. Old JSON configs
remain loadable. The default matches the existing one-second missing-observation
horizon at 25 FPS; it is an engineering bound, not an empirically validated
stoppage duration. Synthetic windows 1, 3, and 25 are prespecified checks, not
candidates selected using match scores.

Only existing confirmation of observed-ball stoppage evidence seeds/refreshes
memory. No changes are made to cue thresholds or confirmation rules. Memory
stores the confirmation frame and raw strength capped at confirmed_dead_score.
It is cleared between halves. The production caller supplies confirmation
feedback once per frame; iter_raw_play_state applies the same confirmation
function and feedback for its own independent stream.

For age a = 1..N after the last fresh confirmation, a missing ball receives
qD = 1/3 + (max(1/3, strength) - 1/3) * (1 - a/(N+1)). The live remainder
1-qD splits equally across H/A via the existing emission path. It has provenance
`confirmed_stoppage_memory`, is not hard evidence, and is non-confirmable.
Thus it cannot receive the fresh-confirmation score boost or refresh itself.
The age counts elapsed frames, including intervening ambiguous observations.

After N frames the active D preference expires. Subsequent missing observations
receive neutral (1/3,1/3,1/3) evidence until fresh confirmation or credible live
return. A constant-size expired marker prevents old boundary-disappearance
context from resurrecting the same hypothesis. Neutral emissions do not force
a label: Viterbi may still choose D through a long neutral interval.

Observed restart/live-motion evidence, or strong team control on a frame without
dead cues, clears memory. The production quality flags for implausible jumps
and inconsistent speeds prevent those frames from retiring it. Existing raw
boundary/dead cues keep precedence. Missing coordinates alone cannot retire or
create a hypothesis. Existing fresh-frame scores are otherwise unchanged.

## Verification and scope

`python -B -m unittest starter_v6.tests.test_dead_ball_persistence` exercises
production inference and per-half decoding. The causal sequence with default
window is HHHH DDDDDD HHHHH versus HHHH DDD HHHHHHHH with zero window.
All 134 pre-existing tests plus 14 persistence tests pass at implementation time.
Full discovery includes restart, accepted-gap ownership, HMM exhaustive path,
source-provenance, and import-isolation regression tests.

H/A ownership, HMM, fusion, restart detection and tag interpretation are unchanged.
No new input data or dependency is used. Full local runs must use separate
ignored checkpoint paths and the official validator; no public truth is used.

Limitations: memory can extend D after an unseen restart or lose useful support
before a real stoppage ends. Existing detector false positives can seed memory.
New missing-ball stoppages are still not detected. The overlong set-piece tag
can still re-confirm D after delivery; that separate defect is intentionally
unchanged. Independent other-game labeled validation is not available.
