"""Beispiel-Liga, falls Schlüssel fehlen oder nichts Speicherbares da ist.

Die Quoten werden aus demselben Modell abgeleitet wie im Live-Betrieb,
damit die Ampel im Demo-Modus nachvollziehbar bleibt. Value-Signale bleiben
gelb, weil Beispiel-Daten keine belastbare Grundlage sind.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from valuepulse.model import strength_from_table
from valuepulse.models import Fixture, Quote, Standing

DEMO_CODE = "DEMO"
DEMO_NAME = "Demo-Liga"


def demo_table() -> list[Standing]:
    raw = (
        ("Nordstern", 10, 24, 22, 8),
        ("Südwall", 10, 16, 15, 12),
        ("Ostheim", 10, 12, 12, 14),
        ("Westbrück", 10, 5, 7, 22),
    )
    return [
        Standing(
            competition_code=DEMO_CODE,
            team=name,
            played=played,
            points=points,
            goals_for=goals_for,
            goals_against=goals_against,
        )
        for name, played, points, goals_for, goals_against in raw
    ]


def build_demo(now: datetime, reason: str) -> tuple[list[Fixture], list[Standing], list[Quote], str]:
    """Vier Spiele: zwei mit klarem Edge, zwei fair bepreist."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    table = demo_table()
    pairs = (
        ("Nordstern", "Westbrück", 1, "value-home"),
        ("Südwall", "Ostheim", 2, "fair"),
        ("Westbrück", "Nordstern", 3, "value-away"),
        ("Ostheim", "Südwall", 4, "fair"),
    )
    fixtures: list[Fixture] = []
    quotes: list[Quote] = []
    for home, away, offset, kind in pairs:
        kickoff = (now + timedelta(days=offset)).replace(minute=30, second=0, microsecond=0)
        fixtures.append(
            Fixture(
                competition=DEMO_NAME,
                competition_code=DEMO_CODE,
                kickoff=kickoff,
                home=home,
                away=away,
                match_id=f"demo-{offset}",
            )
        )
        model = strength_from_table(home, away, table)
        quotes.extend(_books(home, away, kickoff, model.probs, kind, now))
    banner = (
        "Demo-Modus mit Beispiel-Daten. "
        f"{reason} "
        "Grün erscheint erst bei frischen echten Quoten. "
        "Ein Value in den Beispielen bleibt gelb."
    )
    return fixtures, table, quotes, banner


def _books(
    home: str,
    away: str,
    kickoff: datetime,
    probs: dict[str, float],
    kind: str,
    now: datetime,
) -> list[Quote]:
    nudged = dict(probs)
    if kind == "value-home":
        nudged["home"] = max(0.08, probs["home"] - 0.10)
    elif kind == "value-away":
        nudged["away"] = max(0.08, probs["away"] - 0.10)
    else:
        # Buchmacher-Marge: jede Quote ist etwas kürzer als das Modell.
        nudged = {key: min(0.92, value * 1.05) for key, value in probs.items()}

    def prices(scale: float) -> dict[str, float]:
        return {key: max(1.05, (1.0 / nudged[key]) * scale) for key in nudged}

    primary = prices(1.0)
    secondary = prices(0.98)
    stamp = now - timedelta(minutes=20)
    return [
        Quote(
            competition=DEMO_NAME,
            kickoff=kickoff,
            home=home,
            away=away,
            bookmaker="Beispiel-Buch",
            home_odds=primary["home"],
            draw_odds=primary["draw"],
            away_odds=primary["away"],
            last_update=stamp,
            source="demo",
        ),
        Quote(
            competition=DEMO_NAME,
            kickoff=kickoff,
            home=home,
            away=away,
            bookmaker="Beispiel-Wette",
            home_odds=secondary["home"],
            draw_odds=secondary["draw"],
            away_odds=secondary["away"],
            last_update=stamp,
            source="demo",
        ),
    ]

