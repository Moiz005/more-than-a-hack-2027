"""Weak, type-aware Smart Tagging features for E03.

Intervals are observations and contextual priors only. They are never labels.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from starter_v5.ingestion import SmartTagEvent


FAMILY_BY_CODE = {
    "BUILD UP": "attacking_phase",
    "PROGRESSION": "attacking_phase",
    "ATTACKING TRANSITION": "attacking_phase",
    "BALL IN FINAL THIRD": "attacking_context",
    "BALL IN THE BOX": "attacking_context",
    "PLAYERS IN THE BOX": "attacking_context",
    "CREATING CHANCES": "attacking_context",
    "LONG BALL": "attacking_context",
    "DEFENSIVE TRANSITION": "defensive_context",
    "DEFENDING IN DEFENSIVE THIRD": "defensive_context",
    "DEFENDING IN MIDDLE THIRD": "defensive_context",
    "DEFENDING IN ATTACKING THIRD": "defensive_context",
    "SET PIECES": "restart",
    "GOALS": "goal_context",
}
RESTART_TYPES = frozenset({
    "throw-in", "corner kick", "goal kick", "free kick",
    "kick off (after goal)", "kick off (start)",
})


@dataclass(frozen=True)
class TagEvidence:
    active: bool = False
    team_prior: Optional[str] = None
    home_prior: float = 0.0
    away_prior: float = 0.0
    restart_context: bool = False
    restart_type: Optional[str] = None
    goal_context: bool = False
    team_conflict: bool = False
    overlap: bool = False
    capped: bool = False
    unknown_codes: Tuple[str, ...] = ()
    families: Tuple[str, ...] = ()


def _norm(value: Optional[str]) -> str:
    return " ".join((value or "").casefold().split())


def _team(value: Optional[str]) -> Optional[str]:
    folded = _norm(value)
    if folded == "barcelona":
        return "H"
    if folded in {"atletic club", "athletic club", "athletic"}:
        return "A"
    return None


def iter_tag_evidence(events: Iterable[SmartTagEvent], frame_count: int) -> List[TagEvidence]:
    """Return one neutral-or-active record per frame using half-open intervals."""
    if isinstance(frame_count, bool) or not isinstance(frame_count, int) or frame_count < 0:
        raise ValueError("frame_count must be a non-negative integer")
    starts: Dict[int, List[SmartTagEvent]] = {}
    ends: Dict[int, List[SmartTagEvent]] = {}
    for event in events:
        if event.start_frame < 0 or event.end_frame < event.start_frame or event.end_frame > frame_count:
            raise ValueError("Smart Tag interval is outside the frame timeline")
        if event.start_frame == event.end_frame:
            continue
        starts.setdefault(event.start_frame, []).append(event)
        ends.setdefault(event.end_frame, []).append(event)

    active: List[SmartTagEvent] = []
    output: List[TagEvidence] = []
    for frame in range(frame_count):
        if frame in ends:
            exiting = set(id(item) for item in ends[frame])
            active = [item for item in active if id(item) not in exiting]
        active.extend(starts.get(frame, ()))
        if not active:
            output.append(TagEvidence())
            continue
        families = set()
        unknown_codes = set()
        teams = set()
        restart_types = set()
        for item in active:
            code = " ".join(item.code.upper().split())
            family = FAMILY_BY_CODE.get(code)
            if family is None:
                unknown_codes.add(code)
                continue
            families.add(family)
            if family in {"attacking_phase", "attacking_context", "restart", "goal_context"}:
                team = _team(item.tags.get("Team"))
                if team:
                    teams.add(team)
            if family == "restart":
                restart_type = " ".join(_norm(item.tags.get("Type")).split())
                if restart_type in RESTART_TYPES:
                    restart_types.add(restart_type)
        conflict = len(teams) > 1
        # One capped unit of prior per team, irrespective of correlated overlapping tags.
        home = 0.0 if conflict else float("H" in teams)
        away = 0.0 if conflict else float("A" in teams)
        team_prior = next(iter(teams)) if len(teams) == 1 else None
        output.append(TagEvidence(
            active=True,
            team_prior=team_prior,
            home_prior=home,
            away_prior=away,
            restart_context=bool(restart_types),
            restart_type=sorted(restart_types)[0] if restart_types else None,
            goal_context="goal_context" in families,
            team_conflict=conflict,
            overlap=len(active) > 1,
            capped=len(active) > 1 and bool(teams),
            unknown_codes=tuple(sorted(unknown_codes)),
            families=tuple(sorted(families)),
        ))
    return output
