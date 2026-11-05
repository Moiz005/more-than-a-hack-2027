# Sequential Stage 1 → Stage 2 Implementation Report

## Decision and scope

Added the opt-in `stage1_then_stage2` mode on `experiment/e04-v3-visual-possession` in the canonical `starter_v6/` directory. Existing modes remain available. `exact_v3` still runs the previous inference path and reproduces its protected output hash.

## Architecture

Stage 1 now runs before ownership inference. It receives team-neutral lifecycle input and can resolve only `LIVE`, `DEAD`, or `UNGRADED`; the implementation does not invoke the H/A proposal function in this pass. Confirmed stops persist until a recognized restart action or consecutive live recovery supported by observed ball motion, a nearby player from either team, and acceptable tracking quality. No side is selected during recovery.

The existing HBK-01 opening-kickoff detector and fail-closed boundary policy run before Stage 2. Confirmed, estimated, or frame-resolvable bounded detector evidence can make the supported second-half pre-kickoff prefix DEAD. Ambiguous, missing, frame-less, or out-of-range evidence leaves the prefix unchanged. No match frame is hard-coded.

Stage 2 is invoked separately for each contiguous LIVE segment. Its invocation disables dead-ball detection and lifecycle transitions; restart-action frames are neutral for owner acquisition. It emits H/A ownership evidence only. A two-state H/A Viterbi decoder is initialized per segment using ratios derived from the existing HMM configuration. Composition copies Stage 1 DEAD to `D`, the official ungraded mask to `X`, and fills every LIVE frame from Stage 2. Assertions require Stage 2 coverage to equal exactly the Stage 1 LIVE frame set and reject any Stage 2 DEAD mass.

## Changed files

- `starter_v6/config.py` — adds `stage1_then_stage2` as an opt-in integration mode.
- `starter_v6/inference.py` — adds team-neutral Stage 1 and dead-ball-free LIVE ownership execution paths while leaving default behavior intact.
- `starter_v6/sequential.py` — typed play-state contract, exact LIVE-coverage composition, and independent H/A segment decoder.
- `starter_v6/run_e04.py` — performs two-pass inference, applies HBK-01 upstream, and writes aggregate diagnostics.
- `starter_v6/config.sequential.example.json`, `starter_v6/README.md`, and tests — runnable config, behavior documentation, and regression coverage.
- `.plan/codex/sequential-stage1-stage2/` — task, findings, and progress records.

## Verification

Environment: `more-than-a-hack-2027/.venv/bin/python` (Python 3.11.16). Branch remained `experiment/e04-v3-visual-possession`; no versioned starter directory was created.

- Focused sequential and integration tests: 23 passed.
- Full `starter_v6` suite: 346 passed.
- E04 synthetic self-check: passed.
- Full graded-length synthetic resource check: 158,857 graded-equivalent frames across two independent halves; peak reported memory 31.50 MiB.
- `py_compile starter_v6/*.py`: passed.
- `git diff --check`: passed.
- Three sequential candidate generations produced the same CSV SHA-256: `78f1e120f9bc22bf0c8d8992100cf09b20ea7d9fb8e0a8e2b9e5c1eb2597b7a4`.
- Final sequential run runtime: 150.07 seconds; peak resident memory reported by the runner: 418.58 MiB. The runner buffers one LIVE segment for Stage 2 inference and H/A decoding.
- Sequential candidate official validator: `OK`, 199,319 rows, frame 0 through 199,318. Counts: H 74,863; A 63,725; D 20,269; X 40,462.
- Validator's simple spell report: 294 possessions, mean 18.9 seconds (counts each X as a gap; scorer treatment differs).
- Aggregate pipeline counts: Stage 1 LIVE 138,588; DEAD 20,269; UNGRADED 40,462; Stage 2 frames 138,588; 52 LIVE segments. HBK-01 applied a 2,235-frame second-half prefix. Stage 2 ownership diagnostics recorded 50 reacquisition segments, 2 segments without supported control, and maximum observed acquisition latency of 58 frames. These are internal detector summaries, not accuracy evidence.
- `exact_v3` regeneration passed the official validator and exactly matched the protected release SHA-256 `d1604474717565a460d30bdef271d4e6e9b6c088c00bec84f6ef3d97a35f74ae`.

## One-candidate public pipeline/alignment check

Ran the organizer's `evaluation/run_evaluation.py --gt public` once for the sequential candidate, with 1,000 bootstrap draws. It processed 7,500 graded frames and 21 ground-truth segments. This is compatibility/alignment evidence only; it was not used to tune, compare, rank, or promote the candidate.

- `macroF1`: 0.6083; accuracy 0.7317; kappa 0.5483.
- Class F1: H 0.8127 (precision 0.7352, recall 0.9085); A 0.7651 (0.7084, 0.8316); D 0.2470 (1.0000, 0.1409).
- Macro-F1 bootstrap 5th–95th percentiles: 0.4206–0.7419 (21 segments, 1,000 draws).
- `spellF1`: 0.3636; IoU 0.3/0.4/0.5/0.6/0.7: 0.4848/0.4242/0.4242/0.3636/0.1212.
- Spell-F1 bootstrap 5th–95th percentiles: 0.2061–0.5333 (17 possessions, 1,000 draws).
- At IoU 0.5: precision 0.4375, recall 0.4118, F1 0.4242; 7 matched, 10 missed, 9 spurious.
- Transition F1 at ±25 frames: 0.1667 (precision 0.1875, recall 0.1500; 3 matched, 17 missed, 13 spurious). At ±12 frames: F1 0.1111 (2 matched, 18 missed, 14 spurious).
- Possessions: 16 predicted vs 17 ground truth; mean duration 18.2 s vs 14.2 s. Mean transition latency −5.0 frames; median 0; 90th percentile absolute latency 13 frames.
- Alive/dead F1 0.9053; team accuracy on ground-truth alive frames 0.8756. Home share 0.5727 ground truth / 0.5852 predicted (absolute error 0.0125). Fragmentation 17/21 = 0.81. Abstentions on graded ground-truth frames: 0.
- Confusion matrix (ground-truth rows, prediction columns H/A/D/X): H `[3138, 316, 0, 0]`; A `[434, 2143, 0, 0]`; D `[696, 566, 207, 0]`; X `[70595, 60700, 20062, 40462]`.

The complete evaluator output is retained locally under `.local-checkpoints/sequential/public_eval/`. This score does not establish full-match possession accuracy or improvement; full-match independent labels are unavailable.

## Reproduction commands

```bash
.venv/bin/python -m unittest discover -s starter_v6/tests -p 'test_*.py'
.venv/bin/python -m starter_v6.run_e04 --config starter_v6/config.sequential.example.json --checkpoint-root .local-checkpoints/sequential --overwrite
cd evaluation
../.venv/bin/python validate_submission.py ../.local-checkpoints/sequential/example_submission.csv
../.venv/bin/python run_evaluation.py --gt public --results ../.local-checkpoints/sequential --out ../.local-checkpoints/sequential/public_eval --bootstrap 1000
```
