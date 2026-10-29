"""Deterministic team-level geometry, motion, and observation-quality features for E02."""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import median
from typing import Iterable, Iterator, Optional, Sequence, Tuple

from starter_v4.possession import FrameEvidence, PlayerEvidence, _validate_frame


@dataclass(frozen=True)
class E02Config:
    top_k: int = 3
    duplicate_merge_radius_m: float = 0.25
    density_radius_m: float = 8.0
    contest_margin_m: float = 1.5
    pitch_length_m: float = 105.3
    pitch_width_m: float = 68.0
    quality_reference_players: int = 10
    low_player_count: int = 6
    max_ball_speed_mps: float = 40.0
    max_ball_speed_error_mps: float = 12.0
    gap_anchor_radius_m: float = 6.0
    gap_approach_scale_m: float = 1.0
    gap_score_threshold: float = 0.45
    gap_score_margin: float = 0.15
    gap_min_players_per_team: int = 1
    gap_min_quality_weight: float = 0.6
    gap_support_frames: int = 3
    gap_max_frames: int = 25

    def __post_init__(self) -> None:
        for name in ("top_k", "quality_reference_players", "low_player_count", "gap_min_players_per_team", "gap_support_frames", "gap_max_frames"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError("{} must be a positive integer".format(name))
        positive = (
            "duplicate_merge_radius_m", "density_radius_m", "pitch_length_m", "pitch_width_m",
            "max_ball_speed_mps", "max_ball_speed_error_mps", "gap_anchor_radius_m",
            "gap_approach_scale_m",
        )
        for name in positive:
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError("{} must be finite and positive".format(name))
        for name in ("contest_margin_m", "gap_score_threshold", "gap_score_margin", "gap_min_quality_weight"):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0 <= value <= 1 and name != "contest_margin_m":
                raise ValueError("{} must be finite and in [0, 1]".format(name))
        if self.contest_margin_m < 0:
            raise ValueError("contest_margin_m must be non-negative")


@dataclass(frozen=True)
class SpatialFeatures:
    nearest_home_m: Optional[float]
    nearest_away_m: Optional[float]
    topk_home_mean_m: Optional[float]
    topk_away_mean_m: Optional[float]
    home_distance_margin_m: Optional[float]
    unique_player_count_home: int
    unique_player_count_away: int
    density_home: int
    density_away: int
    contested: bool
    boundary_distance_m: Optional[float]


@dataclass(frozen=True)
class MotionFeatures:
    derived_ball_speed_mps: Optional[float]
    ball_velocity_mps: Optional[Tuple[float, float]]
    home_centroid_speed_mps: Optional[float]
    away_centroid_speed_mps: Optional[float]
    home_player_speed_median_mps: Optional[float]
    away_player_speed_median_mps: Optional[float]
    home_ball_comotion: Optional[float]
    away_ball_comotion: Optional[float]
    last_ball_anchor_xy: Optional[Tuple[float, float]]
    anchor_nearest_home_m: Optional[float]
    anchor_nearest_away_m: Optional[float]
    gap_score_home: float
    gap_score_away: float
    gap_candidate_team: Optional[str]


@dataclass(frozen=True)
class ObservationQuality:
    ball_observed: bool
    ball_missing: bool
    low_player_coverage: bool
    one_team_visible: bool
    duplicate_observations: int
    implausible_ball_jump: bool
    ball_speed_inconsistent: bool
    track_population_change: bool
    out_of_bounds: bool
    confidence_weight: float
    flags: Tuple[str, ...]


@dataclass(frozen=True)
class FrameFeatures:
    frame: FrameEvidence
    spatial: SpatialFeatures
    motion: MotionFeatures
    quality: ObservationQuality


def _unique_team_players(
    players: Sequence[PlayerEvidence], team: str, radius: float,
    reference: Optional[Tuple[float, float]],
) -> Tuple[list, int]:
    """Drop near-identical same-team positions so duplicate tracklets do not add votes."""
    selected = []
    duplicates = 0
    if reference is None:
        key = lambda p: (p.x_m, p.y_m, p.track_id if p.track_id is not None else -1)
    else:
        key = lambda p: (math.hypot(p.x_m - reference[0], p.y_m - reference[1]), p.x_m, p.y_m)
    ordered = sorted((p for p in players if p.team == team), key=key)
    for player in ordered:
        if any(math.hypot(player.x_m - prior.x_m, player.y_m - prior.y_m) <= radius for prior in selected):
            duplicates += 1
        else:
            selected.append(player)
    return selected, duplicates


def _distances(players: Sequence[PlayerEvidence], point: Tuple[float, float]) -> list:
    return sorted(math.hypot(player.x_m - point[0], player.y_m - point[1]) for player in players)


def _mean_top(values: Sequence[float], count: int) -> Optional[float]:
    return sum(values[:count]) / float(min(count, len(values))) if values else None


def _centroid(players: Sequence[PlayerEvidence]) -> Optional[Tuple[float, float]]:
    if not players:
        return None
    return (
        sum(player.x_m for player in players) / len(players),
        sum(player.y_m for player in players) / len(players),
    )


def _cosine(first: Optional[Tuple[float, float]], second: Optional[Tuple[float, float]]) -> Optional[float]:
    if first is None or second is None:
        return None
    first_norm = math.hypot(*first)
    second_norm = math.hypot(*second)
    if first_norm < 1e-9 or second_norm < 1e-9:
        return None
    return max(-1.0, min(1.0, (first[0] * second[0] + first[1] * second[1]) / (first_norm * second_norm)))


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, value))


class _FeatureState:
    def __init__(self) -> None:
        self.previous: Optional[FrameEvidence] = None
        self.previous_centroids = {"H": None, "A": None}
        self.previous_anchor_distances = {"H": None, "A": None}
        self.last_ball_anchor: Optional[Tuple[float, float]] = None
        self.last_visible_slots = set()
        self.gap_frames = 0

    def reset(self) -> None:
        self.__init__()


def iter_frame_features(
    frames: Iterable[FrameEvidence], config: E02Config = E02Config()
) -> Iterator[FrameFeatures]:
    """Derive masked features in order; missing ball coordinates remain absent."""
    state = _FeatureState()
    previous_half: Optional[int] = None
    previous_index: Optional[int] = None

    for frame in frames:
        _validate_frame(frame)
        if previous_index is not None and frame.frame != previous_index + 1:
            raise ValueError("frames must be contiguous and ordered")
        if previous_half is not None and frame.half != previous_half:
            state.reset()
        previous_half, previous_index = frame.half, frame.frame

        dedupe_reference = frame.ball_xy if frame.ball_xy is not None else state.last_ball_anchor
        home, dup_h = _unique_team_players(frame.players, "H", config.duplicate_merge_radius_m, dedupe_reference)
        away, dup_a = _unique_team_players(frame.players, "A", config.duplicate_merge_radius_m, dedupe_reference)
        duplicate_count = dup_h + dup_a
        all_unique = home + away
        ball = frame.ball_xy
        nearest_h = nearest_a = topk_h = topk_a = margin_h = None
        density_h = density_a = 0
        contested = False
        boundary_distance = None
        if ball is not None:
            raw_home = [player for player in frame.players if player.team == "H"]
            raw_away = [player for player in frame.players if player.team == "A"]
            distances_h = _distances(home, ball)
            distances_a = _distances(away, ball)
            all_distances_h = _distances(raw_home, ball)
            all_distances_a = _distances(raw_away, ball)
            # Duplicate rows cannot change the nearest observation, but are removed from top-k votes.
            nearest_h = all_distances_h[0] if all_distances_h else None
            nearest_a = all_distances_a[0] if all_distances_a else None
            topk_h, topk_a = _mean_top(distances_h, config.top_k), _mean_top(distances_a, config.top_k)
            if nearest_h is not None and nearest_a is not None:
                margin_h = nearest_a - nearest_h
                contested = abs(margin_h) <= config.contest_margin_m
            density_h = sum(distance <= config.density_radius_m for distance in distances_h)
            density_a = sum(distance <= config.density_radius_m for distance in distances_a)
            boundary_distance = min(ball[0], config.pitch_length_m - ball[0], ball[1], config.pitch_width_m - ball[1])

        current_centroids = {"H": _centroid(home), "A": _centroid(away)}
        ball_velocity = None
        derived_ball_speed = None
        centroid_speeds = {"H": None, "A": None}
        centroid_vectors = {"H": None, "A": None}
        consecutive = state.previous is not None and frame.frame == state.previous.frame + 1 and frame.half == state.previous.half
        if consecutive and ball is not None and state.previous.ball_xy is not None:
            vector = (ball[0] - state.previous.ball_xy[0], ball[1] - state.previous.ball_xy[1])
            ball_velocity = (vector[0] * 25.0, vector[1] * 25.0)
            derived_ball_speed = math.hypot(*ball_velocity)
        if consecutive:
            for team in ("H", "A"):
                previous_centroid = state.previous_centroids[team]
                current_centroid = current_centroids[team]
                if previous_centroid is not None and current_centroid is not None:
                    vector = (current_centroid[0] - previous_centroid[0], current_centroid[1] - previous_centroid[1])
                    centroid_vectors[team] = (vector[0] * 25.0, vector[1] * 25.0)
                    centroid_speeds[team] = math.hypot(*centroid_vectors[team])

        anchor = state.last_ball_anchor
        anchor_nearest = {"H": None, "A": None}
        approach = {"H": 0.0, "A": 0.0}
        anchor_density = {"H": 0, "A": 0}
        gap_candidate = None
        gap_scores = {"H": 0.0, "A": 0.0}
        if ball is None:
            state.gap_frames += 1
            if anchor is not None and state.gap_frames <= config.gap_max_frames:
                for team, team_players in (("H", home), ("A", away)):
                    distances = _distances(team_players, anchor)
                    raw_team_players = [player for player in frame.players if player.team == team]
                    raw_distances = _distances(raw_team_players, anchor)
                    anchor_nearest[team] = raw_distances[0] if raw_distances else None
                    anchor_density[team] = sum(distance <= config.density_radius_m for distance in distances)
                    prior_distance = state.previous_anchor_distances[team]
                    if prior_distance is not None and anchor_nearest[team] is not None:
                        approach[team] = prior_distance - anchor_nearest[team]
                    proximity_score = (
                        _clip01((config.gap_anchor_radius_m - anchor_nearest[team]) / config.gap_anchor_radius_m)
                        if anchor_nearest[team] is not None else 0.0
                    )
                    approach_score = _clip01(approach[team] / config.gap_approach_scale_m)
                    density_score = min(anchor_density[team], config.top_k) / float(config.top_k)
                    gap_scores[team] = 0.30 * proximity_score + 0.55 * approach_score + 0.15 * density_score
                h_count, a_count = len(home), len(away)
                if h_count >= config.gap_min_players_per_team and a_count >= config.gap_min_players_per_team:
                    difference = gap_scores["H"] - gap_scores["A"]
                    best = "H" if difference > 0 else "A"
                    if gap_scores[best] >= config.gap_score_threshold and abs(difference) >= config.gap_score_margin:
                        gap_candidate = best
        else:
            state.gap_frames = 0

        h_speeds = [player.speed_mps for player in home if player.speed_mps is not None]
        a_speeds = [player.speed_mps for player in away if player.speed_mps is not None]
        player_speed = {
            "H": median(h_speeds) if h_speeds else None,
            "A": median(a_speeds) if a_speeds else None,
        }
        home_comotion = _cosine(ball_velocity, centroid_vectors["H"])
        away_comotion = _cosine(ball_velocity, centroid_vectors["A"])

        flags = []
        one_team = bool(home) != bool(away)
        low_coverage = len(all_unique) < config.low_player_count
        slots = {player.track_id for player in frame.players if player.track_id is not None}
        population_change = bool(state.previous is not None and state.last_visible_slots and slots and slots != state.last_visible_slots)
        out_of_bounds = bool(ball is not None and (
            ball[0] < 0 or ball[0] > config.pitch_length_m or ball[1] < 0 or ball[1] > config.pitch_width_m
        ))
        jump = derived_ball_speed is not None and derived_ball_speed > config.max_ball_speed_mps
        speed_inconsistent = bool(
            derived_ball_speed is not None and frame.ball_speed_mps is not None
            and abs(derived_ball_speed - frame.ball_speed_mps) > config.max_ball_speed_error_mps
        )
        if ball is None:
            flags.append("ball_missing")
        if low_coverage:
            flags.append("low_player_coverage")
        if one_team:
            flags.append("one_team_visible")
        if duplicate_count:
            flags.append("duplicate_positions")
        if jump:
            flags.append("implausible_ball_jump")
        if speed_inconsistent:
            flags.append("ball_speed_displacement_mismatch")
        if population_change:
            flags.append("observation_population_change")
        if out_of_bounds:
            flags.append("ball_out_of_bounds")

        coverage = _clip01(len(all_unique) / float(config.quality_reference_players))
        confidence_weight = coverage
        if one_team:
            confidence_weight *= 0.7
        if contested:
            confidence_weight *= 0.6
        if duplicate_count:
            confidence_weight *= 1.0 / (1.0 + 0.1 * duplicate_count)
        if population_change:
            confidence_weight *= 0.8
        if jump or speed_inconsistent:
            confidence_weight *= 0.25
        confidence_weight = _clip01(confidence_weight)

        spatial = SpatialFeatures(
            nearest_h, nearest_a, topk_h, topk_a, margin_h,
            len(home), len(away), density_h, density_a, contested, boundary_distance,
        )
        motion = MotionFeatures(
            derived_ball_speed, ball_velocity, centroid_speeds["H"], centroid_speeds["A"],
            player_speed["H"], player_speed["A"], home_comotion, away_comotion,
            anchor, anchor_nearest["H"], anchor_nearest["A"],
            gap_scores["H"], gap_scores["A"], gap_candidate,
        )
        quality = ObservationQuality(
            ball is not None, ball is None, low_coverage, one_team, duplicate_count,
            jump, speed_inconsistent, population_change, out_of_bounds,
            confidence_weight, tuple(flags),
        )
        yield FrameFeatures(frame, spatial, motion, quality)

        state.previous = frame
        state.previous_centroids = current_centroids
        state.previous_anchor_distances = anchor_nearest if ball is None else {"H": None, "A": None}
        if ball is not None:
            state.last_ball_anchor = ball
        state.last_visible_slots = slots
