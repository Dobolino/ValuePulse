"""Sportarten, die ValuePulse kennt.

Fußball ist an die bestehenden Quellen angeschlossen. Die anderen Sportarten
sind vorbereitet und filtern das Dashboard, liefern aber noch keine eigenen
Spiele. Esports ist absichtlich nicht enthalten.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Sport:
    id: str
    name: str
    icon: str
    live: bool
    odds_sport: str | None
    note: str


SPORTS: tuple[Sport, ...] = (
    Sport("football", "Fußball", "⚽", True, "soccer", "Football-Data und The Odds API."),
    Sport("tennis", "Tennis", "🎾", False, "tennis_atp", "Quelle vorbereitet, noch nicht abgefragt."),
    Sport("basketball", "Basketball", "🏀", False, "basketball_nba", "Quelle vorbereitet, noch nicht abgefragt."),
    Sport("baseball", "Baseball", "⚾", False, "baseball_mlb", "Quelle vorbereitet, noch nicht abgefragt."),
    Sport("ufc", "UFC", "🥊", False, "mma_mixed_martial_arts", "Quelle vorbereitet, noch nicht abgefragt."),
    Sport(
        "american_football",
        "American Football",
        "🏈",
        False,
        "americanfootball_nfl",
        "Quelle vorbereitet, noch nicht abgefragt.",
    ),
    Sport("darts", "Darts", "🎯", False, None, "Noch keine Quotenquelle hinterlegt."),
)

_BY_ID = {sport.id: sport for sport in SPORTS}


def sport_by_id(sport_id: str) -> Sport:
    try:
        return _BY_ID[sport_id]
    except KeyError as exc:
        raise ValueError(f"Unbekannte Sportart: {sport_id}") from exc


def provider_plan(sport_id: str) -> str:
    """Welche Quelle die Pipeline für diese Sportart nutzen würde."""
    sport = sport_by_id(sport_id)
    if sport.live:
        return "football-data+the-odds-api"
    if sport.odds_sport:
        return f"nicht-angeschlossen:{sport.odds_sport}"
    return "nicht-angeschlossen"
