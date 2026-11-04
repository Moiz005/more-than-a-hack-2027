# TacticalFusion V3 P0 source audit

## Phase and gate

- Phase: P0 — pinned V3 source audit, isolation and baseline safety.
- Gate: G0 PASS for source provenance, approved environment, isolation, and
  synthetic/regression safety checks.
- Audit date: 2026-11-04.
- Protected baseline: `9fd0277a23258a448e0863b33d646c8540070c50`.
- Protected tag: `e04-v3-g8-release`; peeled commit resolves to the protected
  baseline above.
- Research branch/worktree: `experiment/e04-v3-visual-possession` at
  `/Users/moiz/Desktop/Metrica-Sports-Hackathon-visual-possession-v3`.
- Public ground truth: not used for tuning, ranking, selection, or candidate
  comparison.

The baseline checkout at
`/Users/moiz/Desktop/Metrica-Sports-Hackathon/more-than-a-hack-2027` remained
detached, clean, and untouched. The research worktree was created directly
from the full pinned commit; no later experimental branch was copied or
cherry-picked.

## Verification record

Approved interpreter:

```text
/Users/moiz/Desktop/Metrica-Sports-Hackathon/more-than-a-hack-2027/.venv/bin/python
Python 3.11.16
pip check: No broken requirements found.
```

Commands and observed results in the isolated worktree:

| Check | Result |
|---|---|
| `git status --short --branch` | clean research branch; baseline was clean detached before isolation |
| `git rev-parse HEAD` | `9fd0277a23258a448e0863b33d646c8540070c50` |
| `git rev-parse e04-v3-g8-release^{commit}` | same protected commit |
| `python -m unittest discover -s starter_v6/tests -p 'test_*.py'` | 194 passed, 1 skipped |
| `python -m unittest discover -s starter_v5/tests -p 'test_*.py'` | 61 passed, 1 skipped |
| `python -m unittest discover -s starter_v4/tests -p 'test_*.py'` | 45 passed |
| `python -m starter_v6.run_e04 --self-check` | passed |
| `python -m starter_v6.run_e04 --synthetic-resource-check` | 158,857 generated frames across 2 independent halves; passed |
| `find data -maxdepth 2 -type f` | only `data/README.md`; licensed match assets unavailable in this worktree |

The combined existing suite therefore ran 300 tests with 2 skips. The skipped
tests are retained as the repository reports them; no skip was reclassified as
success. The approved environment was not modified and no package was
installed.

## Exact E04 call graph

The pinned V3 entrypoint is `starter_v6/run_e04.py`:

1. `main()` (`run_e04.py:80`) loads the strict E04 config, resolves the
   tactical paths with `games.asset_paths()`, requires ATD metadata/raw data
   and Smart Tagging, and obtains the tactical frame count (`:102-118`).
2. It parses ATD metadata with `ingestion.parse_atd_metadata()` and Smart Tags
   with `ingestion.parse_smart_tagging()`, builds the half mask with
   `half_index_by_video_frame()`, and streams strict ATD rows through
   `iter_atd_frames()` (`:115-119`).
3. `pipeline.restart_frame_mask()` marks only half-open `SET PIECES` intervals
   whose `Type` is one of the six known restart types (`pipeline.py:105-118`).
4. `pipeline.iter_frame_evidence()` checks contiguous zero-based video rows,
   converts each ATD row through `frame_evidence_from_atd()`, and runs the
   stateful `RuntimeRestartActionDetector` (`pipeline.py:121-181`).
5. When enabled, `tag_features.iter_tag_evidence()` converts the parsed event
   stream into one bounded contextual record per frame (`tag_features.py:65-127`).
6. `inference.iter_infer_e02()` consumes the evidence stream and optional tag
   stream (`inference.py:222-248`). It calls `iter_frame_features()`, computes
   soft team evidence in `_team_evidence()`, asks
   `StatefulDeadBallDetector.observe()` for raw play-state evidence, applies
   `confirm_dead_ball()` / `finalize_dead_ball()`, and builds finite H/A/D
   emissions via `_result()` and `emissions.fuse_evidence()` (`:271-318`).
7. The runner buffers each official graded half independently and calls
   `hmm.decode()` at the half boundary (`run_e04.py:131-169`). Ungraded rows
   remain `X`; decoded graded rows are written as the exact `frame,label`
   sequence (`run_e04.py:174-181`). Aggregate diagnostics and local provenance
   metadata are written after the CSV (`:182-230`).

The older E01/E03 runner remains available at `starter_v6/run_e01.py`; it uses
the same ingestion, evidence adapter, E02 inference, and tag-context modules,
but writes framewise inference output directly. E04 adds the independent
per-half HMM/Viterbi decode at the final boundary.

## Source and timebase audit

### Tactical timeline and ATD

- `games.py` declares the tactical source as the submission authority with
  199,319 frames at 25 FPS and pitch dimensions 105.3 × 68.0 metres.
- `ingestion.iter_atd_frames()` requires sequential one-based `frame_id` values,
  rejects gaps/duplicates/out-of-order rows, and maps each row to
  `video_frame = frame_id - 1` (`ingestion.py:259-305`).
- `_observation()` retains normalized coordinates, scales finite coordinates to
  metres, and records position/speed validity separately. Missing tokens become
  NaN-backed invalid observations; they are not converted to `(0, 0)` or to
  DEAD (`ingestion.py:227-256`).
- `frame_evidence_from_atd()` drops invalid player observations, preserves
  anonymous slot indices only within the row, and sets a missing ball to
  `ball_xy=None, ball_speed=None` (`pipeline.py:121-156`).
- `half_index_by_video_frame()` assigns half `0` to ungraded frames and the
  two published graded blocks to half `1`/`2`, rejecting out-of-range or
  overlapping blocks (`ingestion.py:475-486`).

### Smart Tagging

- `parse_smart_tagging()` reads `start`/`end` seconds and maps them with
  `round(seconds * fps)` into `SmartTagEvent.start_frame/end_frame`
  (`ingestion.py:381-422`).
- `Team` is normalized to `H`, `A`, or explicit `N/A`; raw tags are retained.
  `Type` and `Half` are retained in the tag mapping.
- `iter_tag_evidence()` uses half-open intervals, removes events at their end
  frame before adding events at the current start, and caps overlapping team
  priors to one unit per team (`tag_features.py:65-127`). Conflicting team tags
  are neutralized rather than combined as independent votes.
- In the pinned runtime, Smart Tags provide weak team/context and restart
  context. A tag alone does not directly write `H`, `A`, `D`, or `X`. `Half` is
  parsed and retained but is not consumed as an inference feature by
  `tag_features.py` or `run_e04.py`; half state comes from `games.py`/the
  frame mask.
- Restart context is not itself a restart execution frame. The runtime action
  detector requires observed motion after stationary or missing-ball context
  and emits `restart_action`; that cue is treated as LIVE counterevidence, not
  as a hard possession owner (`pipeline.py:21-103`).

### Stage 1 — LIVE/DEAD

The Stage 1 boundary is `StatefulDeadBallDetector.observe()` in
`starter_v6/possession.py`, called from `iter_infer_e02()`. Raw cues include
hard/soft out-of-bounds candidates, restart-stationary context, collective
stationarity, ball motion, missingness, and live counterevidence. Confirmation
is separate from raw observation and requires configured temporal support. A
missing ball returns a non-confirmable live/uncertain observation; it does not
create DEAD. A restart action is explicitly treated as a transition back to
play, not a DEAD cue.

### Stage 2 — H/A ownership

The Stage 2 boundary is `_team_evidence()` in `starter_v6/inference.py:47-122`,
fed by `features.iter_frame_features()`. It uses observed-ball nearest distance,
top-k distance, team density, contested margin, co-motion, coverage and jump/
quality penalties. Missing-ball gaps are buffered and can only be revised when
opposing post-gap motion and recovered control satisfy the existing support
contract (`inference.py:336-481`). Tracking slots are not treated as stable
player identities; `track_id` is row-local evidence only.

### Homography

- `ingestion.load_homography_arrays()` validates zero-based sequential frame
  indices, row-major 3×3 matrix fields, finite matrices when `valid=1`, and
  non-negative reprojection error (`ingestion.py:425-472`). The declared
  mapping direction is normalized pitch XY → video pixel XY.
- `starter_v6/load_homography.py` provides pixel projection/unprojection
  helpers, but no runtime E04 inference module imports or calls them.
- The only `starter_v6` consumer is the aggregate `build_data_quality_report()`
  path in `ingestion.py:493-592`; `run_e04.py` does not load homography.
- Finding: **NO INDEPENDENT GEOMETRY SIGNAL** is available to the pinned E04
  inference path. Projecting an ATD point through a homography would only
  re-express the same ATD observation, not independently validate ball
  location, entire-ball line crossing, or last touch. A future P4 decision
  must therefore either identify a permitted independent pixel observation or
  omit runtime homography features.

## Feature inventory and risk map

| Area | Available at pinned V3 | Missing / unverified | P1–P4 reuse implication |
|---|---|---|---|
| ATD alignment | strict streaming parser, one-based→zero-based mapping, metric scaling | actual licensed rows unavailable locally | reuse loader; add only contract tests first |
| ATD quality | missing masks, finite checks, speed validity, jump/mismatch flags, coverage and slot-population diagnostics | identity continuity and physical correction are unavailable | preserve anonymous-slot policy; do not infer from gaps |
| Stage 1 | raw dead cues, confirmation, persistence, restart action/recovery context | referee-only onset and unobserved legal onset | P1/P3/P6 must distinguish onset, persistence and restart |
| Stage 2 | H/A proximity, top-k/density, motion/co-motion, bounded gap recovery | independent controlled-possession labels | P3/P5 must add only auditable control evidence |
| Smart Tags | six restart types, normalized Team, contextual families, overlap cap | tag timing is phase context, not exact legal execution | P2 can refine provenance, not copy intervals into labels |
| Homography | strict parser and quality fields | no independent pixel observation or runtime consumer | P4 should default to audited omission |
| Temporal decode | independent half HMM/Viterbi, X outside graded blocks | no calibrated probabilities or independent accuracy set | preserve feature-off exact V3 mode |
| Protected artifact | tag, commit, release docs, historical expected CSV hash | protected CSV and licensed inputs absent from this worktree | keep V3 tag as rollback; never fabricate hash verification |

The candidate inspection names `starter_v6/two_stage.py` and some later-branch
interfaces, but `two_stage.py` is not present at this commit. No later-branch
implementation or test count was imported.

## Protected release and privacy findings

- `e04-v3-g8-release` and its peeled commit are intact.
- The documented historical CSV SHA256 is
  `d1604474717565a460d30bdef271d4e6e9b6c088c00bec84f6ef3d97a35f74ae`, but the
  corresponding protected CSV is not present in this isolated worktree. Its
  verification status is therefore **NOT AVAILABLE**, not passed.
- Only the public evaluation CSV and committed baseline CSVs are present; no
  protected full-match output or licensed data was copied.
- `.gitignore` already ignores `.local-checkpoints/`, `data/*`, prediction and
  submission artifacts. The local checkpoint proof is recorded in
  `TFV3_P0_PROTECTION_MANIFEST.md` and the ignored directory README.

## Reuse map and P0 stop boundary

- P1 may reuse the actual `games.py`, ingestion, half-mask, tag interval, and
  homography parser contracts; it must add synthetic off-by-one and missingness
  coverage before changing behavior.
- P2 may reuse `SmartTagEvent`, `parse_smart_tagging()`,
  `restart_frame_mask()`, and `TagEvidence`; it must keep tags contextual and
  unknown owners unknown.
- P3 may reuse `FrameFeatures`, `ObservationQuality`, and the existing
  motion/co-motion calculations; the T1 constant-speed co-motion concern and
  identity-switch risk remain open.
- P4 must make the independent-information decision explicitly. The current
  source audit supports omission unless a new permitted observation is found.
- P5/P6/P7+ are not started by this phase.

This report is an audit and safety deliverable only. It does not introduce a
new inference feature, modify the protected V3 behavior, generate a submission,
or use public labels for selection.
