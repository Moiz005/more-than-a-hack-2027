# E04 read-only investigation handoff — 2026-10-31

## Status and scope

This note records a read-only architecture and failure-mode investigation of
`starter_v6` using invented observations only. It is a diagnosis handoff, not
a fix, strategy selection, accuracy claim, or authorization to change the
frozen release.

The investigation artifacts are ignored local files under
`more-than-a-hack-2027/.local-checkpoints/investigation-20261031/`:
`gap_probe.py`, `probes.py`, `targeted_probes.py`, and their JSON result files.
They do not load licensed match inputs or public labels. The JSON files contain
raw synthetic traces and must remain local; this topic records only aggregate
failure findings.

## Confirmed v6 architecture and import graph

The E04 runner is locally self-contained. The runtime graph is:

`games.py → starter_v6.run_e04 → {config, ingestion, inference, pipeline,
tag_features, hmm, diagnostics, provenance}`

`starter_v6.inference` composes `features`, `possession`, `tag_features`, and
`emissions`. The pipeline converts aligned ATD rows to `FrameEvidence`, applies
restart-context detection, and feeds E02 inference. `fuse_evidence()` produces
finite normalized H/A/D evidence potentials; `hmm.decode()` performs
log-space Viterbi independently for each graded half. Ungraded frames remain
`X`, and spell extraction respects half boundaries. Runtime isolation tests
found no loaded `starter_v4` or `starter_v5` modules for the v6 runner.

This is an architecture description, not a recommendation to alter the
pipeline or decoder.

## Confirmed synthetic failure signals

The following behaviors are reproducible on synthetic fixtures and should be
treated as source-level diagnosis targets:

- A live standstill with strong nearby home control can be emitted as dead
  ball; collective stationary context can dominate live counter-evidence.
- A new whistle/restart followed by a long missing-ball interval can remain
  home-live rather than transition to dead ball when no independent expiry cue
  is present.
- Non-confirmable disappearance at a synthetic boundary can eventually become
  dead ball after persistence, despite the fixture expecting continued live
  state. This shows that missingness duration and dead persistence interact in
  a non-obvious way.
- Restart preparation motion can be accepted as a delivery before a legal
  restart is observed. A speed-mismatch observation can also consume restart
  context before downstream quality checks.
- Two adjacent distinct restart contexts can collapse into one continuous mask
  lifecycle, so later context is treated as already consumed.
- Aerial-pass geometry can assign a temporary opposing-team interval when the
  ball crosses an opponent in 2-D; the current inputs do not encode ball height
  or contact.
- A first return after a missing-ball gap can be treated as an outlier because
  there is no prior consecutive coordinate for the jump test.
- A fast restart delivery can fail the consumption path when displacement and
  reported speed disagree, leaving the downstream state inconsistent with the
  synthetic legal-delivery expectation.
- The default HMM transition prior suppresses one- and two-frame opposing
  evidence blips, while longer weak/neutral runs can be shaped primarily by
  persistence. The appropriate duration of genuine short control is unknown.
- Long expired dead context with missing observations can return to live H;
  an unknown-speed observation can interrupt an otherwise persistent dead
  interval.

These are characterization results only. They do not establish that any
corresponding event occurred in the target match.

## Confirmed implementation/configuration concerns

- The synthetic configuration probe accepted a pitch-width mismatch between
  possession and feature configuration (`68.0` versus `70.0`). This is a
  configuration-validation gap, not evidence that either value is correct for
  restricted inputs.
- Synthetic traces confirm the known emission-boundary signals already
  recorded by G2: raw restart suppression by team gating, mixed cue counting
  for dead confirmation, gap evidence not being represented in the HMM
  emission in the characterized path, and one-hot confirmed-dead emission.
  These remain unrepaired diagnosis items.
- The HMM emissions are evidence potentials rather than calibrated
  probabilities; synthetic behavior cannot calibrate transition parameters.

## Verification, release, and recovery

The latest verified release is tag `e04-v2-g8-final-verified` at commit
`535d07d01d42264e2d9753b403c2449b912105f5`. Its repeat-generated local output
hash is `1d7d7a7040aee1fc714311900cc161a88ed97fef4b78cb2d7e3aeb138176f2c7`.
The frozen E04_C7 rollback is tag `e04-c7-frozen` at commit
`7aa2f1b44b9db015a89d61fef797ebe83b4dadd2`; its preserved output hash is
`865c45993fff24c670912d6861fd37d4df3f2f90a0418690fb7cd7c7a75b9ceb`.

Prior release gates recorded deterministic generation, structural submission
validation, self-checks, synthetic resource checks, import isolation, and
source-manifest provenance. Recovery remains `git switch --detach
e04-c7-frozen` when the frozen baseline is required. New outputs must remain
under ignored checkpoint roots with distinct paths; no existing output should
be overwritten implicitly.

## Unknowns and compliance constraints

- No independent labeled other-match set or held-out split is available in the
  repository, so none of these findings can be ranked by possession accuracy.
- Public five-minute labels remain alignment/pipeline checks only and must not
  be used for tuning, threshold selection, or candidate ranking.
- No manual same-match annotation, frame-specific correction, external private
  label, corrected-tracking artifact, or reconstructive extract may be used.
- Licensed inputs, candidate outputs, raw traces, and input fingerprints stay
  local and out of `.knowledge/`, commits, and hosted-LLM prompts.
- Whether any synthetic short transition, restart preparation motion, or
  boundary disappearance corresponds to an official target label is unknown.
- Any future behavior change requires a separately authorized diagnosis/plan,
  new synthetic acceptance contracts, reproducibility gates, and a distinct
  version or explicitly authorized post-freeze workflow. This handoff makes no
  strategy decision.

## Exact fresh-session next step

Start with this topic and [E04 baseline and Phase 0–2 gates](e04-baseline-and-gates.md),
then prepare (without implementing) a separately authorized improvement
diagnosis/plan that maps each selected failure signal to permitted evidence,
an explicit synthetic acceptance contract, and rollback/provenance gates.
Keep both release refs available and do not inspect or tune against public
five-minute labels while choosing hypotheses.

## Provenance

Graph basis: bounded graphify queries for `starter_v6 architecture imports
pipeline inference HMM emissions dead ball restart tags`, `confirmed source
defects synthetic limitations investigation`, and `release refs hashes starter
v6 e04 c7`; cited nodes include `starter_v6/run_e04.py`,
`starter_v6/pipeline.py` (`iter_frame_evidence()` and `restart_frame_mask()`),
`starter_v6/inference.py` (`iter_infer_e02()`), `starter_v6/emissions.py`
(`fuse_evidence()`), `starter_v6/hmm.py` (`decode()`), and
`starter_v6/ingestion.py`. Repository sources include
`more-than-a-hack-2027/.local-checkpoints/phase1/G1_IMPORT_GRAPH.txt`,
`phase8/PHASE8_REPORT.md`, `phase7/PHASE7_REPORT.md`, and the ignored
`investigation-20261031` synthetic scripts/results named above. Reviewed
2026-10-31.
