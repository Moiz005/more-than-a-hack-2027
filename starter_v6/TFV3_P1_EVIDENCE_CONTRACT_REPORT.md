# TacticalFusion V3 Phase 1 evidence contract report

## Phase and gate

- Phase: P1 — unified tactical timeline, data quality and evidence contracts.
- Gate: G1 PASS.
- Baseline: `9fd0277a23258a448e0863b33d646c8540070c50`.
- Research branch: `experiment/e04-v3-visual-possession`.
- Public ground truth: not used for tuning, ranking, or selection.
- Licensed match assets: unavailable in this worktree; all validation below is
  source/schema/synthetic validation.

## Implemented contracts

### Timeline and frame mappings

`starter_v6/timeline.py` is the single small contract layer for the pinned
tactical source:

- `build_tactical_timeline()` reuses `games.py` and produces an immutable
  zero-based `half_by_frame` mask and the two graded half ranges.
- `validate_tactical_reference()` fails closed for `broadcast`, non-25-FPS
  input, or any frame count other than 199,319.
- `validate_atd_frame_mapping()` enforces `frame_id = video_frame + 1`.
- `seconds_to_half_open_frames()` preserves the competition's
  `round(seconds * 25)` conversion and validates ordered half-open bounds.
- `validate_homography_frame_index()` enforces zero-based sequential rows.

The E04 runner now validates the tactical timeline before loading ATD or Smart
Tagging. The ATD adapter and ingestion parser use the shared mapping helpers;
the existing strict sequential checks remain in place.

### Observation quality

`starter_v6/contracts.py::ObservationQuality` records:

- observed versus missing state;
- finite and valid coordinate flags;
- same-source time gap in frames;
- plausible-speed status and jump flag;
- available-player coverage;
- homography validity and reprojection error when present; and
- per-feature provenance strings.

Missing observations cannot be represented as valid coordinates. No constructor
or adapter turns a missing ball into DEAD.

### Evidence provenance

`contracts.py::Evidence` requires a typed `EvidenceSource` (`ATD`, `TAG`,
`HOMOGRAPHY`, or `TEMPORAL`), a frame/interval reference, finite signed value,
meaning, bounded quality and uncertainty, explicit missingness, and a non-empty
dependency group. Dependency groups are intentionally required so future fusion
cannot count ATD distance, ATD motion, tag context, and any homography-derived
re-expression as unlimited independent votes.

### Internal lifecycle states

The contract defines internal-only `PlayState` (`LIVE`, `DEAD`, `UNKNOWN`),
`RestartType` for all six official restart types, `PossibleOwner` (`H`, `A`,
`UNKNOWN`), and `RestartPhase` (`POSSIBILITY`, `PREPARATION`, `EXECUTION`,
`LIVE_RECOVERED`, `UNKNOWN`). `RestartHypothesis` carries confidence,
uncertainty, reference, and dependency groups. None of these enums adds a
submission class; final output remains H/A/D/X.

## Existing V3 semantics preserved

- `ingestion.parse_smart_tagging()` remains the actual Smart Tag parser. Its
  seconds-to-frame conversion now delegates to the shared helper, and
  `tag_features.iter_tag_evidence()` remains half-open and overlap-capped.
- Smart Tag `Type`, `Team`, and `Half` remain contextual metadata. Unknown/N/A
  team stays unknown; a tag alone cannot force LIVE, DEAD, H, A, or an exact
  restart-execution frame.
- Homography rows retain `valid` and `reprojection_error` independently. Invalid
  matrices remain invalid; the loader does not silently promote them. The matrix
  direction remains normalized pitch → video pixels.
- `half_index_by_video_frame()` and E04's independent per-half HMM decode remain
  the output mask/reset boundary. Ungraded frames remain X.
- No production Stage 1/Stage 2 feature or transition weight was added. The new
  contracts are additive and are not used to fabricate target-match labels.

## Time ambiguity and non-inferences

Smart Tag edges are rounded phase-window boundaries, not physical referee or
restart-execution timestamps. The contract therefore records only a half-open
interval and does not emit an execution frame from a tag edge. A valid
homography is a coordinate transform/quality record, not proof of ball-line
crossing, ball height, referee state, or last touch. Missing ball coordinates,
stationary coordinates, and provider speed alone remain insufficient to infer a
legal DEAD onset.

## Tests and equivalence

Focused Phase 1 tests (`starter_v6/tests/test_phase1_contracts.py`) cover:

- pinned tactical source/frame count/FPS and halftime reset mask;
- wrong-source and wrong-dimension fail-closed behavior;
- ATD first/last mapping plus missing, duplicate, and out-of-order IDs;
- Smart Tag rounding, half-open boundaries, and overlapping intervals;
- zero-based homography rows, valid/invalid matrix quality fields, and
  reprojection error preservation;
- missingness/provenance invariants;
- typed evidence/dependency groups; and
- internal restart-state semantics without an external X-like state.

Results:

| Command | Result |
|---|---|
| `.venv/bin/python -m unittest starter_v6.tests.test_phase1_contracts` | 8 passed |
| focused Phase 1 + pipeline/tag/features/inference/HMM tests | 50 passed |
| `.venv/bin/python -m unittest discover -s starter_v6/tests -p 'test_*.py'` | 202 passed, 1 skipped |
| `.venv/bin/python -m unittest discover -s starter_v5/tests -p 'test_*.py'` | 61 passed, 1 skipped |
| `.venv/bin/python -m unittest discover -s starter_v4/tests -p 'test_*.py'` | 45 passed |
| `.venv/bin/python -m starter_v6.run_e04 --self-check` | passed |
| `.venv/bin/python -m starter_v6.run_e04 --synthetic-resource-check` | passed; 158,857 frames across two halves |
| `.venv/bin/python -m pip check` | no broken requirements |

For the no-signal/feature-off compatibility check, the current synthetic E02
trace was compared with the same trace from a temporary archive of the pinned
baseline commit. Both JSON traces were 658 bytes and byte-identical. No public
ground-truth score was read or used.

## Limitations and next phase

- The licensed data bundle and protected release CSV are not present here, so
  actual full-file asset counts, video decode metadata, Smart Tag inventory, and
  homography row counts remain unavailable. The runtime fails closed on wrong
  metadata and will validate actual files when supplied.
- The new `Evidence` and `RestartHypothesis` types establish the contract but
  are not yet wired as additional runtime votes. This preserves exact V3 while
  making P2–P4 adapters auditable.
- Independent other-match possession labels are unavailable; no accuracy or
  spellF1 improvement claim is made.

P2 is the next eligible phase. P1 did not add Smart Tag functionality or
homography-derived inference.
