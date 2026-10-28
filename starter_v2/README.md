# Solution 01 foundation (`starter_v2/`)

This directory began as a copy of the organizer's `starter/`. The original stays unchanged. The
foundation added here provides input checks and a synthetic smoke path; **no possession inference
algorithm has been implemented**.

## Runtime and commands

The organizer repository documents Python 3.8+ for its evaluation tools, with Python 3.8 and 3.11
tested. This workspace uses Python 3.11.16 in the ignored repository-local `.venv`. Create and
activate it with:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --no-deps -e .
```

No new dependencies were approved or added. `requirements.txt` has unpinned NumPy and pandas;
`requirements-starter.txt` pins kloppy 3.18.0 and leaves matplotlib and notebook unpinned. No
requirements were installed or changed. The foundation CLI and its tests use only the Python
standard library.

Run from `more-than-a-hack-2027/`:

```bash
python starter_v2/solution01.py --self-check
python -m unittest discover -s starter_v2/tests -p 'test_*.py'
python starter_v2/solution01.py --check-inputs
```

An optional JSON config can be passed with `--config starter_v2/config.example.json`. Supported
keys are `source`, `data_dir`, and `seed`; unknown keys are rejected. For source and seed, explicit
CLI values override the config, which overrides defaults. For the data root, precedence is
`--data-dir`, `MTAH_DATA_DIR`, config `data_dir`, then repository `data/`. Relative config paths
are interpreted from the current working directory.

`--check-inputs` checks local asset presence only. It never downloads data, substitutes another
source, or reads the contents. The default root is `data/`; `MTAH_DATA_DIR` can point to a
different bundle root, and `--data-dir` overrides it for one invocation. The expected structure is
`<root>/tactical/` or `<root>/broadcast/` with the filenames returned by `games.asset_paths()`.

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
