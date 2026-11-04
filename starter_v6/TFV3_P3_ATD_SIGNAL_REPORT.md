# TacticalFusion P3 — ATD Motion and Observation Signals

## Scope and result

Phase 3 added a tactical-only signal layer in `atd_signals.py` and made motion
provenance explicit in `features.py`. The original Phase 3 release left these
signals outside inference. A separately authorized, opt-in inference bridge is
now documented below; default E04 behavior remains the fallback.

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

## Opt-in inference bridge follow-up

The isolated bridge consumes streamed ATD signals in `iter_infer_e02()` when
`features.atd_signal_fusion_enabled` is true. Persistent control support may
corroborate an already geometrically admissible team and raise its observation
confidence; boundary and rapid uncontrolled-motion hypotheses temper team
confidence. Restart motion shortens acquisition only when the proposal and
control support identify the same team. No ATD proposal creates `D`, and
missing-ball behavior is unchanged. Existing Smart Tag evidence continues to
enter team inference and is now retained with typed provenance in each result.
Default configuration keeps ATD fusion off.

The reproducible opt-in example is `config.atd-fusion.example.json`. On the
authorized tactical input, the full 199,319-frame candidate passed the official
submission-format validator. Compared with the earlier Phase 3 output, 2,758
labels changed. This confirms inference integration and a behavioral effect,
not correctness or improvement. Aggregate counters record 23,533 persistent
control/fused frames, 65 boundary hypotheses, 33,440 rapid-motion hypotheses,
2,981 restart-motion hypotheses, 2,403 restart-context/control matches, and
139,587 active-tag-context frames.
The competition's public five-minute labels are restricted to alignment,
format, and label-semantics checks; they cannot be used to compare versions or
claim gains. A single-candidate pipeline diagnostic on the 7,500 graded public
frames reported macroF1 0.6836 and spellF1 0.4235 (17 ground-truth possessions);
these scores were not compared or used for selection. P4 and formal promotion
gates remain unstarted.
