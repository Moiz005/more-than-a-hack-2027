# TacticalFusion P5 — conservative ownership and controlled transfers

## Result

**G5 PASS — synthetic engineering contract only.** The existing E02 Stage 2
already had H/A geometry, bounded gap recovery, and temporal acquisition. This
phase adds explicit ownership comparison modes, an auditable H/A/UNKNOWN
control hypothesis, accepted transition records, and conservative carry through
reliable fast-ball flight when the receiving team lacks persistent ATD control.
No new submission label was added. UNKNOWN remains internal.

This phase establishes reproducible semantics on synthetic cases. It does not
establish improved match accuracy, `spellF1`, or `macroF1`.

## Source audit and evidence contract

Inspected the actual Stage 2 at the Phase 5 starting checkpoint `6330065`,
including `features.py`, `inference.py`, `possession.py`, `atd_signals.py`,
`emissions.py`, `hmm.py`, `tag_features.py`, `pipeline.py`, and `run_e04.py`.
The protected V3 baseline remains `9fd0277a23258a448e0863b33d646c8540070c50`.

- ATD slot team roles are the source of H/A mapping. Slot IDs are row-local
  observation identifiers; the code does not calculate persistent player
  identity or per-slot velocity. Half changes reset feature and inference
  state. E04 decodes each contiguous graded half separately.
- Team geometry retains separate H/A scores. Nearest proximity, top-k support,
  and team density form one bounded geometry score with weights `0.55/0.25/0.20`.
  Team confidence combines bounded proximity/separation with at most `0.10`
  geometry-margin and `0.05` co-motion adjustments, then applies the quality
  weight and clips to `[0,1]`. ATD support floors confidence with `max` rather
  than adding another full vote; boundary and rapid-motion hypotheses discount
  confidence. Smart Tagging can only resolve a close, observed-ball contest;
  it does not create control without player/ball geometry. These are heuristic
  evidence potentials, not calibrated probabilities.
- Direct observed-team changes use the existing consecutive-frame acquisition
  gate. Accepted gap recovery remains bounded by quality, duration, consecutive
  motion support, and observed recovery; its direction and interval are already
  recorded in `GapOwnershipEvidence` and modify emissions before Viterbi.
- Restart proposals and Smart Tagging remain context. Following confirmed D,
  the old live owner is not carried through the stoppage; a newly observed team
  must acquire ownership under the normal or corroborated restart gate. Unknown
  restarting-team context stays unknown.
- Homography remains omitted from runtime ownership under the G4 decision.

## Added interface and behavior

`E02FrameInference.control_hypothesis` records an H/A/UNKNOWN status, candidate
team, bounded heuristic confidence, evidence groups, and ATD quality flags.
`control_transition` records accepted source/target team, the inclusive support
interval, support count, confidence, and reason. Initialization from UNKNOWN is
distinguished from a known H↔A handover. Typed tag evidence remains separately
available on the frame result. Existing `TeamObservation.source` values and
default V3 output behavior remain unchanged.

`ownership_mode` in E04 JSON config is strict and E04-only:

| Mode | ATD Stage 2 control fusion | Smart Tag team context |
|---|---:|---:|
| `v3_exact` | off | on |
| `atd_control` | on | off |
| `atd_control_plus_context` | on | on |

An omitted mode preserves custom `features` and `tag_features` settings. The
example config selects `v3_exact`.

In ATD modes, if a reliable derived ball speed reaches the configured
`ownership_flight_speed_mps` (8 m/s by default), current ownership is retained
in the H/A emission while an opposing nearest-player observation lacks
persistent ATD control support. Implausible jumps and provider/displacement
speed mismatches do not trigger this carry. Internal control remains UNKNOWN
during the carry; aggregate diagnostics report internal UNKNOWN frames
separately from graded external X outputs. Affected speed and carry-confidence
settings are explicit in `features` config.

## Synthetic counterfactuals and trade-off

The new Phase 5 test module covers both H→A and A→H; one- and two-frame nearest
opponent blips; a row-slot position discontinuity; high-speed ball flight near
an opponent without persistent control; low player coverage and contested
geometry; weak/unknown Smart Tag team; H→D→A and H→D→H; and unknown owner after
D. It also checks deterministic transition records and explicit mode mapping.
Existing Phase 5 tests cover accepted missing-ball recovery, missing-ball
neutrality, and goalkeeper-like live play; existing lifecycle tests cover
restart execution, half reset, and spell boundaries.

| Synthetic case | Result | Ownership/spell trade-off observed |
|---|---|---|
| Stable opposing control | Transfer recorded after 3 consecutive observations (2-frame lag after first evidence) in both directions | No candidate selected by public labels; latency is the configured hysteresis |
| 1–2 frame opposing nearest-player blip | No opposing transition | Avoids a synthetic false handover/fragmentation in these fixtures |
| Fast ball near opponent, no persistent control | Prior live owner remains in emission; control hypothesis is UNKNOWN | Reduces premature handover; can delay a real transfer until persistent control appears |
| H→D→A / H→D→H | No pre-D owner is emitted on first restart frames; new owner follows support | Unknown restart evidence stays X/UNKNOWN until observed control is adequate |
| Low coverage, contest, N/A team context | UNKNOWN; no tag-only owner | Preserves uncertainty; may delay initial ownership |

These outcomes are synthetic only. No match data, public ground truth, or
manual frame annotations were used in this phase. The internal-UNKNOWN count
and external-X count are reported separately, but metric cost cannot be
quantified without authorized independent labels.

## Verification

Focused ownership/config/lifecycle command:

```sh
/Users/moiz/Desktop/Metrica-Sports-Hackathon/more-than-a-hack-2027/.venv/bin/python -m unittest starter_v6.tests.test_phase5_modes starter_v6.tests.test_phase5_ownership starter_v6.tests.test_inference starter_v6.tests.test_config starter_v6.tests.test_lifecycle_catalog starter_v6.tests.test_restart_action_integration starter_v6.tests.test_phase6_fusion -v
```

Result: **66 tests passed** (including 15 new mode/ownership tests). E04
synthetic self-check passed.

Full v6 suite:

```sh
/Users/moiz/Desktop/Metrica-Sports-Hackathon/more-than-a-hack-2027/.venv/bin/python -m unittest discover -s starter_v6/tests -p 'test_*.py'
```

Result: **245 passed, 1 skipped**. The suite caught and prevented a provenance
tuple change that broke protected V3 comparison; the legacy tuple was restored
and the final full suite passed. `run_e04 --self-check` passed; `git diff --check` passed. No package was
installed. No public evaluation or accuracy comparison was run.

## Files and rollback

Changed: `config.py`, `config.example.json`, `features.py`, `inference.py`,
`run_e04.py`, `tests/test_config.py`, and `README.md`; added
`tests/test_phase5_modes.py` and this report. The ATD fusion example was also
updated to remove its obsolete restart acquisition shortcut setting. All match-derived outputs remain
local/ignored. Roll back Phase 5 by reverting its checkpoint commit; the
protected release checkout and tag were not modified.

Next eligible phase: **P6 — Stage 1 LIVE/DEAD and six-restart lifecycle**.
