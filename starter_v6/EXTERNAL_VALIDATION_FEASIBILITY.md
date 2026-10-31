# V3 Phase 5 — External validation feasibility

Checked 2026-10-31 (Asia/Karachi). Starting reference:
35749fdf3652ba501cead2d61b96651232925164.

## Decision

**NO HELD-OUT LABELS AVAILABLE for qualified evaluation in this workspace.**
This is not a claim that no suitable public dataset exists. IDSSE is a promising
conditional source with explicit frame-level possession and ball-status fields.
No source passed all acquisition, provenance, semantics, alignment and input
compatibility checks during this phase. No raw external tracking, annotations
or videos were downloaded. Public documentation and Figshare metadata only were
accessed. No new annotation, account signup, provider contact or purchase occurred.

Stage A is complete; Stage B is NOT IMPLEMENTED. No scores are reported.
Phase 6 can proceed using engineering criteria without measured accuracy ranking.
Conditional data qualification can be separately authorized; do not hold the
candidate freeze open indefinitely or call conditional data nonexistent.

## Rules and legal gate

Current official rules were read directly:
https://raw.githubusercontent.com/metrica-sports/more-than-a-hack-2027/main/RULES.md
Other-game human labels are permitted if organizers can access the source and
the technical report explains labeling/use. Target-match human annotations,
third-party target-match event/corrected tracking data and public-window tuning
are prohibited. Repository reproducibility and asset redistribution restrictions
apply. A source being online does not by itself establish redistribution rights.

This investigation does not authorize bulk downloads, legal agreements, sharing
account details, new annotations, paid access or use of derived labels as truth.
The following table separates verified documentation from qualification gaps.

## Source inventory (primary sources)

| Source | Documented observations/coverage | Reference labels | License/access | Disposition |
|---|---|---|---|---|
| IDSSE, Bassek/Rein/Weber/Memmert; DFL/Sportec | Seven 2022/23 German matches; 25 Hz player/ball XY, metadata, frame/time/half fields | BallPossession 1/2 and BallStatus 0/1 documented in ball frames | Publisher repository and Figshare v1 explicitly CC BY 4.0 with DFL authorization | CONDITIONAL, strongest candidate |
| Metrica Sports sample-data | Three pre-2022 anonymized sample matches; synchronized tracking/events; normalized coordinates on 105x68 pitch | Event annotations documented, not a qualified continuous H/A/D reference | Public sample use encouraged with attribution; reviewed README does not provide a complete formal data license | Not qualified; label/license gaps |
| SkillCorner opendata | Current README: ten 2024/25 Australian A-League matches; 10 Hz tracking, centre-origin metres, detected/extrapolated objects | Possession field and derived Game Intelligence/phases exist; independent annotation provenance not established | MIT repository license, credit requested; data-specific scope should be confirmed | Not qualified as independent truth; also 10-to-25 Hz mismatch |
| StatsBomb/Hudl open-data | Events, lineups and selected 360 snapshots across published competitions | Possession/event fields are not continuous tracking or frame-exact D | README allows public research and requests attribution/logo; full PDF license not interpreted here | Unsuitable for this tracking-model evaluation alone |
| PFF FC 2022 World Cup | Provider describes broadcast tracking/events/grades for all 64 games | Continuous controlled H/A/D semantics not verified from announcement | Access form; downstream rights/specifications require review | CONDITIONAL; no form submitted or terms accepted |
| SoccerTrack v2, Atom Scott et al. | Ten university matches; frame-aligned game-state reconstruction and ball-action annotations | No continuous H/A/D reference established; auxiliary ball track is event-anchored interpolation | Dataset card CC BY 4.0; gated contact-information conditions | Not qualified; gated access and reference/input-dependence risks |

Primary links:

- IDSSE paper: https://pmc.ncbi.nlm.nih.gov/articles/PMC11787359/
- IDSSE author repository/license: https://github.com/spoho-datascience/idsse-data
- Original versioned record: https://doi.org/10.6084/m9.figshare.28196177.v1
- Metadata API actually inspected: https://api.figshare.com/v2/articles/28196177
- Metrica: https://github.com/metrica-sports/sample-data
- SkillCorner: https://github.com/SkillCorner/opendata
- SkillCorner license: https://raw.githubusercontent.com/SkillCorner/opendata/master/LICENSE
- StatsBomb/Hudl: https://github.com/hudl/open-data
- PFF: https://www.blog.fc.pff.com/blog/pff-fc-release-2022-world-cup-data
- SoccerTrack: https://huggingface.co/datasets/atomscott/soccertrack-v2
- SoccerTrack project: https://atomscott.github.io/SoccerTrack-v2/

### IDSSE qualification details

The article describes controlled possession and inactive play following referee
interruptions, supplied speeds in km/h and coordinates in metres. Half and home/
away identity are available. Video is not included. Its frame-level status flags
are more suitable than reconstructing D from coarse event timestamps.

Figshare metadata confirmed v1 CC BY 4.0 and 21 XML files. Individual positional
files are 348,945,715–418,524,833 bytes. No asset files were fetched. The paper
describes trained event operators and tracking postprocessing, but does not
fully establish who assigns/checks every possession/status flag or their
uncertainty and restart-boundary rules. Do not equate manual event provenance
with verified manual frame-label provenance. Organizer inspection appears
feasible through the public release, subject to attribution.

Remaining gates are actual file coverage, annotation provenance, loose-ball and
legal-restart semantics, null/status meanings, exact half alignment and handling
of gaps. Secondary mirrors list differing match IDs; freeze the original DOI
version and file checksums rather than mixing mirror contents.

### Compatibility and independence safeguards

- IDSSE: verify coordinate origin/orientation from original schema, translate
  to the existing pitch convention, convert km/h to m/s, preserve real missing
  coordinates and ID/frame gaps. Resolve pitch dimensions against the frozen
  105.3x68 configuration before any scoring; do not silently rescale thresholds.
- Keep BallPossession/BallStatus solely in reference arrays. Never feed them
  into FrameEvidence or use them to generate model restart/context masks.
- Source human event annotations are not equivalent to noisy automatic Smart
  Tags. Feeding annotation-derived restart context into the candidate could
  contaminate the reference comparison. Missing automatic tags must be handled
  by a declared identical input policy for both candidates, with comparability
  limitations recorded before scores. No equivalent tag stream is established.
- SkillCorner's 10 Hz sampling conflicts with fixed 25 Hz motion/persistence
  assumptions. Interpolation is not a neutral conversion or independent truth.
- Metrica sample-game dates establish other-match independence, but anonymized
  identities and reference semantics still need provenance review.
- PFF World Cup and IDSSE German matches are independent of the target match.
  SoccerTrack university games also differ; left/right side labels still need
  actual home/away metadata. Do not map sides by guesswork.
- SoccerTrack ball interpolation incorporates annotated event timing. Evaluating
  event-derived truth against that input would not cleanly test observed ATD.
- StatsBomb 360 snapshots cannot supply continuous player/ball trajectories.
- For every source, missing reference annotation is ungraded/unknown, never D
  by default. A known inactive state may map to D only after its semantics pass.

## Approval/resource record

| Possible action | Purpose | Required decision | Alternative |
|---|---|---|---|
| Download one original IDSSE match, approximately 349–419 MB positional XML plus small metadata/events | Validate actual flags/units/coverage before an adapter | Explicit authorization for this large external acquisition and intended local storage | Complete Phase 6 without real-label ranking |
| Download all IDSSE tracking files | Multiple independent matches for external evaluation | Bulk-download/storage approval; semantic gate must pass first | Qualify one match first, do not download all by default |
| PFF application or SoccerTrack gated access | Review assets and detailed terms | User authorization for signup/contact sharing/terms; organizer accessibility review | Public documentation only |
| New other-game manual annotation | Create independent controlled-possession/D labels | Separate approval, lawfully accessible footage, named annotators, agreement process and scope | Do not annotate; no-data outcome |

No annotation project is authorized or started. No labor/compute cost estimate
is claimed. No provider messages were sent. This phase's no-data outcome is
complete; pending conditional sources do not block that completion.

## Evaluation requirements if a source later qualifies

This is a proposed protocol checklist, not an executed/finalized experiment:

1. Pin source version, license, hashes, independent match IDs and label provenance.
2. Freeze match/half spans, unknown masks, source timing, team mapping, dimension
   transforms, input availability and exclusions before inspecting predictions.
3. Compare exactly d24d5ae7b02488807ab7167494496c93152bbafa against
   35749fdf3652ba501cead2d61b96651232925164. Keep parameters frozen.
4. Do not feed reference flags/human events into inference as automatic evidence.
5. Preserve native 25 Hz physical timing if possible. Do not force external
   arrays to the competition's 199319-row length. Validate their own length/IDs.
6. Reuse evaluation.possession_metrics.evaluate on aligned arrays. Its spell
   score averages IoU thresholds .3/.4/.5/.6/.7; the Phase 4 .5 helper alone is
   not full spellF1. Scoring fills prediction X within each graded run for spells;
   macroF1 uses raw X as a miss on graded frames. Reference X excludes grading.
7. Separate halves explicitly; if concatenated, preserve an ungraded boundary.
   No spell or X fill may cross halves. Uncertain labels need explicit masks.
8. Before real scoring implement all requested T1–T12 toy tests: perfect H/A/D,
   D-separated same-team spells, direct turnover, merges/splits, offsets, all X
   policies, halves, index mismatch, team inversion, unknown reference and exact
   official scorer parity. Absent classes can yield zero class F1 in this scorer;
   a perfect H-only toy is not automatically macroF1=1.
9. Use match-level splits; repeated selection makes the source validation data.
   For one match, allow one prespecified descriptive frozen comparison without
   tuning, significance claims or misleading frame-independent confidence bounds.
10. Report per-match counts, missingness, D precision/recall, H/A confusion,
    matching at all thresholds, boundary distributions and annotation uncertainty.

## Execution and outcome

External adapter/scorer wrapper: NOT IMPLEMENTED, conditional gate not met.
T1–T12 external-adapter tests: NOT RUN; no adapter exists.
Frozen candidate comparison: NOT RUN — NO ADMISSIBLE OTHER-MATCH GROUND TRUTH
qualified in this workspace. Zero independent matches scored; accuracy remains
unmeasured. No pseudo-labels, synthetic scores or target-window scores substitute.

Documentation-only changes require existing regression/self-check verification.
Executed regression: `.venv/bin/python -B -m unittest discover -s starter_v6/tests
-p 'test*.py'` — 182 passed, zero failed/skipped/expected failures. This includes
HMM path arithmetic, runtime import isolation and Phase 0–4 regressions.
Executed `.venv/bin/python -B -m starter_v6.run_e04 --self-check` — passed.
Git comparisons verified no production/config/protected-directory changes.
FULL COMPETITION RUN NOT REPEATED — NO PRODUCTION CHANGES.
Preserved Phase 4 output hash:
d1604474717565a460d30bdef271d4e6e9b6c088c00bec84f6ef3d97a35f74ae.

G5.1/G5.2/G5.3: PASS for documented no-data feasibility outcome.
G5.4: NOT APPLICABLE — NO EXTERNAL EVALUATION PERFORMED.
Overall GO means the feasibility phase is complete, not accuracy validation.
Phase 6 may select conservatively using causal tests, determinism, format,
inspectability, simplicity and rollback preservation. Do not claim superiority.
IDSSE qualification is worthwhile if authorized within the remaining schedule;
it is a bounded follow-up, not a reason to postpone the November freeze forever.
