# E04 — Three-state HMM and Viterbi decoding

`starter_v6/` is forked from the E03 implementation in `starter_v5/`. E04 reads the same per-frame H/A/D evidence emissions produced by E03 and applies offline Viterbi decoding to each official graded half independently. The organizer `starter/`, `evaluation/`, and E01–E03 version directories are separate and remain unchanged.

## Model contract

The hidden states are `H` (home possession), `A` (away possession), and `D` (dead ball). E03 emissions are normalized evidence potentials, not calibrated probabilities. Viterbi combines their log values with configurable initial and transition probabilities. The decoder uses fixed `H`, `A`, `D` tie order, a positive emission floor, an emission weight, and a temperature; all are set in `config.example.json` and validated by the strict config loader.

Transition matrix rows and columns are ordered `H`, `A`, `D`. The defaults favor state continuation, allow direct H/A turnovers, and allow transitions into and out of D. They are explicit modeling assumptions, not values fitted to public labels. Any future change should be recorded as a distinct configuration and evaluated without tuning on the public five-minute labels.

Each half is decoded independently. Ungraded frames are emitted as `X`; they do not carry hidden state across gaps or halftime. Spell extraction uses half-open frame intervals `[start, end)`, terminates at `X`, and separates adjacent states and halftime boundaries. Missing-ball frames remain E03 evidence states; absence alone is not converted to D.

The output is a full-timeline CSV with the official `frame,label` header. Diagnostics report graded/ungraded counts, state shares, intervals, duration min/median/p90/max and histograms, transitions, missing-ball overlap, emission-argmax agreement, changes against the E03 output, and runtime. They describe model behavior only; they are not ground-truth accuracy or evidence that E04 is superior. No public score is used for model selection.

## Run and verify

Run from `more-than-a-hack-2027/` using the existing project environment and authorized local data:

```bash
.venv/bin/python -m unittest discover -s starter_v6/tests -p 'test_*.py'
.venv/bin/python -m unittest discover -s starter_v5/tests -p 'test_*.py'
.venv/bin/python -m starter_v6.run_e04 --help
.venv/bin/python -m starter_v6.run_e04 --self-check
.venv/bin/python -m starter_v6.run_e04 --synthetic-resource-check
.venv/bin/python -m starter_v6.run_e04 --config starter_v6/config.example.json \
  --output .local-checkpoints/phase8/e04_run1.csv \
  --diagnostics .local-checkpoints/phase8/e04_run1_diagnostics.json \
  --metadata .local-checkpoints/phase8/e04_run1_metadata.json
.venv/bin/python evaluation/validate_submission.py .local-checkpoints/phase8/e04_run1.csv
```

Repeat with distinct `run2` output paths to verify byte-identical generation. Inputs must already be available locally under the configured data directory; the runner does not download or substitute assets. Candidate CSVs, diagnostics, and metadata are restricted local artifacts and must remain under the ignored `.local-checkpoints/phase8/` directory.

Metadata contains source/config/input SHA256 fingerprints, Git revision and dirty-state indicator, Python/platform identifiers, output hash, runtime, and peak process memory. Input hashes and metadata are local provenance aids only; do not publish them. No raw data, per-frame emissions, backpointers, coordinates, or frame-level differences are written to diagnostics.

## Limitations and status

The E04 synthetic tests verify decoder arithmetic, interval semantics, and edge handling. Full-match reproducibility verifies a deterministic, structurally valid candidate. Neither establishes possession accuracy or improvement over E01–E03 or the organizer baseline. Smart Tagging remains weak input evidence through the E03 parent. Transition probabilities are assumptions and no independent full-match possession labels are available for accuracy assessment.
