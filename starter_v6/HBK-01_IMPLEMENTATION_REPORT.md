# HBK-01 implementation report

Date: 2026-11-05
Canonical implementation: `starter_v6/`
Branch: `experiment/e04-v3-visual-possession`
Verified source commit: `03c9245cc45edfc25561d5a7cf9f14b19e622584`
Parent runner: `starter_v6.run_e04`

## Decision

**GO for the isolated engineering experiment. NO-GO for promoting an overlay
submission or claiming a leaderboard improvement.**

HBK-01 is synthetic-tested, tactical-only, opt-in, deterministic, locally
provenanced, and fail-closed. The supplied tactical run did not provide enough
ATD evidence to confirm either opening kickoff, so the overlay correctly
produced no candidate CSV. Real boundary precision, event recall, private
`spellF1`, and private `macroF1` remain **UNKNOWN**.

The existing E04 output remains the immediate submission fallback. Enabling an
overlay requires a future run with a confirmed second-half kickoff and the same
policy/invariant checks; no fixed frame or manually observed timestamp is an
acceptable substitute.

The audit-estimate extension may report a strongest movement frame inside the
Smart Tag interval for manual inspection. This estimate is explicitly not an
exact execution confirmation and cannot modify labels.

## Ablation and local run evidence

All rows below are engineering facts from ignored local artifacts. They are not
accuracy measurements.

| Candidate | Status | Output SHA-256 | Changed frames | Tested invariants / result |
|---|---|---|---:|---|
| E04 original | `COMPLETE` | `d1604474717565a460d30bdef271d4e6e9b6c088c00bec84f6ef3d97a35f74ae` | 0 vs. itself | 199,319 ordered rows; tactical mask checks passed |
| HBK-01 off | `COMPLETE` | `d1604474717565a460d30bdef271d4e6e9b6c088c00bec84f6ef3d97a35f74ae` | 0 vs. E04 | Byte-identical to clean E04 baseline; official validator passed |
| HBK-01 audit | `AUDIT_ONLY / REJECTED` | none | 0 | 638 Smart Tag records retained; one eligible opening candidate per half; both detectors `INSUFFICIENT_EVIDENCE`; all policy preservation assertions true |
| HBK-01 overlay | `NO-GO / REJECTED` | none | 0 | Exit code `2`; reason `second_half_status_INSUFFICIENT_EVIDENCE`; no submission file written |

### Local commands and results

Commands used the required project environment:

```text
/Users/moiz/Desktop/Metrica-Sports-Hackathon/more-than-a-hack-2027/.venv/bin/python -m unittest discover -s starter_v6/tests -p 'test_*.py'
331 passed, run twice

/Users/moiz/Desktop/Metrica-Sports-Hackathon/more-than-a-hack-2027/.venv/bin/python -m starter_v6.run_e04 --self-check
synthetic E04 self-check passed

/Users/moiz/Desktop/Metrica-Sports-Hackathon/more-than-a-hack-2027/.venv/bin/python -m starter_v6.run_half_boundaries --self-check
HBK-01 self-check passed

/Users/moiz/Desktop/Metrica-Sports-Hackathon/more-than-a-hack-2027/.venv/bin/python evaluation/validate_submission.py .local-checkpoints/hbk01/p7-hbk-off/submission.csv
OK; 199319 rows, frame 0..199318
```

The validator reported H=85,579, A=64,452, D=8,826, X=40,462 and 307
reported possessions. These are format/description facts only; they are not
ground-truth scores.

The real tactical audit and overlay used these run IDs:

- `.local-checkpoints/hbk01/p7-audit-20261105/`
- `.local-checkpoints/hbk01/p7-overlay-20261105/`

The off run used `.local-checkpoints/hbk01/p7-hbk-off/`; the clean parent
baseline used `.local-checkpoints/hbk01/p7-parent-baseline/`. These paths are
ignored and must remain local.

## Contract and source-isolation review

- Input source was tactical ATD, tactical Smart Tagging, and the tactical
  reference timeline only. No broadcast input or external event call was used.
- The real audit confirmed tactical source, 25 FPS, 199,319 frames, 638 Smart
  Tag events, one eligible opening kickoff candidate per half, and no confirmed
  `k1` or `k2` timestamp.
- Pre-match, halftime, and post-match regions remained `X`; graded regions had
  no `X`; first/last graded frames were preserved.
- `off` changed no bytes or labels. `audit` changed no labels. `overlay` wrote
  no output after unconfirmed detection.
- No target-match hand labels, public five-minute ground truth, threshold
  selection, frame-specific constants, or post-hoc CSV edits were used.
- `starter/`, `evaluation/`, `games.py`, and the existing E04 parent runner and
  config were not modified by Phase 8.
- Local diagnostics, raw assets, generated CSVs, and provenance remain under
  ignored paths and are not part of the commit.

## Known limitations and unknowns

- Smart Tagging supplies a contextual interval, not the legal kick frame; tag
  endpoints are never treated as execution.
- ATD ball missingness and invalid provider speeds can prevent confirmation. The
  local aggregate scan reported 59.35%/59.27% ball visibility in the two
  graded halves and 85,831 missing ball-position observations overall.
- Player-slot identity and player movement are not independent proof of a kick.
- Homography is validated as an aligned input but is not an independent motion
  observation and is not used to confirm kickoff execution.
- No referee whistle labels or independently labeled other-match boundary set
  were available for admissible evaluation.
- Parent H/A inference after a confirmed kickoff is intentionally unchanged.
- A false-positive D prefix could erase genuine early-second-half possession and
  fragment a spell; a false negative leaves the boundary uncorrected. The
  detector therefore abstains when evidence is insufficient.

## Reproduction and fallback

Run from the repository root with a unique run ID and local ignored checkpoint
root:

```bash
PY=/Users/moiz/Desktop/Metrica-Sports-Hackathon/more-than-a-hack-2027/.venv/bin/python
$PY -m starter_v6.run_half_boundaries \
  --config starter_v6/config.hbk01.example.json \
  --mode audit --run-id audit-<unique> \
  --checkpoint-root .local-checkpoints/hbk01
```

The immediate fallback is the existing E04 CLI:

```bash
$PY -m starter_v6.run_e04 \
  --config starter_v6/config.example.json \
  --output .local-checkpoints/fallback/submission.csv \
  --diagnostics .local-checkpoints/fallback/diagnostics.json \
  --metadata .local-checkpoints/fallback/metadata.json \
  --checkpoint-root .local-checkpoints/fallback
```

This report does not authorize public submission, external upload, threshold
tuning, or a future overlay. Any future change must preserve `starter_v6` as
the canonical directory and rerun the synthetic, regression, provenance,
validator, and fail-closed checks.

## Evidence-recovery extension

The post-release evidence-recovery work remains fail-closed and tactical-only.
It adds aggregate diagnostics for ball visibility, center-circle setup,
nearby-player support, player motion, contiguous motion, and short missing-ball
gaps. A gap can produce `BOUNDED_INTERVAL`, but that status is deliberately
rejected by the boundary policy; only `CONFIRMED` exact contiguous motion is
overlayable. Synthetic tests cover this distinction and preserve the earlier
missing-ball and player-only negative cases. No target-match frame labels or
public evaluation score were used to select these engineering hypotheses.

The audit-estimate pass adds a separate `ESTIMATED_FRAME` result when
persistent plausible ball motion is observed inside the Smart Tag interval but
strict setup evidence is insufficient. The tactical-only audit produced local
manual-check estimates of `00:07:27.5` (first half, frame 11188) and
`01:15:46.4` (second half, frame 113660). Both remain audit-only; the policy
reported zero label changes and did not write an overlay submission.

The all-kickoffs tactical audit also covered four eligible post-goal kickoff
tags. Across six eligible events (two opening, four post-goal), five returned
`ESTIMATED_FRAME` and one returned `INSUFFICIENT_EVIDENCE`. No post-goal result
changed labels; only opening results were passed to the boundary policy.
The final audit artifact is `.local-checkpoints/hbk01/hbk01-all-kickoffs-final-20261105/`.
