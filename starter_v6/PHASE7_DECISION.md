# Phase 7 candidate decision

Date: 2026-10-30
Selected release ref: `e04-v2-g7-selected`
Selected commit: `11b562d028ee6ea7cee65f90bca6c2c2aea77275`
Frozen fallback: `e04-c7-frozen^{}` → `7aa2f1b44b9db015a89d61fef797ebe83b4dadd2`

## Evidence boundary

No admissible labeled other-game possession dataset was found in the repository
or local project inventory. No licensing, label-semantics, or held-out split was
available to support an independent F1 comparison. The public five-minute
ground truth was not used for tuning, ranking, candidate selection, or stopping.
Consequently, this decision makes no possession-accuracy or competition-score
claim.

The decision is based only on permissible engineering evidence: synthetic
counterfactual tests, explicit R01–R15 behavior contracts, import isolation,
source provenance, deterministic generation, official format validation, and
failure analysis. Unlabeled state counts and spell distributions were used only
as sanity diagnostics, never as a selection objective.

## Candidate scoreboard

| Candidate | Source ref | Config | Local artifact | Verification | Decision status |
|---|---|---|---|---|---|
| E04_C7 frozen | `e04-c7-frozen^{}` → `7aa2f1b` | frozen E04 config | preserved local CSV; hash recorded in Phase 0 manifest | frozen validator/runbook and deterministic prior runs | fallback |
| v2 Phase 6 | `11b562d` | `starter_v6/config.example.json` | preserved local CSV; hash recorded in Phase 7 local report | 120 synthetic tests, self-check, resource check, validator, three matching runs | selected |

The detailed local-only artifact manifest, output hashes, runtime metadata and
validator logs are in `.local-checkpoints/phase7/PHASE7_REPORT.md`. Restricted
inputs, full CSVs and input fingerprints remain local and are not included here.

## Selection rationale

Select v2 as the engineering release candidate because it satisfies the Phase 6
semantic and reproducibility gates while making `starter_v6/` self-contained and
exposing the dead/live and H/A evidence boundary directly to the unchanged
three-state HMM. Synthetic tests exercise conflict preservation, H→D→H spell
boundaries, H→A recovery, uninformative halves, duration characterization and
the prior R01–R15 fixture catalog. The choice is not an accuracy claim.

Keep E04_C7 as the explicit rollback candidate because no independent labeled
evaluation exists. Restore it with `git switch --detach e04-c7-frozen` and use
the Phase 0 runbook/artifact manifest. Do not tune either candidate against the
public five-minute slice.

## R01–R15 status

- R01–R02: implemented as quality-aware boundary candidates and confirmation;
  boundary thresholds are provisional sensor heuristics, not football-law
  measurements.
- R03, R07–R09, R12: supporting motion, missingness and conflict evidence only;
  none is sufficient by itself to create D.
- R04–R06 and R11: restart, goal, foul/offside and live-return context are
  represented with cue-family confirmation and restart-action separation.
- R10: goalkeeper-like live control remains live unless independent stop/restart
  context supports D.
- R13–R14: halves decode independently; halftime/ungraded spans and restart
  boundaries are handled by the pipeline rather than match-specific frame fixes.
- R15: optional 38-frame and 50-frame micro-D hypotheses are characterized;
  default is `off`, and hard structural evidence is exempt.

The owner-authored R01–R15 list is not exhaustive. Any new rule requires an
independent synthetic fixture, lawful evaluation evidence where available, and a
separate change record; ad hoc same-match corrections are prohibited.

## Reproduction

From `more-than-a-hack-2027/`:

```text
.venv/bin/python -m unittest discover -s starter_v6/tests -p 'test*.py'
.venv/bin/python -m starter_v6.run_e04 --self-check
.venv/bin/python -m starter_v6.run_e04 --config starter_v6/config.example.json \
  --checkpoint-root .local-checkpoints/phase7/reproduce_v2 \
  --output .local-checkpoints/phase7/reproduce_v2/e04_v2.csv \
  --diagnostics .local-checkpoints/phase7/reproduce_v2/e04_v2_diagnostics.json \
  --metadata .local-checkpoints/phase7/reproduce_v2/e04_v2_metadata.json
.venv/bin/python evaluation/validate_submission.py \
  .local-checkpoints/phase7/reproduce_v2/e04_v2.csv
```

Phase 8 remains responsible for final freeze, clean-checkout reproduction and
submission-specific checks.
