"""E02 soft team evidence and conservative temporal decoding, including corroborated gap changes."""

from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import tee
import math
from typing import Iterable, Iterator, List, Optional, Tuple

from starter_v6.features import E02Config, FrameFeatures, iter_frame_features
from starter_v6.atd_signals import AtdSignalConfig, AtdSignals, iter_atd_signals
from starter_v6.contracts import Evidence, EvidenceSource, FrameReference
from starter_v6.possession import (
    DeadBallObservation,
    FrameEvidence,
    FrameInference,
    PossessionConfig,
    PlayStateHypothesis,
    TeamObservation,
    StatefulDeadBallDetector,
    confirm_dead_ball,
    finalize_dead_ball,
)
from starter_v6.tag_features import TagEvidence
from starter_v6.emissions import FrameEmission, fuse_evidence


@dataclass(frozen=True)
class E02FrameInference:
    inference: FrameInference
    features: FrameFeatures
    emission: FrameEmission
    tag_relation: str = "none"
    gap_decision: str = "none"
    gap_decision_reason: str = "none"
    ownership_evidence: Optional["GapOwnershipEvidence"] = None
    atd_signals: Optional[AtdSignals] = None
    tag_context: Optional[TagEvidence] = None
    evidence: Tuple[Evidence, ...] = ()
    control_hypothesis: Optional["ControlHypothesis"] = None
    control_transition: Optional["ControlTransition"] = None
    play_state_hypothesis: Optional[PlayStateHypothesis] = None


@dataclass(frozen=True)
class ControlHypothesis:
    """Per-frame team-control proposal; UNKNOWN is internal, never an output label."""

    status: str
    team: Optional[str]
    confidence: float
    evidence_groups: Tuple[str, ...]
    quality_flags: Tuple[str, ...]

    def __post_init__(self) -> None:
        if self.status not in {"H", "A", "UNKNOWN"}:
            raise ValueError("control hypothesis status must be H, A, or UNKNOWN")
        if self.team not in {None, "H", "A"}:
            raise ValueError("control hypothesis team must be H, A, or absent")
        if (self.status == "UNKNOWN") != (self.team is None):
            raise ValueError("UNKNOWN status and absent control team must agree")
        if (isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float))
                or not math.isfinite(self.confidence) or not 0.0 <= self.confidence <= 1.0):
            raise ValueError("control hypothesis confidence must be finite and in [0, 1]")
        if not isinstance(self.evidence_groups, tuple) or not isinstance(self.quality_flags, tuple):
            raise ValueError("control hypothesis provenance and flags must be tuples")


@dataclass(frozen=True)
class ControlTransition:
    """Accepted temporally supported change in the internal live-team owner."""

    from_team: str
    to_team: str
    start_frame: int
    end_frame: int
    support_frames: int
    confidence: float
    accepted: bool
    reason: str

    def __post_init__(self) -> None:
        if self.from_team not in {"H", "A", "UNKNOWN"} or self.to_team not in {"H", "A"}:
            raise ValueError("control transition teams must be H, A, or UNKNOWN-to-H/A")
        if self.from_team == self.to_team:
            raise ValueError("control transition must change the owner")
        if (isinstance(self.start_frame, bool) or isinstance(self.end_frame, bool)
                or not isinstance(self.start_frame, int) or not isinstance(self.end_frame, int)
                or self.start_frame < 0 or self.end_frame < self.start_frame):
            raise ValueError("control transition frame interval is invalid")
        if (isinstance(self.support_frames, bool) or not isinstance(self.support_frames, int)
                or self.support_frames < 1):
            raise ValueError("control transition support_frames must be positive")
        if (isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float))
                or not math.isfinite(self.confidence) or not 0.0 <= self.confidence <= 1.0):
            raise ValueError("control transition confidence must be finite and in [0, 1]")
        if not isinstance(self.accepted, bool) or not self.reason:
            raise ValueError("control transition must record acceptance and a reason")


@dataclass(frozen=True)
class GapOwnershipEvidence:
    prior_team: Optional[str]
    recovered_team: Optional[str]
    direction: str
    start_frame: int
    end_frame: int
    support_frames: int
    confidence: float
    accepted: bool
    reason: str


def _team_evidence(features: FrameFeatures, config: PossessionConfig, quality: E02Config,
                   tag: Optional[TagEvidence] = None,
                   atd_signal: Optional[AtdSignals] = None) -> TeamObservation:
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
    sources = ["geometry", "motion", "quality"]
    if quality.atd_signal_fusion_enabled and atd_signal is not None:
        supported_team = atd_signal.control.candidate_team
        if supported_team in {"H", "A"}:
            if best_team is None:
                nearest = distances[supported_team]
                opposing = distances["A" if supported_team == "H" else "H"]
                if (nearest is not None and nearest <= config.control_radius_m
                        and opposing is not None
                        and opposing - nearest >= config.min_team_margin_m):
                    best_team = supported_team
            if best_team == supported_team:
                confidence = max(
                    confidence,
                    min(1.0, config.min_observation_confidence
                        + quality.atd_control_confidence_boost * atd_signal.control.confidence),
                )
                sources.append("ATD_CONTROL_PERSISTENCE")
        if (atd_signal.restart_motion.candidate
                and atd_signal.control.candidate_team == best_team):
            sources.append("ATD_RESTART_MOTION_CONTEXT")
        if atd_signal.boundary.candidate:
            confidence *= quality.atd_boundary_confidence_scale
            sources.append("ATD_BOUNDARY_UNCERTAINTY")
        if atd_signal.ball_motion.rapid_uncontrolled_motion:
            confidence *= quality.atd_rapid_motion_confidence_scale
            sources.append("ATD_RAPID_UNCONTROLLED_MOTION")
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
        max(0.0, min(1.0, scores["H"] * features.quality.confidence_weight)),
        max(0.0, min(1.0, scores["A"] * features.quality.confidence_weight)),
        tuple(sources),
    )


def _result(features: FrameFeatures, label: str, team: TeamObservation, dead: DeadBallObservation,
            tag: Optional[TagEvidence] = None,
            possession_config: PossessionConfig = PossessionConfig(),
            atd_signal: Optional[AtdSignals] = None) -> E02FrameInference:
    dead_score = max(dead.dead_score, dead.confidence if dead.cues else 0.0)
    if dead.hard_evidence:
        dead_score = 1.0
    elif dead.confirmed:
        dead_score = max(dead_score, possession_config.confirmed_dead_score)
    if team.team == "H":
        home, away = team.home_score, team.away_score
        if home + away == 0.0:
            home, away = team.confidence, max(1.0 - team.confidence, 1e-12)
    elif team.team == "A":
        home, away = team.home_score, team.away_score
        if home + away == 0.0:
            home, away = max(1.0 - team.confidence, 1e-12), team.confidence
    else:
        home = away = max(dead.live_score, 0.0) / 2.0
    emission = fuse_evidence(
        features.frame.frame, features.frame.half,
        home=home, away=away, dead=dead_score, live=dead.live_score,
        hard_dead=dead.hard_evidence, sources=dead.source + team.source,
    )


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
    evidence = []
    if atd_signal is not None:
        control = atd_signal.control
        control_meaning = (
            "persistent_control_support:{}".format(control.candidate_team)
            if control.candidate_team is not None else "no_persistent_control_hypothesis"
        )
        evidence.append(Evidence(
            FrameReference(frame=features.frame.frame), EvidenceSource.ATD,
            control.confidence, 1 if control.candidate_team is not None else 0,
            control_meaning, features.quality.confidence_weight,
            not features.quality.ball_observed, control.uncertainty,
            "atd_geometry_motion",
        ))
    if tag is not None and tag.active:
        evidence.append(Evidence(
            FrameReference(frame=features.frame.frame), EvidenceSource.TAG,
            max(tag.home_prior, tag.away_prior), 1 if tag.team_prior is not None else 0,
            "smart_tag_context:{}".format(",".join(tag.families)),
            0.5, False, 0.75, "smart_tag_context",
        ))
    if dead.confirmed or label == "D":
        control_hypothesis = ControlHypothesis(
            "UNKNOWN", None, 0.0, ("confirmed_dead",),
            tuple(features.quality.flags) + ("dead_ball",),
        )
    elif "OWNERSHIP_CARRY_UNCONTROLLED_FLIGHT" in team.source:
        control_hypothesis = ControlHypothesis(
            "UNKNOWN", None, 0.0, ("ball_flight",),
            tuple(features.quality.flags) + ("uncontrolled_flight",),
        )
    else:
        evidence_groups = tuple(team.source)
        if tag is not None and tag.active:
            evidence_groups += ("tag_context_available",)
        control_hypothesis = ControlHypothesis(
            team.team if team.team in {"H", "A"} else "UNKNOWN",
            team.team, team.confidence, evidence_groups,
            tuple(features.quality.flags),
        )
    if dead.event_context == "restart_action":
        play_state = "LEGAL_RESTART_EXECUTION"
        play_confidence = 0.8
        play_evidence = ("restart_action",)
    elif dead.confirmed or label == "D":
        play_state = "DEAD_PERSISTENCE"
        play_confidence = max(dead.confidence, 0.8 if dead.confirmed else 0.0)
        play_evidence = dead.source + dead.cues
    elif dead.event_context == "restart_preparation":
        play_state = "RESTART_PREPARATION"
        play_confidence = 0.5
        play_evidence = dead.source or ("restart_context",)
    elif dead.cues and dead.event_context != "restart_context":
        play_state = "STOP_ONSET"
        play_confidence = dead.confidence
        play_evidence = dead.source + dead.cues
    elif features.frame.restart_context:
        play_state = "RESTART_PREPARATION"
        play_confidence = 0.5
        play_evidence = dead.source or ("restart_context",)
    else:
        play_state = "UNKNOWN"
        play_confidence = 0.0
        play_evidence = dead.source
    play_hypothesis = PlayStateHypothesis(
        play_state, min(1.0, max(0.0, play_confidence)),
        tuple(play_evidence), tuple(features.quality.flags),
    )
    inference = FrameInference(
        features.frame.frame, features.frame.half, label, team, dead,
        play_state_hypothesis=play_hypothesis,
    )
    return E02FrameInference(
        inference,
        features, emission, relation, atd_signals=atd_signal,
        tag_context=tag, evidence=tuple(evidence),
        control_hypothesis=control_hypothesis,
        play_state_hypothesis=play_hypothesis,
    )


def _set_play_state(result: E02FrameInference, status: str,
                    confidence: Optional[float] = None,
                    evidence_groups: Optional[Tuple[str, ...]] = None) -> E02FrameInference:
    current = result.play_state_hypothesis
    hypothesis = PlayStateHypothesis(
        status,
        current.confidence if confidence is None else confidence,
        current.evidence_groups if evidence_groups is None else evidence_groups,
        current.quality_flags,
    )
    return replace(
        result,
        play_state_hypothesis=hypothesis,
        inference=replace(result.inference, play_state_hypothesis=hypothesis),
    )


def _iter_features_with_signals(
    frames: Iterable[FrameEvidence], feature_config: E02Config,
) -> Iterator[Tuple[FrameFeatures, Optional[AtdSignals]]]:
    feature_stream = iter_frame_features(frames, feature_config)
    if not feature_config.atd_signal_fusion_enabled:
        for features in feature_stream:
            yield features, None
        return
    inference_features, signal_features = tee(feature_stream)
    signal_config = AtdSignalConfig(
        pitch_length_m=feature_config.pitch_length_m,
        pitch_width_m=feature_config.pitch_width_m,
    )
    for features, signal in zip(
        inference_features, iter_atd_signals(signal_features, signal_config)
    ):
        yield features, signal


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


def _attach_gap_evidence(
    items: List[E02FrameInference], evidence: GapOwnershipEvidence,
) -> List[E02FrameInference]:
    """Make accepted gap evidence visible to the decoder, not only labels."""
    attached = []
    for item in items:
        emission = item.emission
        if evidence.accepted and evidence.recovered_team in {"H", "A"}:
            confidence = evidence.confidence
            home = emission.home * (1.0 - confidence)
            away = emission.away * (1.0 - confidence)
            if evidence.recovered_team == "H":
                home += confidence
            else:
                away += confidence
            emission = fuse_evidence(
                emission.frame, emission.half,
                home=home, away=away, dead=emission.dead, sources=("accepted_gap",),
            )
        attached.append(replace(item, emission=emission, ownership_evidence=evidence))
    return attached


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
    dead_persistence = False
    recovery_team: Optional[str] = None
    recovery_count = 0
    candidate_team: Optional[str] = None
    candidate_count = dead_candidate_count = 0
    dead_candidate_family: Optional[str] = None
    pending_gap: List[E02FrameInference] = []
    pending_recovery: List[E02FrameInference] = []
    gap_prior_state: Optional[str] = None
    gap_support_team: Optional[str] = None
    gap_support_count = 0
    gap_support_start: Optional[int] = None
    gap_attempted = False
    maximum_buffered_gap = min(feature_config.gap_max_frames, possession_config.max_missing_frames)
    dead_ball_detector = StatefulDeadBallDetector()

    tags = iter(tag_evidence) if tag_evidence is not None else None
    for features, atd_signal in _iter_features_with_signals(frames, feature_config):
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
            dead_persistence = False
            recovery_team = None
            recovery_count = 0
            candidate_team = None
            dead_candidate_family = None
            gap_prior_state = gap_support_team = None
            gap_support_count = 0
            gap_support_start = None
            gap_attempted = False
        previous_half = frame.half

        team = _team_evidence(features, possession_config, feature_config, tag, atd_signal)
        uncontrolled_flight = bool(
            feature_config.atd_signal_fusion_enabled and atd_signal is not None
            and state in {"H", "A"} and team.team in {"H", "A"}
            and team.team != state
            and atd_signal.ball_motion.observed_speed_mps is not None
            and atd_signal.ball_motion.observed_speed_mps >= feature_config.ownership_flight_speed_mps
            and atd_signal.control.candidate_team != team.team
            and not features.quality.implausible_ball_jump
            and not features.quality.ball_speed_inconsistent
        )
        raw_dead = dead_ball_detector.observe(
            frame, team, possession_config,
            live_reliable=not (features.quality.implausible_ball_jump
                               or features.quality.ball_speed_inconsistent
                               or uncontrolled_flight),
            boundary_coordinate_reliable=not features.quality.implausible_ball_jump,
            hard_boundary_evidence=not feature_config.stage1_lifecycle_enabled,
        ).dead_ball_evidence
        if (feature_config.stage1_lifecycle_enabled
                and "free kick" in frame.restart_types
                and raw_dead.event_context == "restart_context"):
            # A tag window cannot distinguish a referee award from advantage.
            raw_dead = replace(
                raw_dead, cues=(), confidence=0.0, confirmable=False,
                source=raw_dead.source + ("free_kick_context_only",),
                validity=("free_kick_context_only",),
                event_context="restart_preparation", dead_score=0.0,
            )
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
            dead_persistence = False
            recovery_team = None
            recovery_count = 0
            dead_candidate_family = None
            candidate_team = None
            gap_prior_state = gap_support_team = None
            gap_support_count = 0
            gap_support_start = None
            gap_attempted = False
            yield _result(features, "X", team, finalize_dead_ball(raw_dead, False), tag, possession_config, atd_signal)
            continue

        confirmed_dead, dead_candidate_family, dead_candidate_count = confirm_dead_ball(
            raw_dead, dead_candidate_family, dead_candidate_count, possession_config,
        )
        if (feature_config.stage1_lifecycle_enabled and not confirmed_dead
                and raw_dead.confirmation_family == "out_of_bounds"):
            raw_dead = replace(
                raw_dead, confidence=0.0, dead_score=0.0,
                live_score=max(raw_dead.live_score, 1.0),
            )
        dead = finalize_dead_ball(raw_dead, confirmed_dead)
        dead_ball_detector.remember_confirmation(frame, raw_dead, confirmed_dead, possession_config)

        # A fast ball near an opponent is not sufficient evidence of a transfer.
        # Preserve the last accepted owner in the live emission until the ATD
        # control proposal independently supports the receiving team.
        if not confirmed_dead and uncontrolled_flight:
            confidence = feature_config.flight_owner_carry_confidence
            team = TeamObservation(
                team.ball_observed, state, confidence,
                team.nearest_home_m, team.nearest_away_m, team.margin_m,
                confidence if state == "H" else 1.0 - confidence,
                confidence if state == "A" else 1.0 - confidence,
                team.source + ("OWNERSHIP_CARRY_UNCONTROLLED_FLIGHT",),
            )

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
            newly_dead = not dead_persistence
            dead_persistence = feature_config.stage1_lifecycle_enabled
            recovery_team = None
            recovery_count = 0
            state = "D"
            missing_count = uncertain_count = candidate_count = 0
            candidate_team = None
            result = _result(features, "D", team, dead, tag, possession_config, atd_signal)
            if newly_dead:
                result = _set_play_state(result, "STOP_ONSET", dead.confidence,
                                         dead.source + dead.cues)
            else:
                result = _set_play_state(result, "DEAD_PERSISTENCE", dead.confidence,
                                         dead.source + dead.cues)
            yield result
            continue

        recovered_status: Optional[str] = None
        if dead_persistence and feature_config.stage1_lifecycle_enabled:
            if frame.restart_action is not None:
                dead_persistence = False
                state = "X"
                candidate_team = None
                candidate_count = 0
                recovery_team = None
                recovery_count = 0
                recovered_status = "LEGAL_RESTART_EXECUTION"
            else:
                derived_speed = features.motion.derived_ball_speed_mps
                provider_speed = features.motion.provider_ball_speed_mps
                moving = (
                    (derived_speed is not None and derived_speed >= 0.5)
                    or (provider_speed is not None and provider_speed >= 0.5
                        and not features.quality.ball_speed_inconsistent)
                )
                supported_live = (
                    team.ball_observed and team.team in {"H", "A"} and moving
                    and team.confidence >= possession_config.min_observation_confidence
                    and not features.quality.low_player_coverage
                    and not features.quality.implausible_ball_jump
                    and not features.quality.ball_speed_inconsistent
                    and not raw_dead.cues
                )
                if supported_live:
                    if recovery_team == team.team:
                        recovery_count += 1
                    else:
                        recovery_team = team.team
                        recovery_count = 1
                else:
                    recovery_team = None
                    recovery_count = 0
                if supported_live and recovery_count >= possession_config.acquire_frames:
                    dead_persistence = False
                    state = team.team
                    candidate_team = None
                    candidate_count = 0
                    recovery_team = None
                    recovery_count = 0
                    recovered_status = "LIVE_RECOVERED"
                else:
                    persisted = DeadBallObservation(
                        ("dead_persistence",), dead.confidence, True, False,
                        ("dead_lifecycle",) + dead.source,
                        ("confirmed_stop", "waiting_for_live_recovery"),
                        "dead_persistence", dead.live_counterevidence, False,
                        possession_config.confirmed_dead_score, 0.0,
                        dead.confirmation_family,
                    )
                    result = _result(features, "D", team, persisted, tag,
                                     possession_config, atd_signal)
                    yield _set_play_state(result, "DEAD_PERSISTENCE",
                                          possession_config.confirmed_dead_score,
                                          persisted.source + persisted.cues)
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
            pending_gap.append(_result(features, label, team, dead, tag, possession_config, atd_signal))

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
            result = _result(features, label, team, dead, tag, possession_config, atd_signal)
        else:
            uncertain_count = 0
            observed_team = team.team
            prior_owner = state if state in {"H", "A"} else "UNKNOWN"
            transition = None
            if observed_team == state:
                candidate_team = None
                candidate_count = 0
            elif observed_team == candidate_team:
                candidate_count += 1
            else:
                candidate_team = observed_team
                candidate_count = 1
            # Restart motion is contextual evidence, not fresh ownership support.
            # Require the normal consecutive observed-control gate after DEAD so
            # pre-stoppage ATD persistence cannot accelerate reacquisition.
            required_acquire_frames = possession_config.acquire_frames
            if observed_team != state and candidate_count >= required_acquire_frames:
                transition = ControlTransition(
                    prior_owner, observed_team,
                    frame.frame - candidate_count + 1, frame.frame,
                    candidate_count, min(1.0, team.confidence), True,
                    "persistent_observed_control",
                )
                state = observed_team
                candidate_team = None
                candidate_count = 0
            label = state if state in {"H", "A"} else "X"
            result = _result(features, label, team, dead, tag, possession_config, atd_signal)
            if recovered_status is not None:
                result = _set_play_state(result, recovered_status,
                                         min(1.0, team.confidence),
                                         dead.source + ((frame.restart_action,) if frame.restart_action else ("consecutive_live_control",)))
            if transition is not None:
                result = replace(result, control_transition=transition)

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
                gap_evidence = GapOwnershipEvidence(
                    gap_prior_state, opposing_team,
                    "{}_to_{}".format(gap_prior_state, opposing_team)
                    if accepted_team is not None else "unaccepted",
                    pending_gap[0].features.frame.frame,
                    pending_gap[-1].features.frame.frame,
                    gap_support_count,
                    min(0.8, gap_support_count / float(max(1, feature_config.gap_support_frames)) * 0.8)
                    if accepted_team is not None else 0.0,
                    accepted_team is not None,
                    reason,
                )
                resolved_gap = _resolve_gap(
                    pending_gap, accepted_team, gap_support_start, gap_attempted, reason
                )
                if accepted_team is not None:
                    resolved_gap = _attach_gap_evidence(resolved_gap, gap_evidence)
                yield from resolved_gap
                if accepted_team is not None:
                    recovered = [
                        replace(item, inference=replace(item.inference, label=accepted_team))
                        for item in pending_recovery
                    ]
                    yield from _attach_gap_evidence(recovered, gap_evidence)
                else:
                    yield from pending_recovery
                yield replace(result, ownership_evidence=gap_evidence if accepted_team is not None else None)
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
