# Synthetic lifecycle integration

Baseline/rollback: 4f14c6a6bf72bf4498c942dd16d815bb5787d01b.
The original lifecycle catalog remains default-mode coverage. TacticalFusion
plan Phase 6 additionally exercises the opt-in Stage 1 lifecycle mode under
`test_phase6_lifecycle_contract.py`; default `stage1_lifecycle_enabled=false`
preserves V3 behavior. All tests use invented inputs.

## Harness and execution

`tests/lifecycle_harness.py` constructs invented ATDFrame/Observation records
and SmartTagEvent intervals. XML/text parsing and official match half constants
are replaced by deterministic typed fixtures and explicit synthetic half masks.
The real iter_frame_evidence, restart_frame_mask, runtime restart detector,
iter_tag_evidence, iter_infer_e02, features, stateful detector, confirmation,
persistence, fusion and HMM execute directly. No detector is mocked; no D label
or emission is injected. Existing ingestion tests cover parser/index boundaries.

`lifecycle()` checks frame order, decodes each graded half independently, emits
X for ungraded frames, and extracts H/A spells per half. Its invented-only rows
record ball/motion, players, quality, tags, action/consumption, evidence scores,
confirmation/retained/expired provenance, parent state, emissions and final labels.
Final evidence retains the raw cue/scores; it is not a second independent raw
detector trace. Never use this harness on licensed data or real match outputs.

`spell_report()` uses inclusive test intervals, same-team temporal IoU and
descending-IoU one-to-one greedy matches at prespecified IoU .5. It records
counts, offsets, unmatched spells, false splits and merged neighbors. Equivalence
to official half-open matching is checked on invented intervals only. X is
ungraded in this harness; hypothetical graded-X abstention filling is outside
this harness because E04 final decoding assigns H/A/D on every graded frame.
Spell indices are zero-based and end-inclusive; D never joins H spells.

Run from repository root:
`.venv/bin/python -B -m unittest starter_v6.tests.test_lifecycle_catalog`
Full regression:
`.venv/bin/python -B -m unittest discover -s starter_v6/tests -p 'test*.py'`

## Prespecified catalog and failure/ambiguity matrix

| ID | Expected/observed contract | Classification / limitation |
|---|---|---|
| L1 | HHHHDDDHHHH; H [0,3], [7,10] | Strong supported setup/delivery |
| L2 | HHHHDDDAAAA; H [0,3], A [7,10] | Strong controlled A geometry after D |
| L3 | HHHHAAAA; H [0,3], A [4,7] | Sustained controlled live takeover |
| L4 | H10 through 2 missing frames; H9 through 1 A-proximity frame | Ambiguous contact has no touch/deflection input; no claim of semantic contact recognition |
| L5 | H4 D4 H7 D; H [0,3], [8,14] | Full boundary/missing/reappearance/consumption/new-stop lifecycle |
| L6 | DDDHHHH; H [3,6] for five recognized restart kinds | Free kick, corner, goal kick, start kickoff, after-goal kickoff |
| L6 penalty | H7 with unknown-owner setup | Unsupported penalty tag; H is decoder tie choice, not verified football ownership. Generic structural evidence is separately covered by L5/L11 |
| L6 goal | GOALS alongside recognized kickoff does not label full interval D | Goal-specific onset is unsupported; setup is supported by kickoff plus slow ball |
| L7 | H6 for keeper-like holding, slow movement and passing | Full nearby-player coverage; no goalkeeper identity field. Collective tactical standstill remains ambiguous |
| L8 | Exact old fixture DDDHHHHHH; fresh boundary tested by L5 | Consumed context suppresses only stale restart_stationary; merged event identity remains limited |
| L9A | H12 through missing gap | Missingness cannot create D |
| L9B/C | D evidence decays to neutral after 25 frames; restart retires it | With later live return: D28 H9. Without later restart: D33 despite neutral final emissions. This is decoder behavior, not indefinite fresh memory |
| L10 | DDD X DDD HHHH; H [7,10] | Explicit ungraded halftime, independent new-half pre-kickoff setup. Outlier/recovery and speed-mismatch controls included |
| L11 | HHHHDHHHH vs H9 | One reliable structural frame splits H; flagged outlier does not. No duration filtering |
| L12 | H5, one-frame setup unconfirmed, delivery emits live=.9 | Restart can be consumed without prior confirmed D; normalization redundancy is covered by existing Phase 1 tests |

The supported exact boundaries were declared in tests before their first run.
No label assertions were rewritten to match output. The initial L5 reappearance
fixture was corrected from a 1.4 m displacement to .9 m, inside the existing
1 m runtime gate. It now yields restart_reappearance, appropriate because there
was no observed stationary setup. Expected label/spell boundaries did not change.

## TacticalFusion Phase 6 opt-in contract

The six typed statuses and restart-type semantics are covered in
`tests/test_phase6_lifecycle_contract.py`. A stop candidate from one outside
coordinate stays unconfirmed; persistent D requires reliable action or
consecutive live recovery to leave. Restart context is deduplicated by type;
conflicting simultaneous types cannot trigger execution. Free Kick context
alone stays `RESTART_PREPARATION`, not confirmed D. Five kick restarts require
stationary setup and credible displacement, while throw-in execution requires
observed field entry. These are conservative engineering rules, not legal-state
ground truth, and are not enabled in default E04 configuration.

## Risks and exclusions

No core supported lifecycle contract failed, and no integration fix was needed.
Penalty/goal/foul/offside onset and real touch semantics remain unsupported.
Unknown owner under symmetric live evidence is resolved by deterministic HMM
ties, not observation certainty. A short opposing blip is suppressed by the HMM;
that does not prove it was a deflection. Strong structural short D survives.
Unseen restarts, merged context identities, missing-ball onset and collective
tactical standstill remain unresolved model limitations. Neutral emissions can
remain D, and later observations influence offline Viterbi boundary placement.
No real-match accuracy or spellF1 inference follows from synthetic exact matches.
