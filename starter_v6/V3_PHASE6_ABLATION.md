# V3 Phase 6 — Causal coverage and release assessment

Start/rollback: 6642298534727f59740d58efba82d678c35dae98.
Candidate provenance: V3_CANDIDATE_LEDGER.md. Decision A: select C4, skip Phase 7.
No production/config changes. No external acquisition or public-GT scoring.

## Method and reproducible commands

New tests/test_phase6_ablation.py runs five unittest methods, with multiple
fixtures. Historical code executes via git archive in isolated temporary trees;
no checkout switching, historical edits, monkey patches or licensed inputs.
Same synthetic script/config/HMM executes in C0-C4. Type A is a supported
single-setting or input intervention; Type B is audited adjacent source; Type C
is multi-field/cumulative evidence and cannot attribute a single mechanism.

Commands actually executed:
- .venv/bin/python -B -m unittest starter_v6.tests.test_phase6_ablation
- .venv/bin/python -B -m unittest discover -s starter_v6/tests -p 'test*.py'
- .venv/bin/python -B -m starter_v6.run_e04 --self-check
- Inline git-object source/config/hash/ownership-AST comparisons and synthetic
  label/spell reports; git diff --check; official validator on preserved C0-C3
  run1 CSVs; SHA256 and byte equality on existing run1/run2 pairs.

Actual: 5 ablation tests passed; full suite 187 passed, 0 failed/skipped/expected
failures. Full suite includes 16 lifecycle tests, HMM exhaustive arithmetic,
import isolation, persistence and all prior phase regressions. No thresholds
were selected from these outcomes. No new full-match generation was necessary.

## A1-A5 causal findings

| Experiment | Control -> treatment | Evidence and result | Isolation |
|---|---|---|---|
| A1 positive | persistence 0 -> 25, same current source | H4 D3 H8 -> H4 D6 H5. Missing-frame D=0 -> .733974,.717949,.701923; retained evidence remains unconfirmed; restart retires it | Type A config intervention |
| A1 live/missing and missing-only | same window pair | Every emission unchanged, no new D | Type A negative |
| A1 long gap/half reset | same source, prespecified policy | At missing age26 D becomes 1/3, no confirmation; half reset clears memory | Evidence-policy assertions; off mode need not be neutral |
| A2 old long tag | C0 -> C1 | DDDHHDDDD -> DDDHHHHHH; stale restart_stationary removed, confirmation true->false, D .99->0; H/A evidence unchanged | Type B, audited two-file lifecycle change |
| A2 negatives | C0 -> C1 | Independent boundary DDDHHDD, fresh-gap DDDHHHDDDHH, half reset DDDHHDDDHH, unconsumed setup DDDD and live-tag HHHHH unchanged | Type B |
| A3 outlier | C1 -> C2 | HDH -> HHH; flagged hard boundary/confirmation rejected; D=1 -> 1/3; no independent memory seed | Type B, audited boundary-quality change |
| A3 reliable boundary | C1 -> C2 | HDH unchanged; hard D=1 preserved | Type B negative |
| A3 recovery | C1 -> C2 | HDDD -> HHDD; initial suspect confirmation removed, next consistent boundary confirms and seeds memory | Type B, intended delay |
| A3 other negatives | C1 -> C2 | In-play jump, missing-only, setup and consumed-context outputs unchanged; independent collective cue survival covered by boundary suite | Type B plus current negative controls |
| A4 delivery/reappearance | remove action field only after real adapter; retain consumption, ball motion and ownership | raw live .9 -> .7, normalized emissions and labels identical; moving evidence retires memory without action | Type A input intervention, not detector-off ablation |
| A4 lifecycle contribution | remove both action and consumption | DDDHHHHHH -> DDDHHDDDD | Type C multi-field intervention: consumption mediation, not isolated M2 |
| A5 combined lifecycle | current C4 production via canonical ATD harness | H4 D4 H7 D, H[0,3]/H[8,14]; restart consumes context, retired memory stays retired, new reliable boundary survives | Current integration; no invented off toggle |

Full M2 detector-off ablation is NOT ISOLATABLE UNDER CURRENT INTERFACES without
altering its coupled consumption output. No production toggle was added. Tested
delivery and reappearance action fields are redundant at normalized-emission
level; recognized restart still has a mediated role through consumed context.
Do not generalize limited fixtures to accuracy or universal signal redundancy.

M1 has no supported independent off toggle: NOT ISOLATABLE as a complete runtime
mechanism. Its onset/persistence integration is exercised in the production
tests. M6 remains byte/AST identical and is a control, not a tuning target.

## Synthetic spell boundaries (inclusive)

| Case | Expected treatment spells | Control spells | Treatment spells / matching |
|---|---|---|---|
| A1 | H[0,3], H[10,14] | H[0,3], H[7,14] | Exact two H; control second start offset -3, IoU 5/8; no split-count difference |
| A2 | H[3,8] | H[3,4] | Exact one H; control end -4, IoU 2/6; false tail D truncates possession |
| A3 isolated jump | H[0,2] | H[0,0], H[2,2] | Exact one H; control false split=1, each overlap IoU1/3 |
| A3 reliable | H[0,0], H[2,2] | Same | Both exact, two H spells |
| A3 recovery | H[0,1] | H[0,0] | Exact one H; control end -1, IoU1/2 |
| A4 fixed consumption | H[3,8] | Same | No spell difference |
| A5 | H[0,3], H[8,14] | no off comparison | Two H, exact D interruption; later independent D |

All listed A-spell counts are zero; Phase 4 L2/L3 supply A-positive controls.
One-to-one matches at IoU .5: A1 2/2, A2 control0/treatment1,
A3 outlier control0/treatment1, reliable2/2 in both, recovery1/1 in both.
IoUs/offsets are synthetic engineering checks, not full official spellF1. Full
competition spellF1 averages .3/.4/.5/.6/.7, which is not computed or used for
candidate ranking here. Existing official matching parity tests use invented data.

## Risks and smallest future checks

| Risk | Evidence status / stage affected | Minimal future evidence |
|---|---|---|
| R1 missed action leaves stale tag | Verified conditional reproduction: setup, 1.2m/step live motion, later stillness -> DDDHHDDDD with zero actions. The motion exceeds existing conservative 1m action gate; not a regression of supported-action contract | Independently labeled restart coverage; do not widen sensitivity on one toy |
| R2 merged context hides new tag-only event | Verified boolean-mask limitation; cue extraction cannot rearm within uninterrupted consumed run; physical cues survive | Independently annotated distinct event identities and negative controls |
| R3 unseen restart while missing | Plausible ambiguity: same missing observations can hide live return, while memory supports D | Authorized independent boundaries during occlusion |
| R4 expiry during real stop | Policy verified, football truth unknown: neutral emissions after 25; not proof play resumed | Independent long-stop labels |
| R5 true abrupt crossing flagged | Plausible quality false rejection; emissions delayed until reliable evidence | Independent trajectory-quality reference |
| R6 consistent wrong coordinates | Verified model response, tracking truth unverified: consistent off-pitch observations confirm hard D | Synthetic consistent sensor-bias stress plus independently corrected tracking |
| R7 tactical standstill | Verified observational ambiguity: slow ball plus 8 slow players can confirm stationary_context without external corroboration | Other-game live standstill/stoppage labels |
| R8 ambiguous ownership | Verified short-opponent-blip suppression and unresolved missingness; actual controlled recovery vs deflection is not observable from identical inputs | Independent controlled-possession labels |
| R9 Viterbi inertia | Verified: neutral expiry tail can remain D; soft isolated candidate can be suppressed, hard one-frame D survives | Prespecified synthetic strength/timing controls; no transition tuning |
| R10 unsupported event semantics | Verified no dedicated penalty/goal/foul/offside onset path | Independent event/label semantics, separate future authorization |

R1 is a known limitation of conservative action coverage, not new evidence that
a broader detector or Phase 7 model experiment is safe. Changing sensitivity
needs validation unavailable here. No current supported lifecycle contract has
failed. None of the risks warrants speculative simultaneous model changes.

## Decision

Select C4 exactly: 6642298534727f59740d58efba82d678c35dae98. C0/C1 have proven
defects; C2-C4 share the corrected executable, with progressively more complete
verification/documentation. Preserve C0 as frozen fallback and Phase 5 as the
assessment rollback. Skip optional Phase 7; Phase 8 may begin when authorized.
G6.1-G6.5 PASS. Actual spellF1 superiority is UNKNOWN.
INDEPENDENT REAL-MATCH ACCURACY COMPARISON: NOT RUN. No IDSSE acquisition.
No D-count/histogram or synthetic-score ranking was performed.
