# C6 evidence and limits

## Recorded run evidence

The final local C6 artifacts are `.local-checkpoints/phase7/c6_e03_final_metadata.json` and `c6_e03_final_diagnostics.json` within the competition repository. They record 199,319 emissions, 33,180 informative and 166,139 uninformative, zero invalid emissions, and 638 Smart Tagging events. Diagnostics state `ground_truth.used: false`; these are integrity and implementation-behavior observations, not accuracy measures.

The recorded final run identifies source revision `61a1e874e83b6911b5ab9cd39e9f994a51d78db9`, config hash `160af03c…`, and output hash `b0cc82f9…`. The commit is locally present and the current `starter_v5/` tree matched that revision at audit. Earlier artifacts point to a different E02 revision; use the final-named artifacts for the C6 run lineage and retain this discrepancy when interpreting historical records.

Tag diagnostics report 638 events, normalized team totals H=314, A=288, N/A=36. Paired E02/E03 diagnostics found no changed emission argmax or final labels in that run, while team-evidence confidence changed on 232 frames. Counts describe the implementation and are not evidence of prediction correctness.

## Provenance

Sources: `.local-checkpoints/phase7/c6_e03_final_metadata.json`, `.local-checkpoints/phase7/c6_e03_final_diagnostics.json`, and `starter_v5/emissions.py`. Hashes are abbreviated here for lookup; authoritative full hashes remain in the local metadata. No licensed frame data was copied. Graph provenance unavailable because the project had no `graphify-out/graph.json` during curation.
