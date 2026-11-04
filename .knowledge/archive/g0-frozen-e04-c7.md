# Archived: G0 handoff — Frozen E04_C7 baseline recoverable

This handoff was superseded by the consolidated current-state handoff.

## Objective

Preserve E04_C7 exactly, establish a reproducible honest baseline, and prove
that the protected starter and evaluation directories were not changed.

## Status

Complete. G0.1, G0.2, G0.3, and G0.4 were satisfied.

## Durable evidence

- Annotated local tag: `e04-c7-frozen` at
  `7aa2f1b44b9db015a89d61fef797ebe83b4dadd2`.
- Full historical runtime import chain: `starter_v6 -> starter_v5 -> starter_v4`.
- Preserved checkpoint artifacts, diagnostics, metadata, configuration, hashes,
  environment, tag record, and runbook remain under the ignored local freeze
  directory:
  `more-than-a-hack-2027/.local-checkpoints/phase0/e04_c7_frozen_20261030/`.
- Regenerated full output matched SHA256
  `865c45993fff24c670912d6861fd37d4df3f2f90a0418690fb7cd7c7a75b9ceb`.
- Official structural validation passed for preserved and regenerated outputs.
- Public/synthetic baseline suite: 83 tests passed; the data-dependent local
  Smart Tagging inventory test was not reported as passing when its input was
  unavailable.
- E04 self-check and synthetic-resource check passed.

## Constraints

No public five-minute ground truth was used for tuning, candidate selection, or
ranking. No licensed match assets, frame-level labels, or reconstructive
extracts were copied into the knowledge base. The complete transitive source
manifest is authoritative for provenance.

## Recovery

Use `git switch --detach e04-c7-frozen` to recover the frozen reference. Any
behavior change requires a separately authorized experiment with synthetic
contracts and reproducibility gates.

## Provenance

Repository-backed summary of the former G0 handoff. Original operational
artifacts remain in the ignored local checkpoint directory.
