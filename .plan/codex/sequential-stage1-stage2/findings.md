# Findings — Sequential Stage 1 → Stage 2

## Source context

- Canonical implementation is `starter_v6/` on `experiment/e04-v3-visual-possession`.
- `iter_infer_e02()` previously combined lifecycle and team ownership. Its live-recovery gate required `team.team` and therefore coupled LIVE/DEAD with H/A ownership.
- `StatefulDeadBallDetector`, `confirm_dead_ball`, Smart Tag restart context, and runtime restart-action detection can be reused when Stage 1 receives a neutral `TeamObservation`.
- The existing ownership code can be reused for LIVE-only segments if dead-ball observation/confirmation and lifecycle restart transitions are disabled in that invocation.
- The existing half-boundary policy accepts confirmed, estimated, or frame-resolvable bounded kickoff evidence and rejects unsupported/frame-less values. Applying it before segmentation routes the resulting DEAD prefix away from Stage 2.
- The protected exact-v3 release hash is `d1604474717565a460d30bdef271d4e6e9b6c088c00bec84f6ef3d97a35f74ae`; the current `exact_v3` runner reproduced it.

## Implementation decisions

- Keep `stage1_then_stage2` opt-in; the existing `exact_v3` runner path retains its three-state per-half decode.
- Stage 1 does not invoke the H/A proposal helper. It uses neutral team evidence, observed motion, either-team proximity, and tracking quality for live recovery.
- Stage 2 runs separately on each contiguous LIVE segment with its dead-ball detector disabled. Its emission contract is H/A-only and the H/A decoder flushes on frame gaps, half changes, and non-LIVE rows.
- Compose the fixed Stage 1 DEAD and official UNGRADED/X masks with H/A ownership. Validate ownership coverage equals exactly the LIVE frame set.
- HBK-01 opening-kickoff evidence is evaluated before Stage 2 and passed through the established fail-closed prefix policy.

## Safety and interpretation

- Public five-minute evaluation is for one-candidate pipeline/alignment verification only; it is not tuning, ranking, or promotion evidence.
- Match-level labels, frame traces, detector windows, and generated CSVs remain in ignored local storage. Knowledge records include aggregate counts only.
- Full-match possession quality and private metrics remain unknown without independent authorized labels.
