# Sequential Stage 1 → Stage 2 implementation

Branch: `experiment/e04-v3-visual-possession`
Canonical code: `starter_v6/`
Python: repository `.venv/bin/python`

## Objective

Add opt-in `stage1_then_stage2` inference: resolve LIVE/DEAD, run ownership only on contiguous LIVE segments, decode H/A independently per segment, and merge fixed D and official X. Preserve legacy modes and `exact_v3`.

## Acceptance gates

- [x] Contract objects enforce exclusive Stage 1 DEAD and Stage 2 ownership.
- [x] Sequential runner mode is explicit; legacy modes remain intact.
- [x] Stage 2 receives exactly Stage 1 LIVE frames and resets at D/X/half boundaries.
- [x] H/A decoder cannot emit D.
- [x] HBK kickoff evidence is consumed upstream in sequential mode; unsupported evidence fails closed.
- [x] Synthetic lifecycle and ownership boundary regressions pass.
- [x] Full test suite, self-check, resource check, compile and diff checks pass.
- [x] Candidate is reproducible, validated and received one public pipeline/alignment check only.
- [x] README, aggregate diagnostics, memory, knowledge topic and fresh-session handoff updated.

## Work log

Initial verified state: clean branch at `cff092fd149df5ba5180e0ea6190b137bada2ca0`; Python 3.11.16 from requested `.venv`. No plan existed in the canonical worktree; this plan was created there before implementation.

## Final evidence

- Focused sequential tests: 23 passed. Full `starter_v6` suite after final code changes: 346 passed.
- E04 synthetic self-check, 158,857-frame-equivalent resource check, full-module `py_compile`, and `git diff --check`: passed.
- Sequential CSV: 199,319 rows; H 74,863, A 63,725, D 20,269, X 40,462. SHA-256 `78f1e120f9bc22bf0c8d8992100cf09b20ea7d9fb8e0a8e2b9e5c1eb2597b7a4` matched across three generations.
- Official validator: passed for both sequential and exact fallback outputs.
- Stage 2 processed exactly 138,588 LIVE frames across 52 segments; Stage 1 DEAD 20,269 and UNGRADED 40,462. HBK-01 upstream prefix applied to 2,235 frames.
- `exact_v3` hash reproduced protected release SHA-256 `d1604474717565a460d30bdef271d4e6e9b6c088c00bec84f6ef3d97a35f74ae`.
- One public check: 7,500 graded frames, macroF1 0.6083 and spellF1 0.3636 (1,000 bootstrap draws); only pipeline/alignment evidence, not selection or tuning. Exact metric fields are in `starter_v6/SEQUENTIAL_STAGE1_STAGE2_IMPLEMENTATION_REPORT.md`.
- README, config example, implementation report, aggregate diagnostics, project `memory.md`, `.knowledge` topic/index/fresh-session handoff are complete and reviewed. The architect-knowledge agent wrote only within `.knowledge/`; no frame-level or reconstructive data was included.

## Errors Encountered

| Error | Attempt | Resolution |
|---|---:|---|
| Import cycle from eager `run_half_boundaries` import | 1 | Lazy-import the HBK detector only inside the sequential mode; self-check and full suite pass. |
| First full suite ran before import fix was loaded | 1 | Rerun after the fix; 345 passed, then final suite after added restart guard passed 346. |
| First sequential runner completion failed legacy `seen_halves` assertion after both passes | 1 | Populate graded half set from the validated timeline mask; subsequent full runs passed. |

## Skill Table

| Skill | Use |
|---|---|
| plan-and-build | Phase breakdown and acceptance gates |
| test-driven-development | Add behavioral tests before implementation |
| git-workflow-and-versioning | Preserve branch and narrow changes |
| api-and-interface-design | Define internal stage contracts |
| documentation-and-adrs | Explain architectural behavior |
| knowledge-base-management | Curate final knowledge handoff |
| graphify | Architecture retrieval |
