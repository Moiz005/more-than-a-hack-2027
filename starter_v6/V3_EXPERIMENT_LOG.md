# v3 experiment tracking

Copy this template for future experiments; do not populate results before execution.

- Experiment ID / objective:
- Starting Git commit / ending Git commit:
- Configuration path / SHA256 / effective configuration:
- Executed source manifest / SHA256 / dependency manifest:
- Files changed:
- Test commands / actual passed / failed / skipped / expected failures:
- Expected versus actual synthetic behavior:
- Enabled/disabled causal comparison:
- HMM arithmetic / import isolation:
- Local aggregate diagnostics (no reconstructive outputs):
- Official validator command / result / row count:
- Output path / SHA256 / repeat SHA256:
- Lawful held-out other-game metrics (or not run):
- Known regressions / limitations:
- Rollback command:
- Gate decision: GO / NO-GO / BLOCKED / SKIPPED

## Phase 0 preservation record

Baseline: `d24d5ae7b02488807ab7167494496c93152bbafa`, annotated tag
`e04-v3-phase0-persistence-baseline` (entire repository tree).
The baseline has 148 passing tests. The two added characterization tests preserve
`DDDHHDDDD` and explicitly mark desired `DDDHHHHHH` as an expected failure.
No production code or configuration is changed in Phase 0.

Local evidence directory: `.local-checkpoints/v3/phase0/d24d5ae_verified/`.
It contains a complete-history Git bundle, copied configuration, historical run
metadata, new independent run metadata/CSVs, private input fingerprints, logs,
and a baseline runbook. Keep these artifacts local and ignored.

Restore the exact baseline entire tree (after saving any current work):
`git switch --detach e04-v3-phase0-persistence-baseline`.
If the repository is lost, `git clone <local-baseline.bundle> <new-directory>`
then detach at that tag. Licensed inputs and the Python environment are separate.

Known cause: runtime adapter consumption is internal to
`RuntimeRestartActionDetector`; only a one-frame action reaches the observer.
Later stationary frames under the same context generate `restart_stationary`,
confirm on the next frame, and produce D again. Persistence does not cause this:
the defect reproduces without missing observations. Phase 1 should distinguish
consumed old context from genuinely new independent stoppage evidence.
