# Solution 01 E01 — Missing-aware possession baseline

`starter_v3/` is a new fork of the organizer's `starter/`. The organizer copy remains unchanged.
The fork reuses the starter loaders and adds the inspected strict ATD ingestion implementation
from `starter_v2/`, plus a missing-aware E01 inference pipeline. The prior `starter_v2/` work is
left in place as the synthetic foundation.

## E01 behavior

- Each frame records ball-observed/missing separately from H/A/unknown team evidence.
- With a valid ball, nearest distances are computed by team. The observation is unknown when the
  ball is outside the control radius, team separation is too small, or confidence falls below the
  configured threshold.
- Clear possession changes require three consecutive confident observations by default. Brief
  missing-ball gaps carry the current team for at most 25 frames; longer gaps become `X`. Uncertain
  valid-ball observations have a separate 12-frame carry bound.
- Dead-ball evidence is independent of missingness. Ball positions clearly beyond the pitch
  boundary are strong evidence. A relevant `SET PIECES` Smart Tag window plus a stationary ball,
  or a stationary ball plus broad low tracked-player motion, is weak evidence and needs consecutive
  confirmation. Missing ball, a restart tag by itself, and a team tag by itself never force `D`.
- Smart Tag intervals are approximate windows around restarts, not possession intervals. `N/A`
  team tags remain unused as owner assignments. ATD track slots are used only for their metadata
  team mapping, not treated as stable player identities.
- Temporal state resets outside the official graded half blocks and at the boundary between halves.
  Ungraded output frames are `X`.

All settings live in `config.example.json`. They are initial conservative engineering defaults,
not values calibrated against public ground truth. The candidate has not been shown to improve
on the organizer baseline. E02 feature expansion and E04 HMM/Viterbi decoding are not implemented;
E03's general Smart Tag integration is also out of scope, beyond the weak restart context needed
for E01 dead-ball evidence.

## Commands

Run from the `more-than-a-hack-2027/` repository root:

```bash
.venv/bin/python -m starter_v3.run_e01 --help
.venv/bin/python -m starter_v3.run_e01 --self-check
.venv/bin/python -m unittest discover -s starter_v3/tests -p 'test_*.py'
.venv/bin/python -m starter_v3.run_e01 --config starter_v3/config.example.json
.venv/bin/python evaluation/validate_submission.py .local-checkpoints/phase5/e01_submission.csv
```

The self-check and test suite use generated synthetic evidence and require no competition data.
The full command reads only the local tactical ATD and Smart Tagging assets; it never downloads or
substitutes inputs. Use `MTAH_DATA_DIR` or `--data-dir` to point to the authorized bundle root.
Absent files produce a clear error. Candidate CSV, aggregate diagnostics, and run metadata are
written only below ignored `.local-checkpoints/phase5/`.

The diagnostics report distinguishes input observations, model inferences, and evidence-consistency
checks. It does not accept ground-truth labels or compute accuracy. Predicted spell counts and
durations describe output only. Do not use public ground truth to tune thresholds or select this
approach; it may be used only for alignment/pipeline verification.

## Reproducibility and limitations

The run writes a deterministic CSV plus local metadata containing Python version, repository
revision, input identifiers, configuration/source hashes, output SHA256, and runtime. The code hash
captures local source contents, including uncommitted work. Running twice with the same inputs,
code, and configuration should yield the same CSV hash.

The proximity and speed rules are intentionally simple. No image model or learned model is used.
Automatic tracking and tagging errors remain, low-confidence evidence can produce `X`, and the
dead-ball detector may miss stoppages without a reliable cue. Synthetic test success and output
statistics do not establish match accuracy or superiority.
