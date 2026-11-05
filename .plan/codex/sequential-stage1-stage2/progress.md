# Progress — Sequential Stage 1 → Stage 2

## Current state

- Branch: `experiment/e04-v3-visual-possession`.
- Interpreter: `more-than-a-hack-2027/.venv/bin/python`.
- Implementation remains opt-in and all generated match artifacts remain under ignored `.local-checkpoints/`.
- Focused sequential/integration suite: 22 tests passed.
- Full `starter_v6` suite: 345 tests passed after fixing a lazy HBK import cycle.
- E04 self-check passed; full graded-length synthetic resource check processed 158,857 frames with peak reported memory 32.48 MiB.
- First end-to-end sequential candidate wrote 199,319 rows and passed the official validator. Aggregate diagnostics: 138,588 Stage 1 LIVE/Stage 2 frames, 20,269 DEAD, 40,462 UNGRADED, 52 LIVE segments; HBK-01 prefix applied to 2,235 frames. Its output SHA-256 was `78f1e120f9bc22bf0c8d8992100cf09b20ea7d9fb8e0a8e2b9e5c1eb2597b7a4`.
- Final-code candidate regeneration completed; output SHA-256 remained `78f1e120f9bc22bf0c8d8992100cf09b20ea7d9fb8e0a8e2b9e5c1eb2597b7a4` across three sequential generations.
- Final sequential candidate passed official validation: 199,319 rows / frame 0..199,318; H 74,863, A 63,725, D 20,269, X 40,462.
- Full `starter_v6` suite after the final lifecycle/restart change: 346 passed. Focused sequential suite: 23 passed. `py_compile`, E04 self-check, synthetic resource check, and `git diff --check` passed.
- Protected `exact_v3` regenerated and passed validation; its SHA-256 `d1604474717565a460d30bdef271d4e6e9b6c088c00bec84f6ef3d97a35f74ae` exactly matched the protected release.
- One public compatibility evaluation ran against only the sequential candidate: 7,500 graded frames; macroF1 0.6083; spellF1 0.3636; bootstrap intervals and full reported fields are recorded in `starter_v6/SEQUENTIAL_STAGE1_STAGE2_IMPLEMENTATION_REPORT.md`. No tuning or comparison was performed.
- README, sequential config example, implementation report, and parent `memory.md` are updated. `.knowledge/` curation and final plan checklist remain.

## Errors encountered and resolutions

| Error | Resolution |
|---|---|
| E04 self-check import cycle through `run_half_boundaries` | Moved opening-kickoff detector import into the sequential runtime branch. |
| First full suite still observed the pre-fix module import cycle | Reran the suite after the fix; all 345 tests passed. |
| First sequential full run exited after inference because sequential mode did not populate legacy graded-half bookkeeping | Populate `seen_halves` from the validated official half mask; candidate then wrote and validated. |

## Remaining gates

- `architect-knowledge` updated `.knowledge/index.md`, created the sequential architecture topic, and updated the current-state fresh-session handoff. The topic records graph query terms, communities, nodes, source locations, and the graph's missing new-module limitation. I reviewed those files and confirmed they contain only architecture, provenance, aggregate checks, and the public single-candidate caveat.
- All acceptance gates are checked in `task_plan.md`; final `git diff --check` and branch/status review passed. Work remains uncommitted in the existing branch, and no restricted outputs are tracked.
