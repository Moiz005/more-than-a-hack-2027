# Barcelona–Athletic Club possession inference

Release: `e04-v2-g7-selected`  
Implementation commit: `11b562d028ee6ea7cee65f90bca6c2c2aea77275`  
Frozen fallback: `e04-c7-frozen^{}` → `7aa2f1b44b9db015a89d61fef797ebe83b4dadd2`

## Approach

The selected candidate is a self-contained `starter_v6` pipeline with two
evidence channels. The play-state channel observes dead-ball and live-play cues
with source provenance, cue-family confirmation, restart boundaries and
observation-quality flags. The live-team channel estimates H/A ownership from
tracking geometry, motion and quality-aware missing-ball recovery. Missing ball
observations remain missingness; they do not automatically become D or an
opposing-team turnover.

The channels meet at `fuse_evidence()`. H/A values are ownership-conditional
live potentials, `live` represents neutral live mass when ownership is unknown,
and `dead` represents play-state evidence. Fusion validates finite nonnegative
inputs and normalizes H/A/D emissions. These values are evidence potentials, not
calibrated probabilities. The final decoder is the existing three-state,
log-space HMM/Viterbi implementation, run independently for the two graded
halves with unchanged transition defaults.

## Assets and labels

The runtime consumes the supplied tactical tracking/ATD, homography and Smart
Tagging inputs through the repository loaders. No labeled other-game dataset was
available, and no training or hand-authored same-match labels were used. The
public five-minute ground truth was not used for tuning, model selection or
stopping decisions. Full-match target labels were unavailable and no full-match
accuracy claim is made.

## Possession and restart rules

The implementation distinguishes observed ball visibility, play state and live
ownership. Boundary and restart cues can establish D only through their tested
confirmation logic. Set-piece tags provide context rather than forcing an
entire tag interval to D. Restart actions mark the live-return boundary; a team
being associated with a restart does not create live possession before the
restart. Goal, foul/offside, goalkeeper-live-control, halftime and short
micro-stoppage cases are represented in synthetic fixtures. Optional 38-frame
and 50-frame micro-D hypotheses are characterized; the default is off and hard
structural evidence is exempt.

## Verification and limitations

The release passed 120 public-code/synthetic tests, HMM arithmetic checks,
self-checks and the synthetic full-length resource check. Three independent
199,319-row local runs passed `evaluation/validate_submission.py` and produced
identical CSV SHA256 values. These checks establish reproducibility and output
format correctness, not possession accuracy or improvement over E04_C7.

Known limitations include noisy tracking and automatically inferred tags,
uncalibrated evidence magnitudes, transition-prior sensitivity to very short
opposing spells, and the absence of independent labeled evaluation. The
owner-authored R01–R15 list is not exhaustive; future rules require independent
synthetic tests, lawful evaluation evidence where available and a separate
change record. Same-match hand fixes are prohibited.

## Reproduction

From the repository root, with authorized input assets available locally:

```bash
.venv/bin/python -m unittest discover -s starter_v6/tests -p 'test*.py'
.venv/bin/python -m starter_v6.run_e04 --self-check
.venv/bin/python -m starter_v6.run_e04 \
  --config starter_v6/config.example.json \
  --data-dir <authorized-data-directory> \
  --checkpoint-root .local-checkpoints/phase8/final_v2 \
  --output .local-checkpoints/phase8/final_v2/<team_name>.csv \
  --diagnostics .local-checkpoints/phase8/final_v2/diagnostics.json \
  --metadata .local-checkpoints/phase8/final_v2/metadata.json
.venv/bin/python evaluation/validate_submission.py \
  .local-checkpoints/phase8/final_v2/<team_name>.csv
```

The exact selected source/config/artifact hashes, clean-checkout evidence and
validator logs are preserved in the local-only Phase 8 release manifest. The
CSV and local input bundle must not be committed to the public repository.
