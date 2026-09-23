from datetime import datetime, timedelta, timezone

from valuepulse.model import assess, data_quality, scoreline_probs, strength_from_table
from valuepulse.models import Quote, Standing


NOW = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)


def _table() -> list[Standing]:
    raw = (
        ("Nordstern", 10, 24, 22, 8),
        ("Südwall", 10, 16, 15, 12),
        ("Ostheim", 10, 12, 12, 14),
        ("Westbrück", 10, 5, 7, 22),
    )
    return [
        Standing("DEMO", name, played, points, goals_for, goals_against)
        for name, played, points, goals_for, goals_against in raw
    ]


def _quotes(model_probs: dict[str, float], home_edge: float, age_hours: float, books: int = 2) -> list[Quote]:
    """Baut Quoten so, dass nur der Heimsieg den gewünschten Edge hat."""
    kickoff = NOW + timedelta(days=1)
    updated = NOW - timedelta(hours=age_hours)

    def price(probability: float, edge: float) -> float:
        implied = min(0.95, max(0.04, probability - edge))
        return 1.0 / implied

    home_odds = price(model_probs["home"], home_edge)
    draw_odds = price(model_probs["draw"], -0.08)
    away_odds = price(model_probs["away"], -0.08)
    rows = []
    for index in range(books):
        factor = 1 - index * 0.01
        rows.append(
            Quote(
                competition="Demo-Liga",
                kickoff=kickoff,
                home="Nordstern",
                away="Westbrück",
                bookmaker=f"Buch {index}",
                home_odds=home_odds * factor,
                draw_odds=draw_odds,
                away_odds=away_odds,
                last_update=updated,
                source="the-odds-api",
            )
        )
    return rows


def test_gleiche_erwartung_ist_symmetrisch():
    probs = scoreline_probs(1.3, 1.3)
    assert abs(probs["home"] - probs["away"]) < 0.01
    assert 0.2 < probs["draw"] < 0.35
    assert abs(sum(probs.values()) - 1) < 1e-9


def test_favorit_zu_hause_liegt_deutlich_vorn():
    model = strength_from_table("Nordstern", "Westbrück", _table())
    assert model.used_table
    assert model.probs["home"] > 0.7


def test_gruen_bei_frischem_value():
    model = strength_from_table("Nordstern", "Westbrück", _table())
    result = assess(model=model, quotes=_quotes(model.probs, home_edge=0.08, age_hours=1), now=NOW)
    assert result is not None
    assert result.signal == "green"
    assert result.headline.startswith("Tipp: Heimsieg | Edge:")
    assert "Modell sieht Heimsieg bei" in result.explanation
    assert "Edge." in result.explanation


def test_exakt_drei_prozent_ist_kein_value():
    model = strength_from_table("Nordstern", "Westbrück", _table())
    result = assess(model=model, quotes=_quotes(model.probs, home_edge=0.03, age_hours=1), now=NOW)
    assert result is not None
    assert result.signal == "red"
    assert result.headline == "Kein Vorteil gegenüber dem Buchmacher."


def test_veraltete_quote_wird_gelb_statt_abbruch():
    model = strength_from_table("Nordstern", "Westbrück", _table())
    result = assess(model=model, quotes=_quotes(model.probs, home_edge=0.08, age_hours=30), now=NOW)
    assert result is not None
    assert result.signal == "yellow"
    assert result.headline == "Tipp theoretisch möglich, aber Datenqualität verringert."
    assert result.quality <= 70
    assert any("24 Stunden" in note for note in result.quality_notes)


def test_api_limit_senkt_die_qualitaet():
    score, notes = data_quality(
        odds_age_hours=1,
        used_table=True,
        bookmaker_count=3,
        api_limited=True,
        is_demo=False,
    )
    assert score == 70
    assert notes


def test_vierundzwanzig_stunden_genau_ist_noch_frisch():
    score, _notes = data_quality(
        odds_age_hours=24,
        used_table=True,
        bookmaker_count=2,
        api_limited=False,
        is_demo=False,
    )
    assert score == 90
