# V3 Phase 6 — Verified candidate ledger

Assessment date: 2026-10-31, Asia/Karachi. Start C4, clean working tree.
No production/config changes or new external acquisition. Source hashes below
were recomputed from git objects using the 16-path runtime manifest, then checked
against historical metadata. Complete repository trees differ from model hashes.

## Candidate identity

| Candidate | Full commit | Repository tree | Executed source |
|---|---|---|---|
| C0 persistence fallback | d24d5ae7b02488807ab7167494496c93152bbafa | 13772f92cfd21364dfde7a11ab64f2f439790e31 | S0 |
| C1 consumed context | bd757b493180a96b39d2c57e5901829d4d507b87 | c47ea4995eefa284fec3cf45c21a1fa1ecb9bb28 | S1 |
| C2 boundary quality | 4f14c6a6bf72bf4498c942dd16d815bb5787d01b | c5c106bf70b4eaa45b8d336d5b76d519ac713d61 | S2 |
| C3 integrated lifecycle | 35749fdf3652ba501cead2d61b96651232925164 | 0102fd31e2e768e1c19b49a14dc3c6a400d9a046 | S2 |
| C4 feasibility documented | 6642298534727f59740d58efba82d678c35dae98 | e21b37aa1e91bb93812dfe14aed6e0ece031416d | S2 |

- S0: 4616663aef7743a60fc8d0f4f55ac0da7d10f4704231aa2af1d21d3b62caedd4
- S1: f949487eb5bd1300c6a3a31f2bf770bcdf6d7b7b6b879ecb556c7d1c04d5531b
- S2: de971b7751ebbc625d84d08e92287d10c09f480438d4e86d0b5b794b8d734683

Manifest: games.py; starter_v6/__init__.py, config.py, diagnostics.py,
emissions.py, features.py, hmm.py, inference.py, ingestion.py, intervals.py,
pipeline.py, possession.py, provenance.py, run_e01.py, run_e04.py, tag_features.py.
Algorithm: sorted relative path + NUL + file bytes, SHA256 (provenance.py).

## Common frozen configuration and environment

Every candidate's config.example.json is byte-identical, SHA256:
132709c7843a1685dc3261d331cefa5570fa10137738ab6c32d61813e763f8f0.
Recorded model-effective config hash:
500cc240b6527726f783e25df0a3143624486babe3286d57eb5272439601fae2.
Observed run metadata: Python 3.11.16; loaded third-party distribution manifest
setuptools=79.0.1. This is not a complete environment lockfile. Current tests
also use numpy=2.4.6 and pandas=3.1.0 for official synthetic scorer checks.

HMM prior (.45,.45,.10); transitions ((.98,.01,.01),(.01,.98,.01),
(.025,.025,.95)); floor 1e-12, weight=1, temperature=1.
Possession persistence=25 frames, acquire_frames=3, control_radius_m=1.5,
min_observation_confidence=.6, deadball_confirm_frames=2, micro_dead_filter=off.
Full defaults and effective configuration are preserved in each metadata file.
The entire feature module, HMM and example configuration are identical across
C0-C4. Ownership _team_evidence, _resolve_gap and _attach_gap_evidence ASTs
are identical across all candidates. No H/A model or HMM change is hidden here.

## Mechanisms and isolated source differences

| Candidate | Stateful D | Runtime action | Persistence | Consumed context | Boundary jump gate |
|---|---|---|---|---|---|
| C0 | yes | yes | 25 | no | no |
| C1 | yes | yes | 25 | yes | no |
| C2/C3/C4 | yes | yes | 25 | yes | yes |

C0->C1 changes production pipeline.py and possession.py only: lifecycle flag
propagation and restart_stationary gating. C1->C2 changes inference.py and
possession.py only: specific boundary jump flag, existing non-boundary helper
extraction and boundary-history protection. Existing unrelated cue precedence
can consequently fall through; this is a documented part of M5, not a separate
unidentified model change. C2->C3->C4 production byte equality was verified.

## Existing artifacts reverified in Phase 6

| Candidate | Checkpoint directory | Artifact revision | CSV SHA256 | Historical tests |
|---|---|---|---|---|
| C0 | .local-checkpoints/v3/phase0/d24d5ae_verified | d24d5ae | H0 | 148 |
| C1 | .local-checkpoints/v3/phase1/context_consumption | 3804387 | H1 | 158 |
| C2 | .local-checkpoints/v3/phase3/boundary_quality | 137fd3f | H2 | 166 |
| C3 | .local-checkpoints/v3/phase4/lifecycle_integration | a6f013a | H2 | 182 |
| C4 | no dedicated full generation; inherits identical C3 model | none | H2 by source equivalence, not a new run | 182 |

- H0: 7596d3908f16dec3fee299ffa6538d9184a1d9ddcbd24fbb3f0e3265820583b0
- H1: e501d82f0fb15650761e7d594cea35999166e89e54122e3392c4a052615b4763
- H2: d1604474717565a460d30bdef271d4e6e9b6c088c00bec84f6ef3d97a35f74ae

For C0-C3, run1/run2 CSV byte equality was rechecked, hashes recomputed, and
run1 officially revalidated: 199319 rows, frames 0..199318. Corresponding
clean-commit metadata includes config/source/dependency manifests. The listed
artifact revisions differ from final documentation commits but their executed
source matches the named candidate, verified by git-content hashes.
Historical test counts are recorded phase evidence, not newly rerun historical
full suites. Phase 6 freshly ran the current suite (187 passing) and source-
archived production counterfactuals for all five candidates. Existing clean run
records do not establish accuracy, full system package pinning or external labels.

FULL GENERATION NOT REPEATED: no production/config changes, paired preserved
outputs and source equivalence already establish the required engineering record.
No new target-match instrumentation. Private assets/CSVs remain ignored.

## Decision and recovery

Select exactly C4 (6642298534727f59740d58efba82d678c35dae98) for release preparation.
It is the C2 executable model with C3 lifecycle verification and C4 legal
feasibility record. C0/C1 retain demonstrated synthetic defects; C2/C3 are
equivalent models but less complete handoffs. This is not a spellF1 ranking.
Backup C0 is explicit and recoverable, not claimed accurate or superior.

Restore any full candidate tree after preserving current work:
`git switch --detach FULL_COMMIT_FROM_TABLE`.
Frozen backup: `git switch --detach e04-v3-phase0-persistence-baseline`.
Assessment rollback: `git switch --detach 6642298534727f59740d58efba82d678c35dae98`.
Historical releases/tags remain intact; no release tag is moved or newly created.
Decision A: skip optional Phase 7; proceed to Phase 8 only when authorized.
