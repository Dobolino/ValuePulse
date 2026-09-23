"""Daten, die Pipeline und Dashboard gemeinsam benutzen."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Fixture:
    competition: str
    competition_code: str
    kickoff: datetime
    home: str
    away: str
    match_id: str


@dataclass
class Standing:
    competition_code: str
    team: str
    played: int
    points: int
    goals_for: int
    goals_against: int


@dataclass
class Quote:
    competition: str
    kickoff: datetime
    home: str
    away: str
    bookmaker: str
    home_odds: float
    draw_odds: float
    away_odds: float
    last_update: datetime | None
    source: str


@dataclass
class Assessment:
    pick: str
    pick_label: str
    edge: float
    model_probs: dict[str, float]
    odds: dict[str, float]
    implied: dict[str, float]
    bookmaker: str
    quality: int
    quality_notes: list[str]
    signal: str
    headline: str
    explanation: str
    home_xg: float | None = None
    away_xg: float | None = None
    used_table: bool = False


@dataclass
class MatchView:
    competition: str
    kickoff: datetime
    kickoff_label: str
    home: str
    away: str
    assessment: Assessment


@dataclass
class DashboardData:
    mode: str
    banner: str
    matches: list[MatchView] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    odds_requests_remaining: int | None = None
    generated_at: datetime | None = None
