# Solution 01 foundation (`starter_v2/`)

This directory began as a copy of the organizer's `starter/`. The original stays unchanged. The
foundation includes input checks, aligned ingestion, and a deterministic E01 possession state
machine exercised on synthetic scenarios. E01 is an initial rule-based implementation, not a
validated competition submission; E02–E04 are not implemented.

## Runtime and commands

The organizer repository documents Python 3.8+ for its evaluation tools, with Python 3.8 and 3.11
tested. This workspace uses Python 3.11.16 in the ignored repository-local `.venv`. Create and
activate it with:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --no-deps -e .
```

No dependency files were added or changed. `requirements.txt` declares unpinned NumPy and pandas;
with user approval these existing requirements were installed into `.venv` for baseline validation
and scoring. `requirements-starter.txt` pins kloppy 3.18.0 and leaves matplotlib and notebook
unpinned. The foundation CLI and synthetic inference/diagnostics tests use only the Python standard
library.

Run from `more-than-a-hack-2027/`:

```bash
python starter_v2/solution01.py --self-check
python -m unittest discover -s starter_v2/tests -p 'test_*.py'
python starter_v2/solution01.py --check-inputs
```

## Synthetic possession harness (Phase 4)

The semantic tests create coordinates and events in test code; they are independent of the licensed
match and public labels. `starter_v2/possession.py` provides a small E01 state machine with
confirmed control acquisition, explicit dead-ball evidence, bounded missing/uncertain carry, and
half resets. It is intentionally a simple synthetic test subject, not an experimentally validated
possession model. Restart markers alone do not assign a possessing team.

Run all synthetic and ingestion tests from the repository root:

```bash
.venv/bin/python -m unittest discover -s starter_v2/tests -p 'test_*.py'
.venv/bin/python starter_v2/solution01.py --self-check
```

The possession tests cover a controlled H pass despite a brief nearest-player switch, confirmed
turnover, H-D-H spell splitting, missing-ball gaps, long uncertainty, restarts, half resets, CSV
alignment/label errors, and normalized H/A/D emissions. Emissions must be finite probabilities in
`[0,1]` whose rows sum to 1. Unnormalized scores are not accepted by this API.

Expected sequences are asserted directly in `tests/test_possession.py`:

| Synthetic scenario | Expected labels |
|---|---|
| Controlled H pass, one brief nearest-A observation | `X H H H H H` |
| H-to-A turnover after two consecutive controlled-A frames | `X H H H H A A` |
| H possession, explicit dead ball, H restart/control | `X H D X H` |
| Short missing-ball gap during H | `X H H H H` |
| Long missing-ball gap, then sustained A control | `X H H H X X X A` |
| Half change from H to A | `X H X A` |
| Restart marker alone followed by A control | `D X X A` |

These are contract examples produced from generated coordinates/events, not competition observations.

`starter_v2/diagnostics.py` prints aggregate-only diagnostics for predictions and aligned evidence.
Its JSON input contains `labels`, `ball_observed`, `confidence`, `evidence_team`, and
`runtime_seconds`; ground-truth fields are rejected. Output separates `observations`, `inferences`,
evidence/prediction `consistency_checks`, and `ground_truth` provenance (`used: false`; no
accuracy/score computed). Predicted spell counts, shares, and durations describe model output only
and do not indicate accuracy. The generic report shape is in
`starter_v2/fixtures/diagnostics_report_template.json`. Example invocation:

```bash
.venv/bin/python -m starter_v2.diagnostics path/to/local_diagnostics.json
```

Diagnostics include possession count and duration summaries, H/A/D/X shares, state transitions,
missing-ball overlap, high-confidence prediction/evidence contradictions, and supplied inference
runtime. Keep match-derived inputs, reports, and plots under ignored local storage. Share only
generic synthetic examples; never attach restricted rows, clips, or reconstructive diagnostics.

Every future versioned starter must pass the synthetic suite and its own smoke check before its
entry point (`--help` and synthetic self-check), config-loading test, minimal tests, and documented
commands are verified before its `memory.md` status is changed to “ready to run.” Do not add absent
version directories as completed entries. `starter_v2` is currently recorded as not submission-ready.

An optional JSON config can be passed with `--config starter_v2/config.example.json`. Supported
keys are `source`, `data_dir`, and `seed`; unknown keys are rejected. For source and seed, explicit
CLI values override the config, which overrides defaults. For the data root, precedence is
`--data-dir`, `MTAH_DATA_DIR`, config `data_dir`, then repository `data/`. Relative config paths
are interpreted from the current working directory.

`--check-inputs` checks local asset presence only. It never downloads data, substitutes another
source, or reads the contents. The default root is `data/`; `MTAH_DATA_DIR` can point to a
different bundle root, and `--data-dir` overrides it for one invocation. The expected structure is
`<root>/tactical/` or `<root>/broadcast/` with the filenames returned by `games.asset_paths()`.

## Phase 2 ingestion

`ingestion.py` reuses `games.py` for asset paths, source frame counts, pitch dimensions and graded
half blocks. It parses metadata with the standard library, streams ATD frames with strict one-based
ID checks, and can materialize compact arrays with normalized XY coordinates, metric XY coordinates,
speed values, and separate position/speed validity masks. Missing coordinates remain NaN. Declared
pitch dimensions are captured when the ATD metadata exposes them; metric scaling uses the
`games.py` pitch dimensions (105.3 m × 68.0 m), while normalized values are retained.
The 46 tactical and 51 broadcast metadata entries are track slots, not stable player identities;
array columns index those source-specific slots only.

Smart Tagging intervals use the organizer loader's `round(seconds * fps)` convention, uppercase
event codes, normalize the named sides to `H`/`A`, and preserve explicit `N/A` team tags. The
homography reader validates the 3×3 field set, frame sequence, validity flag and documented
normalized-pitch-to-pixel direction. Graded frame ranges come directly from `games.half_video_blocks`;
ungraded frames are reported separately so later temporal inference can reset at half boundaries.
`half_index_by_video_frame()` exposes a compact mask with 0 for ungraded frames and 1/2 for the
graded halves.

Run from the repository root:

```bash
python -m starter_v2.ingestion
```

This hashes all nine expected tactical and broadcast assets, then streams tactical ATD, Smart
Tagging, and homography to build aggregate quality metrics. The two JSON files go to ignored
`.local-checkpoints/`. Hashing the two videos can take a while. Use `--inventory-only` to inventory
and hash the bundle without parsing observations, or `--quality-only` to regenerate only the
tactical aggregate report. Standard output contains summary counts only; no rows or per-frame
extracts are written.

## Reproducibility and outputs

`provenance.py` provides deterministic Python/NumPy seed setup, streamed SHA256, and stable JSON
metadata containing runtime versions and logical input identifiers. Hashes are opt-in and the
helper has not been run against licensed assets. Do not put absolute paths, per-frame values, or
restricted extracts in metadata. Generated prediction files, clips, and restricted diagnostics
belong in ignored local output paths.

## Local-only data handling

- Keep all licensed videos, tracking, tags, homographies, and derived extracts on the local machine
  under the ignored `data/` tree.
- Do not attach those assets to chat, prompts, hosted coding assistants, issue trackers, or other
  cloud tools. Do not paste rows, frame crops, tracking excerpts, or reconstructive diagnostics.
- Run any future asset-reading scripts locally. If a developer tool would transmit file contents
  or telemetry that could contain them, do not use it for this project; share only public code,
  public documentation, synthetic fixtures, schemas, and aggregate non-reconstructive findings.
- Never commit assets or derived extracts. `.gitignore` excludes the data tree, videos, predictions,
  clips, restricted diagnostics, and common local secret files.

## Version and phase workflow

To start another approach, inspect `memory.md`, create a new directory directly under the repository
root (for example `starter_v3/`), copy only the chosen parent starter, and record the new directory,
parent, algorithm, differences, and actual status in `memory.md`. Do not create E01–E04 directories
until their corresponding steps are implemented. Keep `starter/` and `evaluation/` unchanged.

For each phase report, record: prompt scope; files edited; tests actually run and their result;
runtime/configuration and any hashes actually generated; the `memory.md` update; and a GO/NO-GO
decision with unresolved blockers. Never mark checklist items complete based only on intent.

## Codex task template and approval boundaries

Start each implementation request with this compact template:

```text
Goal / phase:
Scope and excluded work:
Allowed inputs and files:
Competition-rule constraints:
Dependency or architecture changes requested:
Acceptance checks:
Required report and checkpoint gate:
```

Follow root `AGENTS.md`: obtain user approval before adding dependencies, destructive changes,
schema changes, significant refactors, or external actions. Stop and flag uncertain competition
rules before implementing. Never pass licensed data, extracts, secrets, or reconstructive
diagnostics to hosted assistants or external tools. Keep all asset processing local.
