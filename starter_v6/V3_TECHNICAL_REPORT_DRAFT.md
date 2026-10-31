# Missing-aware temporal possession inference — v3

## Problem and inputs

Infer H (home live possession), A (away live possession), D (dead ball), with X
outside published graded halves, for every tactical-video frame. Coherent
possession spells and stoppage boundaries matter more than isolated assignments.

The selected implementation consumes organizer-provided automatic tactical ATD
player/ball coordinates, speeds and team-slot metadata, plus automatic Smart
Tagging intervals. Missing/invalid observations remain explicitly missing.
ATD frame_id is one-based and maps to submission frame_id-1. Tag seconds use
the published 25 FPS tactical timeline and half-open intervals. Broadcast video,
broadcast tracking and homography are not used by the final runner; earlier
ingestion utilities support homography, but it is not an inference dependency.
No video inspection, external event API or learned model runs during prediction.

## Executed method and possession rules

Local starter_v6 modules combine nearest/top-k team geometry, density, motion,
contest and quality weighting into separate H/A evidence. Team tags can resolve
close geometry under existing gates; they are noisy priors, not ownership truth.
Established ownership and bounded uncertain/missing continuity avoid interpreting
every brief proximity change as controlled possession. Accepted gap recovery
requires existing historical-anchor and post-gap support; it is not missingness
alone. A brief contact is not directly observed as a labeled football deflection.

Owner-independent dead-ball cues include reliable structural boundary evidence,
supported restart preparation and collective stationary context. Cue-family
confirmation prevents unrelated weak cues borrowing each other's persistence.
Missing ball alone cannot confirm D. Known boundary discontinuities are gated
by the existing implausible-coordinate-jump flag; subsequent consistent boundary
evidence or independent cues can still establish a stoppage.

Runtime restart actions require recognized set-piece context plus stationary
setup or supported reappearance and credible observed movement. An accepted
action consumes that context, suppressing stale restart_stationary extraction
under the old tag while retaining independent new stoppage cues. Tag interval
end, nearby players and tracking disappearance alone do not prove a restart.

Confirmed D seeds decaying, non-confirmable missing-ball evidence for at most
25 frames. Credible live/restart evidence retires memory; expiry is uncertainty,
not evidence that play resumed. Detector state resets between halves.

Finite normalized H/A/D potentials preserve uncertain live ownership and soft D
support. A three-state log-space Viterbi decoder runs independently per graded
half with the frozen HMM settings. It uses future evidence offline; neutral
emissions can retain D through decoder inertia. Default micro-D filtering is off,
so strong brief structural stoppages can split same-team possession spells.
Published ungraded spans receive X. Graded output is H/A/D.

This rule-based design was retained because its observations, uncertainty and
synthetic counterexamples are inspectable and reproducible. No training or
calibration was performed for this freeze.

## Validation and selection

Phase 8 freshly ran 194 regression tests (187 existing plus seven official
spell-semantics tests), with no failures, skips or expected failures in the
authorized local environment. Coverage includes actual adapter-to-emission-to-
Viterbi lifecycles, historical causal comparisons, missingness/half resets,
exhaustive small HMM paths, import isolation and source provenance.

Original synthetic corrections include DDDHHDDDD -> DDDHHHHHH after recognized
restart context consumption, and HDH -> HHH for an isolated implausible boundary
jump. Reliable independent stoppages remain detectable. The official scorer is
exercised only with invented labels, including all five spell IoU thresholds,
one-to-one matching and X/grading behavior. These are not real accuracy estimates.

Full release validation requires two identical full-length CSVs generated from
the exact clean committed tree, official validation and matching source/config/
input fingerprints. V3_RELEASE_MANIFEST.md gives expected hashes; observed final
results and artifact identity are in the ignored release verification record.
The annotated release tag is created only after those checks succeed.

## Data, compliance and limitations

No labeled training dataset was used. No independent other-match labeled
accuracy comparison was completed. No target-match hand labels, corrected
tracking, third-party human events or private truth are used by this pipeline.
Older local public-sample scoring artifacts exist; their scores were not read,
rerun or used in this fresh selection. Historical decision influence cannot be
proved absent retrospectively. Current selection rests on documented engineering
evidence, not published five-minute scores or unlabeled D prevalence.

Full-match spellF1 superiority is unknown. Synthetic correctness, valid CSV
format and deterministic reproduction do not establish possession accuracy.
Remaining limitations include unseen restarts during occlusion, conservative
restart coverage, merged/overlong tag identity, missing-ball onset uncertainty,
persistence extension/expiry, decoder inertia, tactical standstill/goalkeeper
ambiguity, brief controlled handovers, and quality rejection of a genuine abrupt
crossing. There are no dedicated penalty, goal, foul or offside onset classifiers;
generic goal-to-kickoff context does not establish exact goal timing.

Licensed assets and reconstructive outputs stay local and ignored. Only public
source, synthetic fixtures and non-reconstructive provenance are release material.
Conditional external-data qualification may be separately authorized later.

## Reproduction and deliverables

See V3_RELEASE_RUNBOOK.md, V3_RELEASE_MANIFEST.md and requirements-release.txt.
Recover the entire tagged repository and use the authorized licensed tactical
inputs with CPython 3.11.16 and recorded dependencies. Preserve unique run paths.
Official SUBMISSION.md permits a short Markdown technical document, requires a
reproducible public code repository and the possession CSV, and requests team-
named deliverables. Team naming, public publication, form upload and receipt
remain Phase 9 actions; none is claimed here.
