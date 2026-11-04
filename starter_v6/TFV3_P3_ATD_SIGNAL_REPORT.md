# TacticalFusion P3 — ATD Motion and Observation Signals

## Scope and result

Phase 3 adds a tactical-only, non-labeling signal layer in `atd_signals.py` and
makes motion provenance explicit in `features.py`. The E04 decoder, Stage 1/2
inference, H/A/D emissions, and CSV generation do not consume these proposals.
The feature group can therefore be ablated by omitting `iter_atd_signals()`;
the existing V3 inference remains the fallback.

## Existing V3 inventory

The inspected V3 path already has:

- normalized ATD coordinates scaled to the 105.3 × 68.0 m pitch;
- ball and player position, nearest and top-k team distances, density, contests,
  boundary distance, available unique-player counts, and missing-ball flags;
- provider ball speed and provider player speeds in the input contract;
- ball displacement and team-centroid motion at 25 FPS only between consecutive
  observed frames in the same half, plus ball/team co-motion;
- outlier and provider-speed/displacement mismatch flags, observation coverage
  quality weighting, and bounded missing-ball recovery (up to 25 frames);
- restart and stoppage cues with quality gates in the existing inference path.

V3 does not link row-local ATD slots as continuous physical player identities,
emit typed possession-control persistence, classify rapid uncontrolled motion,
or return a separate boundary/restart proposal with uncertainty. Its centroid
motion uses the observed team sets; no per-slot acceleration is computed.

## Added signal contract

`MotionFeatures` now exposes provider ball speed separately from displacement-
derived speed, records that the latter spans exactly one frame, and names
provider player-speed medians as provider values. Slot-set change is retained as
an observation-quality discount only; IDs are not used to calculate player
acceleration or identity continuity.

`iter_atd_signals()` returns immutable per-frame records for:

- **Control support:** a team must be within 1.5 m, separated by at least 0.75 m,
  pass the quality floor, persist for three consecutive observed frames, and have
  positive ball/team-centroid co-motion. Close opposition is explicit
  contradictory evidence. The output is a support hypothesis, not possession.
- **Rapid uncontrolled motion:** a plausible derived speed of at least 8 m/s,
  with no nearby player. It is labeled as unresolved rapid motion, not a shot,
  aerial ball, or possession change. Outlier/mismatch frames are excluded.
- **Boundary proposal:** an in-pitch observation followed by a plausible nearby
  out-of-pitch observation produces a low-confidence `touchline_hypothesis` or
  `goal_line_hypothesis`. This does not assert whole-ball crossing, last touch,
  or DEAD.
- **Stationary/restart proposal:** missing ball remains `unknown_missing_ball`;
  stationary ball without restart context remains `stationary_live_or_unresolved`.
  A restart proposal needs an observed stationary setup, current restart context,
  and two clean moving frames within a 75-frame setup horizon. A speed spike is
  rejected. No proposal changes a play-state label.

Control/restart temporal support resets on a missing sample or nonconsecutive
input; all support resets at a half change, and restart setup support also ends
when its context ends. No ball position or possession value is forward-filled.
Uncertainty is high by default and lower only for the narrowly supported
hypotheses above.

## Feature-level ablation and evidence

| Feature group | Existing V3 capability | Added value | Ablation result |
|---|---|---|---|
| Motion provenance | Provider/derived speed coexist in `FrameEvidence` | Separate fields; derived gap is exactly one frame | Removing the new layer leaves V3 trace unchanged |
| Control | Nearest distances and co-motion are available separately | Bounded persistence, opposition conflict, explicit uncertainty | Synthetic control support requires proximity + co-motion + persistence |
| Ball motion | Displacement and jump/mismatch flags | Rapid uncontrolled motion hypothesis, with no owner claim | Aerial/deflection/spike counterexamples do not produce control/restart claims |
| Boundary | Boundary distance and guarded DEAD cue exist | Distinct, low-confidence touchline/goal-line hypotheses | Only consecutive plausible crossing fixtures propose; missing/jump cases abstain |
| Restart execution | Existing contextual restart inference | Setup→persistent-motion proposal with explicit temporal expiry | Tag/setup or speed spike alone produces no proposal |

For neutral-mode equivalence, `trace_synthetic --all` was run against protected
commit `9fd0277a23258a448e0863b33d646c8540070c50` and the Phase 3 worktree. After
removing only the six Phase 2 metadata fields, the normalized traces match
exactly across **11 fixtures / 54 frame rows**. Those fields are
`half_values`, `interval`, `overlap_group_id`, `provenance`, `restart_types`, and
`source_teams`; no Phase 3 inference signal was added to the trace or decoder.

The isolated signal suite has **14 adversarial tests**. These cover persistent
control, contested/loose play, aerial-like rapid motion, deflection, speed
spikes, slot switches, missing and long gaps, return after stoppage, both
boundary axes, restart setup/persistence/expiry, and halftime resets. These are
synthetic contract checks, not accuracy estimates.

## Limits and G3 decision

No licensed match assets were available in the research worktree; no match-level
feature counts, prediction comparison, public-ground-truth score, spellF1, or
macroF1 claim was produced. Rapid motion can be a rolling pass, a shot, or a
tracking artifact; proximity/co-motion can still describe a nearby runner rather
than control; boundary hypotheses do not establish legal restart semantics.
Thresholds are conservative engineering defaults, not fitted values.

**G3 PASS (engineering contract only):** provenance and missingness are
preserved; synthetic counterexamples remain hypotheses/abstentions and never
create labels; the new feature group has discrete purposes beyond V3 and can be
disabled without changing the protected inference trace. Accuracy validation
and production integration remain unclaimed.
