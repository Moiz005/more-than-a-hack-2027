# V3 release provenance

Intended annotated tag: `e04-v3-g8-release`. Resolve its exact commit after the
mandatory checks; use the private release record for observed results and paths.
Selected model: C4 `6642298534727f59740d58efba82d678c35dae98`; Phase 6 parent
`ee57304922ff29aa9e3372e1603510669d5d8d56`. Release additions are documentation,
dependency records and synthetic tests only.

| Item | Frozen expectation |
|---|---|
| Executed source SHA256 | de971b7751ebbc625d84d08e92287d10c09f480438d4e86d0b5b794b8d734683 |
| starter_v6/config.example.json SHA256 | 132709c7843a1685dc3261d331cefa5570fa10137738ab6c32d61813e763f8f0 |
| Effective model configuration SHA256 | 500cc240b6527726f783e25df0a3143624486babe3286d57eb5272439601fae2 |
| CSV SHA256, historical C2/C3 expectation | d1604474717565a460d30bdef271d4e6e9b6c088c00bec84f6ef3d97a35f74ae |
| CSV structure | UTF-8, frame,label, 199319 rows, frames 0 through 199318 |
| Output labels | H/A/D in graded halves; X outside published graded spans |
| Interpreter | CPython 3.11.16, macOS 15.7.9 x86_64 |
| Environment | V3_RELEASE_ENVIRONMENT.json and requirements-release.txt |
| Primary fallback | e04-v3-phase0-persistence-baseline / d24d5ae7b02488807ab7167494496c93152bbafa |

The complete 16-path executed-source list and hash construction are in
V3_CANDIDATE_LEDGER.md. It covers games.py and all executed local v6 modules;
tests/docs are separate from the model hash. Every full run records its actual
loaded-source list and hashes; verify it matches the expectation above.

The effective-config hash intentionally excludes data/output/diagnostic/metadata
paths. Exact path-bearing effective config is retained privately per run. Full
defaults are resolved by load_e04_config; file bytes alone do not enumerate them.
HMM prior (.45,.45,.10), transitions ((.98,.01,.01),(.01,.98,.01),
(.025,.025,.95)); persistence25; confirmation2; acquisition3; micro_dead_filter off.
Restart gate: speed >.5m/s, observed displacement .1..1m when available,
reappearance player radius1.5m. Boundary and quality thresholds are unchanged.

## Inputs and private record

Required: licensed tactical ATD metadata/raw tracking and automatic Smart Tagging.
Video, broadcast tracking and homography are not consumed by the selected runner.
At preparation all three current input fingerprints equal preserved Phase 4
run1 fingerprints. Detailed names/absolute locations and hashes remain ignored.
Each new run must match the preparation, the other run and the historical input
fingerprints; no restricted inputs or per-frame diagnostics belong in Git.

Private audit root: `.local-checkpoints/v3/phase8/release_candidate_20261031/`.
The isolated checkout beneath it has its own ignored
`.local-checkpoints/v3/phase8/release_candidate/run1/` and `run2/` directories.
`release_verification.json` in the audit root records exact commit/tag, commands,
environment, input equivalence, validator outcomes, selected artifact path and
both observed hashes. `submission.csv` in the audit root is the stable final
copy only after successful verification. Creation uses exclusive paths.

Reproduction and validation commands are in V3_RELEASE_RUNBOOK.md. Do not use
--overwrite. Do not update dependencies or alter config after verification.

## Provenance limits

Historical runtime dependency metadata captured loaded distributions, not a
complete lockfile. This freeze additionally inventories every installed Python
distribution in the verified environment and pins those versions explicitly.
It is an environment snapshot, not a wheel-hash lock, OS image, ABI guarantee or
proof of cross-platform identity. Reproduction is checked in the verified local
environment. No independently labeled other-match accuracy measurement exists.
