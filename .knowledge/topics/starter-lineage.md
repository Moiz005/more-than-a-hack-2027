# Starter lineage and approaches

## Canonical lineage

- `more-than-a-hack-2027/starter/` is the organizer's original baseline and must remain unchanged.
- `starter_v2/` is the project foundation and synthetic ingestion/diagnostics harness.
- `starter_v3/` is E01, forked from organizer starter: missing-aware possession evidence, separate dead-ball cues, and bounded continuity.
- `starter_v4/` is E02, forked from E01: team-level geometry, motion, observation quality, and gap-transition evidence.
- `starter_v5/` is E03, forked from E02: Smart Tagging as weak contextual evidence and normalized H/A/D emissions. Its `FrameEmission` scores are evidence potentials, not calibrated posterior probabilities.
- `starter_v6/` is E04, forked from E03: configurable three-state H/A/D log-space HMM/Viterbi decoding, independently per graded half. X remains the ungraded-frame output. Root `memory.md` has the runnable command and current status; `Ready to Run` means reproducible execution/format validation, not proven possession accuracy.

Root `memory.md` is the concise approach index and should be updated when a new version is actually created or materially changes. Distinct versions preserve reproducibility and parent lineage.

## Current E04 status

E04_C7 is the frozen, reproducible reference at tag `e04-c7-frozen`
(`7aa2f1b44b9db015a89d61fef797ebe83b4dadd2`). G1 made `starter_v6` locally
self-contained with exact synthetic and full-output parity; G2 added an
asset-free trace harness without changing prediction behavior. Use
[E04 baseline and Phase 0–2 gates](e04-baseline-and-gates.md) for gate
evidence, commits, tests, failure signals, and the next step.

## Provenance and confidence

Lineage and approach summaries were verified in root `memory.md`,
`starter_v5/README.md`, `starter_v6/README.md`, tracked version directories,
and the G0/G1/G2 checkpoint records. C6 provenance references
`.local-checkpoints/phase7/c6_e03_final_metadata.json`; that artifact records
source revision `61a1e874e83b6911b5ab9cd39e9f994a51d78db9`. Graphify's local AST
graph now provides provenance for v6 runtime nodes including
`starter_v6/synthetic.py`, `starter_v6/hmm.py`, and
`starter_v6/tests/test_import_isolation.py`; documentation-heavy claims remain
anchored to cited checkpoint files because semantic document extraction was
unavailable without an external key.
