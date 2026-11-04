# TacticalFusion Phase 6 — Stage 1 lifecycle

**Status:** Engineering implementation complete; synthetic gate only.  
**Scope:** Tactical ATD and tactical Smart Tagging. No audio, broadcast, homography, or restricted match data was used in this phase's contract tests.  
**Default:** `features.stage1_lifecycle_enabled=false`; existing V3/E04 behavior remains the default.

## Implementation

- Added typed internal `PlayStateHypothesis` states: `STOP_ONSET`, `DEAD_PERSISTENCE`, `RESTART_PREPARATION`, `LEGAL_RESTART_EXECUTION`, `LIVE_RECOVERED`, and `UNKNOWN`. These are diagnostic hypotheses; CSV output remains H/A/D/X.
- Added a normalized, deduplicated per-frame timeline of supported restart types. Duplicate events of the same type collapse; overlapping conflicting types remain explicit and cannot produce an action.
- For corner, goal, free, and kickoff restarts, execution requires observed stationary setup followed by credible displacement and speed. Throw-in execution requires an observed outside-to-inside field crossing. Untagged legacy context keeps its existing generic compatibility path.
- In opt-in lifecycle inference, a single outside coordinate is not hard DEAD. Confirmed D persists until a detected legal restart action or enough consecutive reliable live-control observations satisfy the existing acquisition threshold.
- Free Kick context alone is conservatively treated as restart preparation. It cannot distinguish a referee-awarded free kick from advantage. Unsupported onset and restarting-team ownership remain unknown.
- Lifecycle mode is plumbed into the E01/E04 runners only when explicitly enabled. No default preset was changed.

## Verification

Using the project's required virtual environment:

- Focused synthetic lifecycle, catalog, ablation, and restart-action suite: **40 tests passed**.
- Full `starter_v6` suite: **254 passed, 1 skipped**.
- `python -m starter_v6.run_e04 --self-check`: passed.
- `python -m json.tool starter_v6/config.example.json`: passed.
- `git diff --check`: passed.
- Protected baseline worktree: clean at `9fd0277a23258a448e0863b33d646c8540070c50`.

Checkpoint commit is recorded after this report is finalized.

The tests use invented coordinates, players, restart tags, and half identifiers. They establish software contracts only, not match accuracy, spellF1, macroF1, legal referee decisions, or improvement over V3. Public ground truth was not used.

## Limitations

A missing or noisy onset may remain `UNKNOWN`; a throw-in whose outside-to-inside trajectory is unobserved does not get an inferred execution; an untagged stop has no type-specific execution semantics; goal tags alone do not establish exact post-goal onset; Free Kick tags cannot disambiguate advantage; restart-owner evidence is not inferred from Stage 1. Confidence is heuristic and not calibrated. These limitations can miss real stops/restarts and require independent evaluation on permitted labeled data before considering any accuracy claim.
