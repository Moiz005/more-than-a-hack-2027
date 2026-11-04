# Competition and data constraints

## Stable contract

- Submission timeline is the tactical video: 25 FPS, 199,319 frames, zero-based `0..199318`; output CSV header is `frame,label`.
- Labels are `H`, `A`, `D`, `X`. `X` is abstention, not a fourth ground-truth state.
- Official graded blocks are inclusive: `11185..90651` and `110808..190197` (158,857 frames total). Decode or carry temporal state independently by half; ungraded spans must not bridge halves.
- Tracking frame IDs are one-based and convert to submission indices by subtracting one. Smart Tagging times are seconds from tactical-video start and are converted at 25 FPS. Broadcast timeline is unsynchronized.
- Live possession persists through loose/contested moments until controlled turnover or stoppage. Missing ball does not imply `D`; a stoppage splits otherwise same-team spells.
- Public ground truth covers only the first five minutes and is allowed for pipeline/alignment checks, not fitting, threshold/window tuning, ranking, or selecting approaches.
- Do not hand-correct provided-match frames or use external private labels/corrected tracking. Licensed assets and reconstructive derivatives stay local and out of commits.

## Provenance

Repository-backed sources: `project.md` task/output/evaluation/rules sections; `more-than-a-hack-2027/games.py`; official `DATA.md`, `RULES.md`, `EVALUATION.md`, `SUBMISSION.md`; root `AGENTS.md`. Graph provenance unavailable: no `graphify-out/graph.json` existed at curation time; topics were derived from these canonical docs.
