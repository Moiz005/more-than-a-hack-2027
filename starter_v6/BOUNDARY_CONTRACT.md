# HBK-01 Boundary Contract

Status: Phase 1 contract. This document defines the behavior that later HBK-01
code must implement; it does not claim a detector, a target-match kickoff
time, or an accuracy improvement.

## 1. Scope and source authority

HBK-01 is an opt-in, tactical-only post-decoding layer around the unchanged
starter_v6 E04/V3 runner. It may change only the second-half pre-kickoff
prefix when a kickoff execution frame is independently confirmed from
quality-aware tactical observations.

The submission timeline is the tactical video. The official graded ranges are
provided by the existing timeline contract (games.half_video_blocks("BAR-ATH")
and starter_v6.timeline.build_tactical_timeline); HBK-01 code must read those
ranges rather than duplicate match-specific literals in inference logic.

The source conventions are:

- Video/submission frames are zero-based.
- ATD frame_id is one-based and maps to video_frame = frame_id - 1.
- Tactical video runs at 25 FPS; a diagnostic timestamp is video_frame / 25.
- Smart Tag intervals use rounded frame conversion and half-open bounds
  [start_frame, end_frame).
- X means outside a published graded range. It is not a claim that play is
  legally dead.
- Within a graded range, D means the ball is not legally in play and H/A mean
  live possession by the existing parent decoder.

Smart Tagging SET PIECES / Type = Kick Off (Start) is contextual search
evidence only. Its timestamp, five-second duration, end frame, Team = N/A,
or presence alone never establishes a legal LIVE/DEAD transition or a team
owner. Kick Off (After Goal) is outside this opening-kickoff contract.

## 2. Four-boundary policy

The policy considers exactly these boundaries:

| Boundary | Frames affected | HBK-01 behavior |
| --- | --- | --- |
| First-half graded start | first graded frame of half 1 | Preserve the parent H/A/D result. First-half kickoff detection is diagnostic only; do not invent a pre-grade D interval. |
| First-half graded end | first ungraded frame after half 1 | Preserve the last parent graded label. The first ungraded frame is X; do not infer an exact whistle frame. |
| Second-half graded start / opening kickoff | second-half graded start through execution frame | If and only if execution is CONFIRMED, overlay D on the half-open prefix [graded_start, kickoff_execution_frame). Preserve the parent label at kickoff_execution_frame and after it. |
| Second-half graded end | first ungraded frame after half 2 | Preserve the last parent graded label. The first post-match frame is X; do not infer an exact whistle frame. |

The legal opening-kickoff execution frame is the first zero-based tactical
frame where a credible observed kick makes the ball clearly move. It is not
the tag boundary, referee signal, camera movement, player movement, stationary
centre-mark setup, or an automatically selected frame after a fixed delay.

### 2.1 Exact overlay contract

Let s2 = second_half.graded_start and let k2 be a confirmed execution frame.
The only permitted label mutation is:

    for frame in range(s2, k2):
        result[frame] = "D"

The following must hold before an overlay is accepted:

- s2 < k2 <= second_half.graded_end.
- result[k2] and every later graded second-half label equal the parent E04
  output.
- Every first-half label equals the parent E04 output.
- Every ungraded frame remains X according to the official timeline mask.
- The terminal graded frame of each half remains the parent label.
- A confirmed kickoff does not select H or A; owner assignment remains the
  parent E04 responsibility.
- A parent D at or after k2 is retained and reported as post_kickoff_D, not
  silently changed.

If k2 is missing, ambiguous, unsupported, out of range, or fails alignment,
the overlay is rejected. Audit output may still describe the failure, but no
modified submission may be written and no fixed-duration D prefix may be
guessed.

## 3. Detector statuses and severity

The detector and candidate selector use these stable status names:

| Status | Meaning | Overlay effect |
| --- | --- | --- |
| CONFIRMED | Exactly one candidate satisfies the prescribed quality and continuity evidence, with a valid aligned execution frame. | Eligible for the second-half prefix only. |
| AMBIGUOUS | Two or more candidates remain materially plausible, or a deterministic quality rule cannot separate them. | Audit only; no overlay. |
| INSUFFICIENT_EVIDENCE | The candidate window lacks enough valid consecutive observations to establish a kick. | Audit only; no overlay. |
| MISSING_TAG | No usable opening Kick Off (Start) candidate exists for the requested half. | Audit only; no overlay. |
| INVALID_ALIGNMENT | Frame mapping, half association, bounds, or source/timeline contract is invalid. | Hard failure; no overlay or modified CSV. |

INVALID_ALIGNMENT is a failed run condition. Every unconfirmed second-half
result is audit-only and must fail closed. First-half status may be reported,
but it never authorizes a first-half label mutation.

## 4. Diagnostic contract

Diagnostics must call the mask boundaries graded_start and graded_end.
They must not call them whistle times, match-clock times, or inferred legal
restart times.

For every half/candidate, diagnostics should preserve:

- raw tag bounds and rounded half-open frame bounds;
- half association and search-window bounds;
- detector status and evidence/rejection reason codes;
- kickoff_execution_frame when confirmed;
- video-relative timestamp kickoff_execution_frame / 25 seconds;
- whether the first-half result was diagnostic-only;
- hypothetical/actual second-half prefix bounds and length;
- post_kickoff_D count in any explicitly bounded audit window;
- alignment and preservation assertions.

The timestamp is relative to the tactical video file. It must not be described
as the football match clock, wall-clock time, or a manually observed kickoff.

## 5. Submission invariants

For a full synthetic or real-data submission, the contract requires:

1. Exactly 199319 rows after the header.
2. Header exactly frame,label.
3. Frame values ordered from 0 through 199318, once each.
4. Labels limited to H, A, D, and X.
5. Ungraded frames are X:
   - pre-match frames 0..11184;
   - halftime frames 90652..110807;
   - post-match frames 190198..199318.
6. Graded frames contain no X:
   - first half 11185..90651;
   - second half 110808..190197.
7. The first-half parent output is unchanged.
8. The second-half parent output is unchanged from k2 onward.
9. If no second-half execution is confirmed, an overlay run writes no modified
   CSV.

The exact ranges above are the published BAR-ATH contract for this experiment;
runtime code must obtain them from the existing timeline implementation.

## 6. Synthetic acceptance oracle

All acceptance examples below are invented. They are deliberately small and
use synthetic half ranges half_1 = 100..159, halftime = 160..199, and
half_2 = 200..259 to test boundary behavior without target-match timing.
The parent labels in the examples are arbitrary valid H/A/D/X sequences.

| Case | Invented input | Required result |
| --- | --- | --- |
| Setup before kickoff | Tag window [90,110); ball is reliable and centre-near/stationary at frames 100–104; no movement follows. | No execution frame. Status is INSUFFICIENT_EVIDENCE; never infer LIVE or overlay D. |
| Delayed execution | Tag window [205,215); credible setup at 207–209; first valid continuous displacement begins at 214. | kickoff_execution_frame = 214; overlay only [200,214) for a confirmed second-half result; frame 214 keeps the parent label. |
| Tag endpoint is not execution | Tag window [205,210); setup continues through 212; movement begins at 213. | Select 213 if quality evidence confirms it, not tag end 210 and not a fixed delay from 210. |
| Noisy one-frame spike | Centre-near setup, one implausible displacement at 218, then stationary/missing observations. | No confirmation; status INSUFFICIENT_EVIDENCE or AMBIGUOUS according to the specified quality result, never a guessed kick. |
| Missing ball during setup | Valid centre setup at 205–207, ball missing at 208–210, no valid post-gap consecutive movement. | No confirmation; missingness is not motion and is not DEAD evidence. |
| Missing provider speed only | Valid consecutive ball positions with physically plausible displacement at 220–222; provider speed absent. | Speed absence does not invalidate position-based motion when all other quality gates pass. |
| Multiple kicks | Two plausible movement starts inside one candidate search window, neither deterministically higher quality. | Preserve both candidates and return AMBIGUOUS; never choose the first or closest to an external timestamp. |
| Tag outside half | Opening tag overlaps the ungraded region before half_1 but its search window associates with half 1. | Candidate may be retained for diagnostic selection; no pre-grade D is written and frame 99 remains X. |
| Wrong-half tag | A tag claims half 1 but its validated position falls in synthetic halftime or half 2. | Preserve the record with a warning and reject it for the claimed half; do not silently reassign it. |
| Distinct half boundaries | Parent has D at frame 159 and A at frame 259. | Frame 160 and every halftime frame are X; frame 260 is X; terminal graded labels 159/259 remain unchanged. |
| First-half kickoff | Confirmed synthetic first-half execution at 108. | Emit diagnostic timestamp and status only; all first-half parent labels remain unchanged. |
| Confirmed prefix | Second-half start 200, confirmed execution 214, parent labels A at 200–213 and H at 214. | Output is D at 200–213, H at 214, and the parent suffix thereafter. Changed-frame support is exactly [200,214). |
| Already-D prefix | Parent already has D at 200–213 and confirmed execution 214. | Return explicit no_change provenance; do not claim an improvement. |
| Out-of-range execution | Candidate execution is 199 or 260. | INVALID_ALIGNMENT/rejected overlay; no modified CSV. |

The oracle must also check that synthetic records are not mutated, selection is
deterministic, no observation gap is bridged as measured velocity, and the
detector does not depend on absolute match frame numbers.

## 7. False-positive and false-negative controls

### 7.1 False positives to reject

- Treating a Smart Tag start/end or Team = N/A as a kick or owner.
- Treating a stationary centre-mark ball as proof that play has started.
- Treating a missing ball, zero speed, or absent provider speed as either a
  kick or a legal dead-ball transition.
- Treating a player run, camera movement, formation reset, or centre-circle
  departure as ball execution without credible ball motion.
- Triggering on a single noisy position jump, an impossible speed, or a motion
  event separated from setup by an unobserved gap.
- Selecting an arbitrary first/closest candidate when multiple candidates
  conflict.
- Writing D outside the confirmed second-half prefix, during halftime, before
  the first-half grade, or after the confirmed execution frame.
- Converting kickoff context into H/A ownership or repairing parent
  post-kickoff D labels within this experiment.

### 7.2 False negatives to distinguish

- Rejecting a genuine subtle kick merely because provider ball speed is missing,
  when consecutive valid positions and physical displacement are sufficient.
- Rejecting a genuine kick because the Smart Tag window starts before the first
  graded frame or ends before the actual execution.
- Requiring the second-half candidate to occur within a short fixed interval
  after graded_start.
- Requiring all 22 players, fixed track-slot identities, or a complete
  formation to be visible.
- Using the final confirmation frame instead of the first eligible movement
  frame.
- Treating a valid first-half diagnostic as permission to change first-half
  output.

These are test obligations, not tuning instructions. Thresholds and quality
rules must remain untuned engineering hypotheses until later synthetic phases
define them and no public target-match labels may be used to choose them.

## 8. Phase 1 acceptance checklist

- A reviewer can identify the only permitted mutation interval as the confirmed
  second-half half-open prefix [graded_start, kickoff_execution_frame).
- A reviewer can explain why first-half kickoff detection is diagnostic-only.
- Every unconfirmed/invalid second-half result fails closed without a modified
  CSV.
- Synthetic examples cover setup-before-kick, delayed execution, noisy spike,
  missing ball, multiple kicks, tag-boundary mismatch, wrong-half association,
  and distinct half boundaries.
- No case uses a real-match kickoff frame, public ground truth, human label, or
  an externally supplied target timestamp.
