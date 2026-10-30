"""E02 soft team evidence and conservative temporal decoding, including corroborated gap changes."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, Iterator, List, Optional, Tuple

from starter_v4.features import E02Config, FrameFeatures, iter_frame_features
from starter_v4.possession import (
    DeadBallObservation,
    FrameEvidence,
    FrameInference,
    PossessionConfig,
    TeamObservation,
    observe_dead_ball,
)
from starter_v5.tag_features import TagEvidence
from starter_v5.emissions import FrameEmission, frame_emission


@dataclass(frozen=True)
class E02FrameInference:
    inference: FrameInference
    features: FrameFeatures
    emission: FrameEmission
    tag_relation: str = "none"
    gap_decision: str = "none"
    gap_decision_reason: str = "none"


def _team_evidence(features: FrameFeatures, config: PossessionConfig, quality: E02Config,
                   tag: Optional[TagEvidence] = None) -> TeamObservation:
    """Combine observed-ball proximity, top-k geometry, density, and quality as soft evidence."""
    if not features.quality.ball_observed:
        return TeamObservation(False, None, 0.0, None, None, None)
    spatial = features.spatial
    scores = {"H": 0.0, "A": 0.0}
    distances = {"H": spatial.nearest_home_m, "A": spatial.nearest_away_m}
    topk = {"H": spatial.topk_home_mean_m, "A": spatial.topk_away_mean_m}
    density = {"H": spatial.density_home, "A": spatial.density_away}
    for team in ("H", "A"):
        if distances[team] is None:
            continue
        nearest_score = max(0.0, min(1.0, 1.0 - distances[team] / config.control_radius_m))
        topk_score = max(0.0, min(1.0, 1.0 - topk[team] / (2.0 * config.control_radius_m)))
        density_score = min(density[team], quality.top_k) / float(quality.top_k)
        scores[team] = 0.55 * nearest_score + 0.25 * topk_score + 0.20 * density_score

    if distances["H"] is None and distances["A"] is None:
        best_team, confidence = None, 0.0
    elif distances["H"] is None:
        best_team = "A"
        separation = 1.0
        confidence = 0.5 * (max(0.0, 1.0 - distances[best_team] / config.control_radius_m) + separation)
    elif distances["A"] is None:
        best_team = "H"
        separation = 1.0
        confidence = 0.5 * (max(0.0, 1.0 - distances[best_team] / config.control_radius_m) + separation)
    else:
        best_team = "H" if distances["H"] <= distances["A"] else "A"
        other = "A" if best_team == "H" else "H"
        distance_margin = abs(distances["H"] - distances["A"])
        separation = max(0.0, min(1.0, distance_margin / config.min_team_margin_m))
        proximity = max(0.0, min(1.0, 1.0 - distances[best_team] / config.control_radius_m))
        confidence = 0.5 * (proximity + separation)
        if distance_margin < config.min_team_margin_m:
            best_team = None
            # A matching weak phase prior may resolve a close observed-ball contest, but
            # never creates control in the absence of player/ball geometry.
            candidate = "H" if distances["H"] <= distances["A"] else "A"
            prior = (tag.home_prior if candidate == "H" else tag.away_prior) if tag is not None else 0.0
            if tag is not None and not tag.team_conflict and prior > 0 and proximity >= 0.5:
                best_team = candidate
                confidence = max(confidence, min(1.0, config.min_observation_confidence * 2.0))

        # Top-k distance and team density refine the observed-ball signal; they cannot replace it.
        contextual_margin = scores[best_team] - scores[other] if best_team is not None else 0.0
        confidence += 0.1 * max(-1.0, min(1.0, contextual_margin))

    if best_team is not None and distances[best_team] is not None:
        if distances[best_team] > config.control_radius_m:
            best_team = None
    if best_team is not None:
        comotion = features.motion.home_ball_comotion if best_team == "H" else features.motion.away_ball_comotion
        if comotion is not None:
            confidence += 0.05 * max(-1.0, min(1.0, comotion))
    confidence = max(0.0, min(1.0, confidence * features.quality.confidence_weight))
    if features.spatial.contested:
        confidence *= 0.8
    if confidence < config.min_observation_confidence:
        best_team = None

    margin = None
    if distances["H"] is not None and distances["A"] is not None:
        margin = distances["A"] - distances["H"]
    return TeamObservation(
        features.quality.ball_observed,
        best_team,
        confidence,
        distances["H"],
        distances["A"],
        margin,
    )


def _result(features: FrameFeatures, label: str, team: TeamObservation, dead: DeadBallObservation,
            tag: Optional[TagEvidence] = None) -> E02FrameInference:
    if dead.confirmed:
        emission = frame_emission(features.frame.frame, features.frame.half,
                                  dead= max(dead.confidence, 1.0 if dead.hard_evidence else 0.0),
                                  informative=True)
    elif team.team == "H":
        emission = frame_emission(features.frame.frame, features.frame.half,
                                  home=max(team.confidence, 1e-12), away=max(1.0-team.confidence, 1e-12),
                                  informative=True)
    elif team.team == "A":
        emission = frame_emission(features.frame.frame, features.frame.half,
                                  home=max(1.0-team.confidence, 1e-12), away=max(team.confidence, 1e-12),
                                  informative=True)
    else:
        emission = frame_emission(features.frame.frame, features.frame.half)
    relation = "none"
    if tag is not None and tag.active:
        if tag.team_conflict:
            relation = "conflict_neutralized"
        elif tag.team_prior is None:
            relation = "unknown_owner"
        elif team.team == tag.team_prior:
            relation = "agreement"
        elif team.team is None and team.ball_observed:
            relation = "uncertain_no_resolution"
        else:
            relation = "contradiction"
    return E02FrameInference(FrameInference(features.frame.frame, features.frame.half, label, team, dead),
                             features, emission, relation)


def _resolve_gap(
    pending: List[E02FrameInference],
    accepted_team: Optional[str],
    support_start: Optional[int],
    attempted: bool,
    decision_reason: str,
) -> List[E02FrameInference]:
    resolved = []
    decision = "accepted" if accepted_team is not None else ("rejected" if attempted else "none")
    for index, item in enumerate(pending):
        label = item.inference.label
        if accepted_team is not None and support_start is not None and index >= support_start:
            label = accepted_team
        inference = replace(item.inference, label=label)
        resolved.append(replace(
            item,
            inference=inference,
            gap_decision=decision if index == 0 else "none",
            gap_decision_reason=decision_reason if index == 0 else "none",
        ))
    return resolved


def _gap_rejection_reason(
    pending: List[E02FrameInference], support_count: int, config: E02Config, attempted: bool
) -> str:
    if not attempted:
        return "none"
    if len(pending) > config.gap_max_frames:
        return "gap_exceeded_limit"
    if support_count < config.gap_support_frames:
        return "insufficient_consecutive_gap_support"
    return "opposing_post_gap_control_not_confirmed"


def iter_infer_e02(
    frames: Iterable[FrameEvidence],
    possession_config: PossessionConfig = PossessionConfig(),
    feature_config: E02Config = E02Config(),
    tag_evidence: Optional[Iterable[TagEvidence]] = None,
) -> Iterator[E02FrameInference]:
    """Infer a sequence without filling missing coordinates; only confirmed gaps can be revised."""
    state = "X"
    previous_half: Optional[int] = None
    previous_frame: Optional[int] = None
    missing_count = uncertain_count = 0
    candidate_team: Optional[str] = None
    candidate_count = dead_candidate_count = 0
    pending_gap: List[E02FrameInference] = []
    pending_recovery: List[E02FrameInference] = []
    gap_prior_state: Optional[str] = None
    gap_support_team: Optional[str] = None
    gap_support_count = 0
    gap_support_start: Optional[int] = None
    gap_attempted = False
    maximum_buffered_gap = min(feature_config.gap_max_frames, possession_config.max_missing_frames)

    tags = iter(tag_evidence) if tag_evidence is not None else None
    for features in iter_frame_features(frames, feature_config):
        tag = next(tags) if tags is not None else None
        frame = features.frame
        if previous_frame is not None and frame.frame != previous_frame + 1:
            raise ValueError("frames must be contiguous and ordered")
        previous_frame = frame.frame
        if previous_half is not None and frame.half != previous_half:
            yield from _resolve_gap(
                pending_gap, None, None, gap_attempted,
                _gap_rejection_reason(pending_gap, gap_support_count, feature_config, gap_attempted),
            )
            yield from pending_recovery
            pending_gap.clear()
            pending_recovery.clear()
            state = "X"
            missing_count = uncertain_count = candidate_count = dead_candidate_count = 0
            candidate_team = None
            gap_prior_state = gap_support_team = None
            gap_support_count = 0
            gap_support_start = None
            gap_attempted = False
        previous_half = frame.half

        team = _team_evidence(features, possession_config, feature_config, tag)
        raw_dead = observe_dead_ball(frame, team, possession_config)
        if frame.half == 0:
            yield from _resolve_gap(
                pending_gap, None, None, gap_attempted,
                _gap_rejection_reason(pending_gap, gap_support_count, feature_config, gap_attempted),
            )
            yield from pending_recovery
            pending_gap.clear()
            pending_recovery.clear()
            state = "X"
            missing_count = uncertain_count = candidate_count = dead_candidate_count = 0
            candidate_team = None
            gap_prior_state = gap_support_team = None
            gap_support_count = 0
            gap_support_start = None
            gap_attempted = False
            yield _result(features, "X", team, DeadBallObservation(raw_dead.cues, raw_dead.confidence, False, raw_dead.hard_evidence), tag)
            continue

        if raw_dead.hard_evidence:
            confirmed_dead = True
            dead_candidate_count = 0
        elif raw_dead.cues:
            dead_candidate_count += 1
            confirmed_dead = dead_candidate_count >= possession_config.deadball_confirm_frames
        else:
            dead_candidate_count = 0
            confirmed_dead = False
        dead = DeadBallObservation(raw_dead.cues, raw_dead.confidence, confirmed_dead, raw_dead.hard_evidence)

        if confirmed_dead:
            yield from _resolve_gap(
                pending_gap, None, None, gap_attempted,
                _gap_rejection_reason(pending_gap, gap_support_count, feature_config, gap_attempted),
            )
            yield from pending_recovery
            pending_gap.clear()
            pending_recovery.clear()
            gap_prior_state = gap_support_team = None
            gap_support_count = 0
            gap_support_start = None
            gap_attempted = False
            state = "D"
            missing_count = uncertain_count = candidate_count = 0
            candidate_team = None
            yield _result(features, "D", team, dead, tag)
            continue

        # Observed recovery separates a new missing interval from an unresolved old transition.
        # Flush the prior interval before buffering any later gap, preserving frame order.
        if not team.ball_observed and pending_gap and pending_recovery:
            yield from _resolve_gap(
                pending_gap, None, None, gap_attempted,
                _gap_rejection_reason(pending_gap, gap_support_count, feature_config, gap_attempted),
            )
            yield from pending_recovery
            pending_gap.clear()
            pending_recovery.clear()
            gap_prior_state = gap_support_team = None
            gap_support_count = 0
            gap_support_start = None
            gap_attempted = False

        if not team.ball_observed:
            if not pending_gap:
                gap_prior_state = state if state in {"H", "A"} else None
                gap_support_team = None
                gap_support_count = 0
                gap_support_start = None
                gap_attempted = False
            missing_count += 1
            uncertain_count = candidate_count = 0
            candidate_team = None
            if missing_count > possession_config.max_missing_frames:
                state = "X"
            label = state if state in {"H", "A"} else "X"
            pending_gap.append(_result(features, label, team, dead, tag))

            opposing_team = "A" if gap_prior_state == "H" else "H" if gap_prior_state == "A" else None
            gap_support_ok = (
                opposing_team is not None
                and missing_count <= min(feature_config.gap_max_frames, possession_config.max_missing_frames)
                and features.motion.gap_candidate_team == opposing_team
                and features.quality.confidence_weight >= feature_config.gap_min_quality_weight
                and not features.quality.low_player_coverage
                and not features.quality.implausible_ball_jump
                and not features.quality.ball_speed_inconsistent
            )
            if gap_support_ok:
                gap_attempted = True
                if gap_support_team == opposing_team:
                    gap_support_count += 1
                else:
                    gap_support_team = opposing_team
                    gap_support_count = 1
                    gap_support_start = len(pending_gap) - 1
            else:
                gap_support_team = None
                gap_support_count = 0
                gap_support_start = None
            if len(pending_gap) > maximum_buffered_gap:
                yield from _resolve_gap(
                    pending_gap,
                    None,
                    None,
                    gap_attempted,
                    "gap_exceeded_limit" if gap_attempted else "none",
                )
                pending_gap.clear()
                gap_support_team = None
                gap_support_count = 0
                gap_support_start = None
                gap_attempted = False
            continue

        missing_count = 0
        if team.team is None:
            uncertain_count += 1
            candidate_count = 0
            candidate_team = None
            if uncertain_count > possession_config.max_uncertain_frames:
                state = "X"
            label = state if state in {"H", "A"} else "X"
            result = _result(features, label, team, dead, tag)
        else:
            uncertain_count = 0
            observed_team = team.team
            if observed_team == state:
                candidate_team = None
                candidate_count = 0
            elif observed_team == candidate_team:
                candidate_count += 1
            else:
                candidate_team = observed_team
                candidate_count = 1
            if observed_team != state and candidate_count >= possession_config.acquire_frames:
                state = observed_team
                candidate_team = None
                candidate_count = 0
            label = state if state in {"H", "A"} else "X"
            result = _result(features, label, team, dead, tag)

        if pending_gap:
            opposing_team = "A" if gap_prior_state == "H" else "H" if gap_prior_state == "A" else None
            if team.team == opposing_team and state == opposing_team:
                accepted_team = None
                if (
                    gap_support_count >= feature_config.gap_support_frames
                    and gap_support_team == opposing_team
                    and gap_support_start is not None
                    and len(pending_gap) <= feature_config.gap_max_frames
                    and len(pending_gap) <= possession_config.max_missing_frames
                ):
                    accepted_team = opposing_team
                reason = (
                    "opposing_motion_and_recovery_confirmed"
                    if accepted_team is not None
                    else _gap_rejection_reason(pending_gap, gap_support_count, feature_config, gap_attempted)
                )
                yield from _resolve_gap(
                    pending_gap, accepted_team, gap_support_start, gap_attempted, reason
                )
                if accepted_team is not None:
                    yield from (
                        replace(item, inference=replace(item.inference, label=accepted_team))
                        for item in pending_recovery
                    )
                else:
                    yield from pending_recovery
                yield result
                pending_gap.clear()
                pending_recovery.clear()
                gap_prior_state = gap_support_team = None
                gap_support_count = 0
                gap_support_start = None
                gap_attempted = False
            elif team.team == opposing_team and state != opposing_team:
                pending_recovery.append(result)
            else:
                yield from _resolve_gap(
                    pending_gap, None, None, gap_attempted,
                    _gap_rejection_reason(pending_gap, gap_support_count, feature_config, gap_attempted),
                )
                yield from pending_recovery
                pending_gap.clear()
                pending_recovery.clear()
                gap_prior_state = gap_support_team = None
                gap_support_count = 0
                gap_support_start = None
                gap_attempted = False
                yield result
        else:
            yield result

    yield from _resolve_gap(
        pending_gap, None, None, gap_attempted,
        _gap_rejection_reason(pending_gap, gap_support_count, feature_config, gap_attempted),
    )
    yield from pending_recovery
