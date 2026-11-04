# Archived: G1 handoff — starter_v6 independent with parity

This handoff was superseded by the consolidated current-state handoff.

## Objective

Verify that `starter_v6` runs independently of older starter packages while
preserving E04_C7 emissions, labels, tests, provenance, recovery, and output.

## Status

Complete. G1.1 through G1.5 passed.

## Durable evidence

- G1 report: `more-than-a-hack-2027/.local-checkpoints/phase1/G1_REPORT.md`.
- Import graph: `more-than-a-hack-2027/.local-checkpoints/phase1/G1_IMPORT_GRAPH.txt`.
- Final metadata, source manifest, and full CSV:
  `more-than-a-hack-2027/.local-checkpoints/phase1/verification_g1/`.
- Frozen recovery record:
  `more-than-a-hack-2027/.local-checkpoints/phase0/e04_c7_frozen_20261030/`.
- No direct legacy imports were found in runtime or test code under
  `starter_v6`.
- Runtime isolation and frozen synthetic parity passed.
- The original 83 public/synthetic tests passed; selected Phase 1 total was
  87, and full discovery including authorized local inventory was 88.
- Source provenance contained all 16 executed project Python files, with no
  v4/v5 or virtual-environment source entries.
- Current-commit full-match output was byte-identical to E04_C7.

## Constraints

No public five-minute ground truth was used for tuning, selection, or ranking.
No algorithm behavior changed, and no restricted rows or frame-level extracts
were copied into this handoff.

## Recovery

Keep the frozen tag and self-contained v6 baseline as reference. Begin new
behavioral work only after a separately authorized plan and synthetic contract.

## Provenance

Repository-backed summary of the former G1 handoff. Original operational
artifacts remain in the ignored local checkpoint directories.
