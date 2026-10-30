"""Local-only parsers for ATD, Smart Tagging, homography, and bundle provenance.

The raw ATD is consumed a frame at a time. ``load_atd_arrays`` materializes compact typed arrays
only when a caller needs the full sequence; ``build_data_quality_report`` stays streaming and
emits aggregates only. No function downloads, displays, or exports restricted frame content.
"""

from __future__ import annotations

import array
import csv
import hashlib
import json
import math
import os
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple

from games import GAME, GAMES, SOURCES, asset_paths, half_video_blocks, half_of_video_frame, require, source_frames


MISSING_TOKENS = frozenset(("", "n", "nan", "na", "n/a", "none", "null"))
HOMOGRAPHY_COLUMNS = tuple("h{}{}".format(row, col) for row in range(3) for col in range(3))
HOMOGRAPHY_MAPPING_DIRECTION = "normalized_pitch_xy_to_video_pixel_xy"


class IngestionError(ValueError):
    """Input data does not match the documented schema or alignment contract."""


@dataclass(frozen=True)
class TrackSlot:
    index: int
    slot_id: str
    name: str
    team: str


@dataclass(frozen=True)
class ATDMetadata:
    team_ids: Tuple[str, str]
    team_names: Tuple[str, str]
    slots: Tuple[TrackSlot, ...]
    pitch_length_m: float
    pitch_width_m: float
    declared_pitch_length_m: Optional[float] = None
    declared_pitch_width_m: Optional[float] = None
    missing_semantics: str = "NaN or another documented missing token means no observation; position and speed validity are tracked separately."


@dataclass(frozen=True)
class Observation:
    x_norm: float
    y_norm: float
    speed_mps: float
    x_m: float
    y_m: float
    valid: bool
    speed_valid: bool


@dataclass(frozen=True)
class ATDFrame:
    frame_id: int
    video_frame: int
    players: Tuple[Observation, ...]
    ball: Observation


@dataclass
class TrackingArrays:
    """Compact row-major arrays; player index = video_frame * slot_count + slot_index."""

    frame_ids: array.array
    video_frames: array.array
    slot_count: int
    player_x_norm: array.array
    player_y_norm: array.array
    player_x_m: array.array
    player_y_m: array.array
    player_speed_mps: array.array
    player_valid: bytearray
    player_speed_valid: bytearray
    ball_x_norm: array.array
    ball_y_norm: array.array
    ball_x_m: array.array
    ball_y_m: array.array
    ball_speed_mps: array.array
    ball_valid: bytearray
    ball_speed_valid: bytearray


@dataclass(frozen=True)
class SmartTagEvent:
    code: str
    start_s: float
    end_s: float
    start_frame: int
    end_frame: int
    tags: Mapping[str, str]
    team: Optional[str]
    team_raw: Optional[str]


@dataclass
class HomographyArrays:
    frame_indices: array.array
    matrices: array.array
    reprojection_error: array.array
    valid: bytearray
    mapping_direction: str = HOMOGRAPHY_MAPPING_DIRECTION


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def _child_text(element: ET.Element, name: str) -> Optional[str]:
    for child in list(element):
        if _local_name(child.tag) == name.casefold():
            return child.text.strip() if child.text and child.text.strip() else None
    return None


def _attribute(element: ET.Element, *names: str) -> Optional[str]:
    wanted = {name.casefold() for name in names}
    for key, value in element.attrib.items():
        if _local_name(key) in wanted and value.strip():
            return value.strip()
    return None


def _declared_pitch_dimensions(root: ET.Element) -> Tuple[Optional[float], Optional[float]]:
    """Read declared dimensions when present; operational scaling still uses games.py constants."""
    parent_of = {child: parent for parent in root.iter() for child in list(parent)}
    pitch_containers = {"pitch", "pitchdimension", "pitchdimensions", "pitchsize"}
    aliases = {
        "length": {"length", "pitchlength", "pitch_length", "fieldlength", "field_length"},
        "width": {"width", "pitchwidth", "pitch_width", "fieldwidth", "field_width"},
    }
    values: Dict[str, set] = {"length": set(), "width": set()}
    for element in root.iter():
        element_name = _local_name(element.tag)
        in_pitch_container = False
        parent = parent_of.get(element)
        while parent is not None:
            if _local_name(parent.tag) in pitch_containers:
                in_pitch_container = True
                break
            parent = parent_of.get(parent)
        for axis, names in aliases.items():
            explicitly_named = element_name in names - {"length", "width"}
            contextual_name = (in_pitch_container or element_name in {"length", "width"}) and element_name == axis
            if explicitly_named or contextual_name:
                text = element.text.strip() if element.text and element.text.strip() else None
                if text is not None:
                    try:
                        value = float(text)
                    except ValueError:
                        continue
                    if math.isfinite(value) and value > 0:
                        values[axis].add(value)
            if element_name in pitch_containers:
                for key, raw_value in element.attrib.items():
                    if _local_name(key) in names:
                        try:
                            value = float(raw_value)
                        except ValueError:
                            continue
                        if math.isfinite(value) and value > 0:
                            values[axis].add(value)
    length = next(iter(values["length"])) if len(values["length"]) == 1 else None
    width = next(iter(values["width"])) if len(values["width"]) == 1 else None
    return length, width


def parse_atd_metadata(path: Path, game: str = GAME) -> ATDMetadata:
    """Read team order, track-slot mapping, and pitch dimensions without loading tracking rows."""
    root = ET.parse(str(path)).getroot()
    teams = [element for element in root.iter() if _local_name(element.tag) == "team"]
    if len(teams) != 2:
        raise IngestionError("{}: expected exactly 2 team entries, found {}".format(path, len(teams)))
    team_ids = tuple(_attribute(team, "id") or "" for team in teams)
    team_names = tuple(_child_text(team, "name") or "" for team in teams)
    if any(not value for value in team_ids) or len(set(team_ids)) != 2:
        raise IngestionError("{}: team IDs must be present and unique".format(path))
    if any(not value for value in team_names):
        raise IngestionError("{}: both team names must be present".format(path))

    player_elements = [element for element in root.iter() if _local_name(element.tag) == "player"]
    if not player_elements:
        raise IngestionError("{}: no player/track-slot entries".format(path))
    slots: List[TrackSlot] = []
    seen_ids = set()
    seen_names = set()
    code_by_id = {team_ids[0]: "H", team_ids[1]: "A"}
    for index, player in enumerate(player_elements):
        slot_id = _attribute(player, "id")
        team_id = _attribute(player, "teamId", "team_id")
        name = _child_text(player, "name") or _attribute(player, "name") or ""
        if not slot_id or not name:
            raise IngestionError("{}: each track slot needs an ID and name".format(path))
        if slot_id in seen_ids or name.casefold() in seen_names:
            raise IngestionError("{}: duplicate track-slot ID or name".format(path))
        if team_id not in code_by_id:
            raise IngestionError("{}: track slot refers to an unknown team".format(path))
        seen_ids.add(slot_id)
        seen_names.add(name.casefold())
        slots.append(TrackSlot(index, slot_id, name, code_by_id[team_id]))

    pitch = GAMES[game]["pitch"]
    declared_length, declared_width = _declared_pitch_dimensions(root)
    return ATDMetadata(
        (team_ids[0], team_ids[1]),
        (team_names[0], team_names[1]),
        tuple(slots),
        float(pitch[0]),
        float(pitch[1]),
        declared_length,
        declared_width,
    )


def _float_or_nan(token: str, context: str) -> float:
    value = token.strip()
    if value.casefold() in MISSING_TOKENS:
        return float("nan")
    try:
        parsed = float(value)
    except ValueError as error:
        raise IngestionError("{}: expected numeric value or missing token".format(context)) from error
    if not math.isfinite(parsed):
        raise IngestionError("{}: infinity is not a valid observation; use NaN for missing data".format(context))
    return parsed


def _observation(text: str, length_m: float, width_m: float, context: str) -> Observation:
    fields = text.strip().split(",")
    if len(fields) < 2 or len(fields) > 3:
        if text.strip().casefold() in MISSING_TOKENS:
            fields = ["NaN", "NaN", "NaN"]
        else:
            raise IngestionError("{}: expected x,y or x,y,speed".format(context))
    x = _float_or_nan(fields[0], context)
    y = _float_or_nan(fields[1], context)
    speed = _float_or_nan(fields[2], context) if len(fields) == 3 else float("nan")
    return Observation(
        x, y, speed,
        x * length_m if math.isfinite(x) else float("nan"),
        y * width_m if math.isfinite(y) else float("nan"),
        math.isfinite(x) and math.isfinite(y),
        math.isfinite(speed),
    )


def iter_atd_frames(
    path: Path,
    metadata: ATDMetadata,
    expected_frames: Optional[int] = None,
    source: str = "tactical",
    game: str = GAME,
) -> Iterator[ATDFrame]:
    """Stream strict, sequential ATD frames and translate one-based IDs to zero-based video rows."""
    expected = expected_frames if expected_frames is not None else source_frames(source, game)
    if expected < 0:
        raise ValueError("expected_frames must be nonnegative")
    frame_count = 0
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.rstrip("\r\n")
            parts = line.split(":", 2)
            if len(parts) != 3:
                raise IngestionError("{} line {}: expected frame:players:ball".format(path, line_number))
            try:
                frame_id = int(parts[0])
            except ValueError as error:
                raise IngestionError("{} line {}: invalid frame_id".format(path, line_number)) from error
            expected_id = frame_count + 1
            if frame_id != expected_id:
                raise IngestionError(
                    "{} line {}: expected frame_id {}, found {}".format(path, line_number, expected_id, frame_id)
                )
            if frame_count >= expected:
                raise IngestionError("{}: more than {} frames".format(path, expected))
            player_fields = parts[1].split(";") if parts[1] else []
            if len(player_fields) != len(metadata.slots):
                raise IngestionError(
                    "{} line {}: expected {} player slots, found {}".format(
                        path, line_number, len(metadata.slots), len(player_fields)
                    )
                )
            players = tuple(
                _observation(value, metadata.pitch_length_m, metadata.pitch_width_m,
                             "{} line {} slot {}".format(path, line_number, slot_index))
                for slot_index, value in enumerate(player_fields)
            )
            ball = _observation(parts[2], metadata.pitch_length_m, metadata.pitch_width_m,
                                "{} line {} ball".format(path, line_number))
            yield ATDFrame(frame_id, frame_id - 1, players, ball)
            frame_count += 1
    if frame_count != expected:
        raise IngestionError("{}: expected {} frames, found {}".format(path, expected, frame_count))


def load_atd_arrays(
    path: Path,
    metadata: ATDMetadata,
    expected_frames: Optional[int] = None,
    source: str = "tactical",
    game: str = GAME,
) -> TrackingArrays:
    """Materialize compact, aligned arrays while retaining normalized and metric coordinates."""
    frame_count = expected_frames if expected_frames is not None else source_frames(source, game)
    slot_count = len(metadata.slots)
    total = frame_count * slot_count
    nan = float("nan")
    player_x_norm = array.array("d", [nan]) * total
    player_y_norm = array.array("d", [nan]) * total
    player_x_m = array.array("d", [nan]) * total
    player_y_m = array.array("d", [nan]) * total
    player_speed = array.array("d", [nan]) * total
    player_valid = bytearray(total)
    player_speed_valid = bytearray(total)
    ball_arrays = [array.array("d", [nan]) * frame_count for _ in range(5)]
    ball_valid = bytearray(frame_count)
    ball_speed_valid = bytearray(frame_count)

    for frame in iter_atd_frames(path, metadata, frame_count, source, game):
        row_start = frame.video_frame * slot_count
        for slot_index, observation in enumerate(frame.players):
            index = row_start + slot_index
            player_x_norm[index] = observation.x_norm
            player_y_norm[index] = observation.y_norm
            player_x_m[index] = observation.x_m
            player_y_m[index] = observation.y_m
            player_speed[index] = observation.speed_mps
            player_valid[index] = int(observation.valid)
            player_speed_valid[index] = int(observation.speed_valid)
        ball = frame.ball
        ball_arrays[0][frame.video_frame] = ball.x_norm
        ball_arrays[1][frame.video_frame] = ball.y_norm
        ball_arrays[2][frame.video_frame] = ball.x_m
        ball_arrays[3][frame.video_frame] = ball.y_m
        ball_arrays[4][frame.video_frame] = ball.speed_mps
        ball_valid[frame.video_frame] = int(ball.valid)
        ball_speed_valid[frame.video_frame] = int(ball.speed_valid)

    return TrackingArrays(
        array.array("q", range(1, frame_count + 1)),
        array.array("q", range(frame_count)),
        slot_count,
        player_x_norm, player_y_norm, player_x_m, player_y_m, player_speed,
        player_valid, player_speed_valid,
        ball_arrays[0], ball_arrays[1], ball_arrays[2], ball_arrays[3], ball_arrays[4],
        ball_valid, ball_speed_valid,
    )


def _normalize_team(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    raw = value.strip()
    folded = " ".join(raw.casefold().split())
    if folded in {"n/a", "na", "n.a.", "not available"}:
        return "N/A"
    if folded == "barcelona":
        return "H"
    if folded in {"athletic club", "atletic club", "athletic"}:
        return "A"
    return raw


def _tag_value(label: ET.Element, child_name: str, attribute_name: str) -> Optional[str]:
    value = _child_text(label, child_name) or _attribute(label, attribute_name)
    return value.strip() if value else None


def parse_smart_tagging(
    path: Path,
    fps: int = GAMES[GAME]["fps"],
    expected_frames: Optional[int] = source_frames("tactical", GAME),
) -> List[SmartTagEvent]:
    """Parse Smart Tagging intervals; team names normalize to H/A while N/A stays explicit."""
    if fps <= 0:
        raise ValueError("fps must be positive")
    root = ET.parse(str(path)).getroot()
    events: List[SmartTagEvent] = []
    for instance in (element for element in root.iter() if _local_name(element.tag) == "instance"):
        start_text = _child_text(instance, "start")
        end_text = _child_text(instance, "end")
        code_text = _child_text(instance, "code")
        if start_text is None or end_text is None:
            raise IngestionError("{}: event is missing start or end time".format(path))
        try:
            start_s, end_s = float(start_text), float(end_text)
        except ValueError as error:
            raise IngestionError("{}: event time is not numeric".format(path)) from error
        if not math.isfinite(start_s) or not math.isfinite(end_s) or start_s < 0 or end_s < start_s:
            raise IngestionError("{}: event interval has invalid bounds".format(path))
        start_frame = int(round(start_s * fps))
        end_frame = int(round(end_s * fps))
        if expected_frames is not None and (start_frame > expected_frames or end_frame > expected_frames):
            raise IngestionError("{}: event interval exceeds the video frame range".format(path))

        tags: Dict[str, str] = {}
        for label in (element for element in instance.iter() if _local_name(element.tag) == "label"):
            group = _tag_value(label, "group", "group")
            value = _tag_value(label, "text", "text")
            if group and value is not None:
                canonical_group = {"team": "Team", "half": "Half", "type": "Type"}.get(
                    group.casefold(), group.strip()
                )
                tags[canonical_group] = value
        team_raw = tags.get("Team")
        events.append(SmartTagEvent(
            (code_text or "").strip().upper(), start_s, end_s, start_frame, end_frame,
            tags, _normalize_team(team_raw), team_raw.strip() if team_raw else None,
        ))
    return events


def load_homography_arrays(path: Path, expected_frames: Optional[int] = None) -> HomographyArrays:
    """Load framewise 3x3 transforms and validate row indices, shape, and validity flags."""
    expected = expected_frames if expected_frames is not None else source_frames("tactical", GAME)
    required = ("frame",) + HOMOGRAPHY_COLUMNS + ("reprojection_error", "valid")
    matrices = array.array("d")
    errors = array.array("d")
    validity = bytearray()
    indices = array.array("q")
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or any(column not in reader.fieldnames for column in required):
            raise IngestionError("{}: homography header is missing required columns".format(path))
        row_count = 0
        for row in reader:
            if None in row:
                raise IngestionError("{} row {}: unexpected extra columns".format(path, row_count + 2))
            frame_text = row.get("frame")
            try:
                frame = int(frame_text) if frame_text is not None else -1
            except ValueError as error:
                raise IngestionError("{} row {}: invalid frame index".format(path, row_count + 2)) from error
            if frame != row_count:
                raise IngestionError(
                    "{} row {}: expected frame {}, found {}".format(path, row_count + 2, row_count, frame)
                )
            if row_count >= expected:
                raise IngestionError("{}: more than {} homography frames".format(path, expected))
            try:
                valid_token = (row.get("valid") or "").strip().casefold()
                valid = 1 if valid_token in {"1", "true"} else 0 if valid_token in {"0", "false"} else -1
                if valid < 0:
                    raise ValueError("valid flag must be 0 or 1")
                matrix = [float(row[column]) for column in HOMOGRAPHY_COLUMNS]
                error_value = float(row["reprojection_error"])
            except (TypeError, ValueError, KeyError) as error:
                raise IngestionError("{} row {}: malformed matrix or validity field".format(path, row_count + 2)) from error
            if valid and not all(math.isfinite(value) for value in matrix):
                raise IngestionError("{} row {}: valid matrix contains non-finite values".format(path, row_count + 2))
            if math.isfinite(error_value) and error_value < 0:
                raise IngestionError("{} row {}: reprojection error cannot be negative".format(path, row_count + 2))
            indices.append(frame)
            matrices.extend(matrix)
            errors.append(error_value)
            validity.append(valid)
            row_count += 1
    if row_count != expected:
        raise IngestionError("{}: expected {} homography frames, found {}".format(path, expected, row_count))
    return HomographyArrays(indices, matrices, errors, validity)


def half_index_by_video_frame(frame_count: int, game: str = GAME) -> Tuple[bytearray, Dict[int, Tuple[int, int]]]:
    """Return 0 for ungraded frames and the half number for each graded video frame."""
    labels = bytearray(frame_count)
    ranges: Dict[int, Tuple[int, int]] = {}
    for half, first, last in half_video_blocks(game):
        if first < 0 or last >= frame_count or first > last:
            raise IngestionError("games.py half block is outside the video frame range")
        if any(labels[index] for index in range(first, last + 1)):
            raise IngestionError("games.py half blocks overlap")
        labels[first:last + 1] = bytes([half]) * (last - first + 1)
        ranges[half] = (first, last)
    return labels, ranges


def _ratio(numerator: int, denominator: int) -> float:
    return round(100.0 * numerator / denominator, 4) if denominator else 0.0


def build_data_quality_report(
    metadata_path: Path,
    atd_path: Path,
    smart_tagging_path: Path,
    homography_path: Path,
    game: str = GAME,
) -> dict:
    """Stream tactical inputs and return aggregate-only quality metrics; never emit frame rows."""
    frame_count = source_frames("tactical", game)
    metadata = parse_atd_metadata(metadata_path, game)
    half_labels, half_ranges = half_index_by_video_frame(frame_count, game)
    bucket_names = {0: "ungraded", 1: "first_half", 2: "second_half"}
    frame_counts = Counter()
    ball_valid = Counter()
    player_observations = Counter()
    player_valid = Counter()
    player_speed_valid = Counter()
    ball_speed_valid = Counter()
    player_count_distribution: Dict[str, Counter] = {name: Counter() for name in bucket_names.values()}
    for frame in iter_atd_frames(atd_path, metadata, frame_count, "tactical", game):
        bucket = bucket_names[half_labels[frame.video_frame]]
        frame_counts[bucket] += 1
        player_observations[bucket] += len(frame.players)
        valid_count = sum(int(observation.valid) for observation in frame.players)
        player_valid[bucket] += valid_count
        player_speed_valid[bucket] += sum(int(observation.speed_valid) for observation in frame.players)
        player_count_distribution[bucket][str(valid_count)] += 1
        ball_valid[bucket] += int(frame.ball.valid)
        ball_speed_valid[bucket] += int(frame.ball.speed_valid)

    events = parse_smart_tagging(smart_tagging_path, GAMES[game]["fps"], frame_count)
    event_codes = Counter(event.code or "(missing)" for event in events)
    event_teams = Counter(event.team if event.team is not None else "(missing)" for event in events)
    homography = load_homography_arrays(homography_path, frame_count)

    coverage = {}
    for bucket in bucket_names.values():
        n_frames = frame_counts[bucket]
        n_players = player_observations[bucket]
        row = {
            "frame_count": n_frames,
            "ball_observed_frames": ball_valid[bucket],
            "ball_visibility_percent": _ratio(ball_valid[bucket], n_frames),
            "player_observations": n_players,
            "valid_player_positions": player_valid[bucket],
            "invalid_player_positions": n_players - player_valid[bucket],
            "valid_player_speeds": player_speed_valid[bucket],
            "invalid_player_speeds": n_players - player_speed_valid[bucket],
            "valid_ball_speeds": ball_speed_valid[bucket],
            "invalid_ball_speeds": n_frames - ball_speed_valid[bucket],
            "tracked_player_count_distribution": dict(sorted(
                player_count_distribution[bucket].items(), key=lambda item: int(item[0])
            )),
        }
        coverage[bucket] = row
    coverage["first_half"]["video_frame_range_inclusive"] = list(half_ranges[1])
    coverage["second_half"]["video_frame_range_inclusive"] = list(half_ranges[2])
    coverage["ungraded"]["video_frame_count"] = frame_count - sum(
        last - first + 1 for first, last in half_ranges.values()
    )

    return {
        "schema_version": 1,
        "source": "tactical",
        "frame_count": frame_count,
        "fps": GAMES[game]["fps"],
        "alignment": {
            "ATD_frame_id_first": 1,
            "ATD_frame_id_last": frame_count,
            "submission_video_frame_first": 0,
            "submission_video_frame_last": frame_count - 1,
            "rule": "video_frame = frame_id - 1; graded halves come from games.py",
        },
        "metadata": {
            "team_slot_counts": dict(Counter(slot.team for slot in metadata.slots)),
            "track_slot_count": len(metadata.slots),
            "pitch_length_m": metadata.pitch_length_m,
            "pitch_width_m": metadata.pitch_width_m,
            "declared_pitch_length_m": metadata.declared_pitch_length_m,
            "declared_pitch_width_m": metadata.declared_pitch_width_m,
            "missing_semantics": metadata.missing_semantics,
        },
        "coverage_by_half": coverage,
        "invalid_observations": {
            "player_position_count": sum(player_observations.values()) - sum(player_valid.values()),
            "player_speed_count": sum(player_observations.values()) - sum(player_speed_valid.values()),
            "ball_position_count": frame_count - sum(ball_valid.values()),
            "ball_speed_count": frame_count - sum(ball_speed_valid.values()),
            "homography_frame_count": frame_count - sum(homography.valid),
        },
        "smart_tagging": {
            "event_count": len(events),
            "counts_by_code": dict(sorted(event_codes.items())),
            "counts_by_normalized_team": dict(sorted(event_teams.items())),
        },
        "homography": {
            "frame_count": len(homography.valid),
            "valid_frames": sum(homography.valid),
            "invalid_frames": len(homography.valid) - sum(homography.valid),
            "mapping_direction": homography.mapping_direction,
        },
    }


def _sha256(path: Path, chunk_size: int = 4 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_asset_inventory(data_dir: Optional[Path] = None, game: str = GAME) -> dict:
    """Hash all expected assets locally and return only a manifest for ignored local storage."""
    manifest = {"schema_version": 1, "game": game, "sources": []}
    for source in ("tactical", "broadcast"):
        paths = asset_paths(game, str(data_dir) if data_dir is not None else None, source)
        source_assets = []
        for key, filename in paths.items():
            path = Path(filename)
            if not path.is_file():
                raise FileNotFoundError("missing {} {} asset".format(source, key))
            source_assets.append({
                "asset_id": "{}.{}".format(source, key),
                "filename": path.name,
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            })
        manifest["sources"].append({"source": source, "assets": source_assets})
    return manifest


def write_local_json(path: Path, payload: Mapping[str, object]) -> None:
    """Write aggregate/provenance JSON to a caller-selected local path."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Inventory local assets and summarize tactical data quality.")
    parser.add_argument("--data-dir", type=Path, help="bundle root; defaults to MTAH_DATA_DIR or ./data")
    parser.add_argument("--inventory-out", type=Path,
                        default=Path(".local-checkpoints/phase2_asset_inventory.json"))
    parser.add_argument("--quality-out", type=Path,
                        default=Path(".local-checkpoints/phase2_data_quality.json"))
    parser.add_argument("--inventory-only", action="store_true", help="skip ATD/tag/homography quality scan")
    parser.add_argument("--quality-only", action="store_true", help="skip hashing the video assets")
    args = parser.parse_args(argv)
    data_dir = args.data_dir or (Path(os.environ["MTAH_DATA_DIR"]) if os.environ.get("MTAH_DATA_DIR") else None)
    try:
        inventory = None
        if not args.quality_only:
            inventory = build_asset_inventory(data_dir)
            write_local_json(args.inventory_out, inventory)
        report = None
        if not args.inventory_only:
            paths = asset_paths(data_dir=str(data_dir) if data_dir else None)
            report = build_data_quality_report(
                Path(paths["atd_meta"]), Path(paths["atd_raw"]),
                Path(paths["smart_tagging"]), Path(paths["homography"]),
            )
            write_local_json(args.quality_out, report)
        output = {"status": "ok"}
        if inventory is not None:
            output["asset_files_verified"] = sum(len(item["assets"]) for item in inventory["sources"])
            output["inventory_manifest"] = str(args.inventory_out)
        if report is not None:
            output["tactical_frames_verified"] = report["frame_count"]
            output["track_slots"] = report["metadata"]["track_slot_count"]
            output["smart_tagging_events"] = report["smart_tagging"]["event_count"]
            output["quality_report"] = str(args.quality_out)
        print(json.dumps(output, indent=2, sort_keys=True))
        return 0
    except (OSError, ET.ParseError, IngestionError, KeyError, ValueError) as error:
        print("Phase 2 ingestion failed: {}".format(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(_main())
