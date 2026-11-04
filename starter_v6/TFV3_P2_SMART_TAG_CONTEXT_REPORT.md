# TacticalFusion P2 Smart Tag context report

## Decision and gate

G2 PASS. Existing E04 tag priors remain the sole path by which tags influence
inference. The adapter adds traceable context metadata, not additional votes.
No target-match assets or public labels were used; the local data bundle is
unavailable, so asset-specific inventories are unverified here.

## Contract changes

The existing parser and `iter_tag_evidence()` remain authoritative for XML,
frame rounding, and half-open ranges. `TagEvidence` now carries all recognized
restart types, original Team values (including `N/A`), Half values, the union
interval for active annotations, deterministic overlap-group identity, and
tag-code provenance. Team priors remain capped at one unit per side. Competing
teams neutralize both priors. Restart type does not infer owner. Half remains
metadata only. Duplicate overlapping tags do not amplify a prior.

Tag evidence still enters `_team_evidence()` only as weak context for resolving
close observed geometry. `_result()` records tag relation but does not convert
tags to labels. Restart/goal tags without ATD evidence cannot force DEAD or an
execution timestamp. Feature-off continues to omit tag evidence as before.

## Incremental information

The inference contribution is intentionally unchanged: there is no new
independent prediction functionality. The additive value is auditability for
later phases: typed source team, all simultaneous restart types, half metadata,
interval uncertainty bounds, overlap grouping, and provenance survive
aggregation. These fields do not imply legal play state, possession owner, or
physical restart timing.

## Synthetic verification

`starter_v6.tests.test_tag_features` covers absent and N/A fields, all six
restart types, Half metadata, competing teams, duplicate/overlapping
annotations, bounded priors, half-open intervals, tag-only non-forcing of DEAD,
and contradiction against clear geometry. Test results and complete regression
counts are recorded in the phase handoff; synthetic outcomes are not accuracy
claims.
