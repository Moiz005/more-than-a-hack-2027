# Phase 8 engineering acceptance

Executed from the release-preparation working directory:

`.venv/bin/python -B -m unittest discover -s starter_v6/tests -p 'test*.py'`

Actual: 194 passed; zero failures, errors, skipped or expected failures.
The 187 -> 194 change is seven new scorer-semantics tests, not changed algorithm
expectations. E04 --self-check passed. The exact committed clean checkout must
also be verified before tagging; its observed logs remain private.

## Official semantics S1-S7

All seven test methods live in tests/test_release_spell_semantics.py and call
the unmodified evaluation.possession_metrics implementation using invented labels.

| Check / exact test method | Expected / observed | Result |
|---|---|---|
| test_S1_same_team_separated_by_dead | HHHDDHHH has H[0,3),H[5,8) | PASS |
| test_S2_false_dead_fragments_one_spell | H8 vs H3D2H3 yields 1 reference/2 predicted spells; one match at .3, none at .4/.5/.6/.7 | PASS |
| test_S3_missing_dead_merges_two_spells | Reverse comparison yields 2 reference/1 prediction; same threshold match counts | PASS |
| test_S4_direct_turnover_needs_no_dead | HHHAAA has H[0,3),A[3,6), no D | PASS |
| test_S5_abstentions_charge_frames_but_fill_temporally_per_valid_run | HXXAXX against HHHAAA has raw macroF1 1/3, perfect absent-D reference has 2/3; filled temporal labels exact. Leading X backfills; all-X run stays X; no filling across ungraded gap | PASS |
| test_S6_all_thresholds_same_team_iou_and_one_to_one | .3/.4/.5/.6/.7 verified; same-team IoU3/8; one merged prediction cannot match two references; wrong-team overlap ignored | PASS |
| test_S7_grading_gaps_split_halves_and_graded_dead_is_retained | HHXXHH stays two H spells; DDXXDD retains graded D and separate valid runs | PASS |

Official temporal runs derive from reference non-X spans, not independent half
IDs. In the published contract an ungraded gap separates halves. Contiguous
same-label halves without a reference gap are not split by scorer magic.
ATD indexing separately passes PipelineAdapterTests.test_adapter_rejects_slot_count_and_frame_alignment_errors
and test_stream_adapter_checks_first_last_rows_and_mask_alignment.
S5's toy metric values explain absent-class/X behavior only, not release accuracy.

## Regression R1-R18

All methods below passed in the full command above. `L` denotes
tests/test_lifecycle_catalog.py::LifecycleCatalogTests; `P` denotes
tests/test_dead_ball_persistence.py::DeadBallPersistenceTests; `C` denotes
tests/test_v3_context_consumption.py::ContextConsumptionTests; `B` denotes
tests/test_boundary_quality.py::BoundaryQualityTests. These files use production
inference/emission/Viterbi components. L additionally runs invented ATD/tag
records through the actual adapter; P directly constructs upstream evidence.

| Requirement | Exact method(s) | Expected and actual / status |
|---|---|---|
| R1 memory | P.test_a_causal_stoppage_gap_restart_two_home_spells; test_b_live_missing_does_not_seed_memory; test_c_expiry_is_neutral_and_does_not_reconfirm_itself; test_g_half_and_ungraded_reset | Confirmed seeding, decay, no fresh missing-only D, neutral expiry/reset; PASS |
| R2 old context | C.test_causal_comparison_to_protected_phase0_tree | Historical DDDHHDDDD -> DDDHHHHHH; PASS |
| R3 new stop | C.test_independent_boundary_after_consumption; L.test_L5_comprehensive_boundary_gap_throwin_new_stop | Independent boundary D preserved; PASS |
| R4 jump | B.test_protected_phase1_causal_oracle; test_isolated_jump_is_uncertain_not_hard_and_cannot_seed_memory | HDH -> HHH; no hard D/memory seed; PASS |
| R5 reliable crossing | B.test_reliable_crossing_and_speed_mismatch_only_remain_hard | HDH stays hard D, speed mismatch alone not the jump gate; PASS |
| R6 recovery | B.test_later_consistent_boundary_recovers_and_seeds_memory | Reject suspect onset then confirm consistent boundary; PASS |
| R7 keeper | L.test_L7_goalkeeper_and_slow_live; P.test_f_goalkeeper_live_gap_does_not_start_stoppage | Slow keeper-like live H and missing gap create no automatic D; PASS, identity/standstill LIMITATION |
| R8 H-D-H | L.test_L1_same_team_stop | HHHHDDDHHHH, two H spells; PASS |
| R9 H-D-A | L.test_L2_stop_then_away | HHHHDDDAAAA, supported A after D; PASS |
| R10 H-A | L.test_L3_direct_takeover | HHHHAAAA, no artificial D; PASS |
| R11 deflection | L.test_L4_deflection_is_ambiguous_not_control | H10 missing-contact fixture / H9 brief-A fixture; PASS, real contact semantics LIMITATION |
| R12 long tag | L.test_L8_consumed_context_and_independent_boundary; C.test_missing_after_delivery_does_not_reactivate_retired_memory | No duplicate stale D or revived memory; PASS |
| R13 inertia | L.test_neutral_expiry_does_not_force_decoder_live | D33 despite neutral expired tail, not confirmed live; PASS |
| R14 short D | L.test_L11_short_structural_stop_vs_outlier | HHHHDHHHH for structural D vs H9 outlier; default filter off; PASS |
| R15 no prior D | L.test_L12_restart_without_confirmed_dead | H5 despite recognized delivery; no invented earlier D; PASS |
| R16 independent cue | B.test_independent_collective_cue_survives_suspicious_boundary | stationary_context survives rejected boundary; PASS |
| R17 halves | L.test_L10_quality_halves_ungraded_and_pre_kickoff; C.test_halves_rearm_even_if_mask_remains_active; B.test_half_reset_no_cross_half_jump | DDDXDDDHHHH, fresh second-half setup/no state leakage; PASS |
| R18 contexts | L.test_L6_supported_restarts_and_unsupported_penalty | DDDHHHH for free kick/corner/goal kick/start/after-goal kickoff; GOALS tag does not label full interval D; PASS. Dedicated penalty/goal onset LIMITATION |

HMM DecoderTest.test_matches_exhaustive_oracle_across_many_short_sequences
checks 120 emission sequences against all tiny state paths. Runtime import
isolation resolves local v6 modules without v4/v5. Tests deliberately exercise
known limitations instead of silently changing expected labels.

## Public-code/privacy review

All 197 pre-release tracked paths were inventoried locally, along with proposed
release additions, imports, config, dependency list and output-path guards.
No tracked licensed asset, private checkpoint, unexpected large binary or
high-confidence credential-pattern finding was identified. Public organizer
GT and four baseline CSVs are deliberate fixtures; no public-score values were
opened for selection. Only data/README.md is tracked under data/.
Ignored checkpoints and local input links stay outside Git. Historical protected
directories and tags remain unchanged. No remediation/dependency change is
needed. Pattern scanning is not a proof that every possible secret is absent.

Older local public-scoring artifacts were discovered without reading scores.
Fresh selection and limits of historical influence verification are documented
in V3_RELEASE_DECISION.md. No new public-GT evaluation, external acquisition,
manual match labels, match-specific patches or restricted uploads occurred.

All model source and config remain byte-identical to C4. Current input hashes
match the recorded Phase 4 fingerprints. This is engineering evidence, not
admissible independent accuracy evidence. NO MEASURABLE REAL-MATCH SPELLF1 EVIDENCE.
