"""Tor-Modell, Edge und Ampel.

Das Modell ist bewusst klein: Aus der Tabelle werden erwartete Tore geschätzt,
daraus per Poisson die Drei-Weg-Wahrscheinlichkeiten. Der Edge ist der erwartete Nettoertrag je eingesetzter Einheit: p × Quote − 1.

Eine Quote älter als 24 Stunden oder ein API-Limit senkt nur die Datenqualität.
Die Rechnung läuft trotzdem.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

from valuepulse.config import EDGE_MIN, QUALITY_GREEN_MIN, STALE_ODDS_HOURS, MAX_SIGNAL_EV, MIN_SIGNAL_QUALITY, MAX_SINGLE_ODDS
from valuepulse.models import Assessment, Quote, Standing
from valuepulse.names import names_match

OUTCOME_LABELS = {
    "home": "Heimsieg",
    "draw": "Unentschieden",
    "away": "Auswärtssieg",
}

# Heimsieg-Vorteil, wenn zwei gleich starke Teams aufeinandertreffen.
_HOME_BOOST = 1.15
_AWAY_BOOST = 0.90
# Zieht extreme Tabellenwerte zur Mitte, damit kleine Stichproben nicht übertreiben.
_SHRINK = 0.65
_MAX_GOALS = 8


def expected_value(probability: float, odds: float) -> float:
    """Expected net return per unit stake, independent of bookmaker margin."""
    if not math.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("Wahrscheinlichkeit muss zwischen 0 und 1 liegen.")
    if not math.isfinite(odds) or odds <= 1:
        raise ValueError("Quote muss endlich und größer als 1 sein.")
    return probability * odds - 1.0


def pct(value: float, digits: int = 1) -> str:
    """Deutsche Prozentzahl, z. B. 5,2 %."""
    number = f"{value * 100:.{digits}f}".replace(".", ",")
    return f"{number} %"


def decimal_de(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def poisson_pmf(goals: int, expected: float) -> float:
    if expected <= 0:
        return 1.0 if goals == 0 else 0.0
    probability = math.exp(-expected)
    for step in range(1, goals + 1):
        probability *= expected / step
    return probability


def scoreline_probs(home_xg: float, away_xg: float) -> dict[str, float]:
    """Summiert alle Spielstände bis 8 Tore und verteilt den Rest proportional."""
    home = draw = away = 0.0
    for home_goals in range(_MAX_GOALS + 1):
        home_p = poisson_pmf(home_goals, home_xg)
        for away_goals in range(_MAX_GOALS + 1):
            probability = home_p * poisson_pmf(away_goals, away_xg)
            if home_goals > away_goals:
                home += probability
            elif home_goals == away_goals:
                draw += probability
            else:
                away += probability
    total = home + draw + away
    if total <= 0:
        return {"home": 0.34, "draw": 0.28, "away": 0.38}
    return {"home": home / total, "draw": draw / total, "away": away / total}


def _clamp_xg(value: float) -> float:
    return max(0.15, min(3.4, value))


@dataclass
class StrengthModel:
    probs: dict[str, float]
    home_xg: float | None
    away_xg: float | None
    used_table: bool
    note: str | None = None


def strength_from_table(home: str, away: str, table: list[Standing]) -> StrengthModel:
    """Erwartete Tore aus Toren und Gegentoren der Liga-Tabelle."""
    usable = [row for row in table if row.played >= 5]
    home_row = next((row for row in usable if names_match(row.team, home)), None)
    away_row = next((row for row in usable if names_match(row.team, away)), None)
    if home_row is None or away_row is None or len(usable) < 4:
        probs = scoreline_probs(1.45, 1.15)
        return StrengthModel(
            probs=probs,
            home_xg=1.45,
            away_xg=1.15,
            used_table=False,
            note="Tabellenwerte fehlen. Das Modell nutzt einen neutralen Erfahrungswert mit leichtem Heimsieg-Vorteil.",
        )

    per_game = [row.goals_for / row.played for row in usable]
    league_gpg = sum(per_game) / len(per_game)
    if league_gpg <= 0.05:
        league_gpg = 1.3

    def factor(raw: float) -> float:
        shrunk = 1.0 + (raw - 1.0) * _SHRINK
        return max(0.35, min(2.2, shrunk))

    def attack(row: Standing) -> float:
        return factor((row.goals_for / row.played) / league_gpg)

    def defense(row: Standing) -> float:
        # Über 1: die Abwehr kassiert mehr als der Ligadurchschnitt.
        return factor((row.goals_against / row.played) / league_gpg)

    home_xg = _clamp_xg(league_gpg * _HOME_BOOST * attack(home_row) * defense(away_row))
    away_xg = _clamp_xg(league_gpg * _AWAY_BOOST * attack(away_row) * defense(home_row))
    return StrengthModel(
        probs=scoreline_probs(home_xg, away_xg),
        home_xg=home_xg,
        away_xg=away_xg,
        used_table=True,
        note=None,
    )


def best_prices(quotes: list[Quote]) -> tuple[dict[str, float], dict[str, str], dict[str, datetime | None]]:
    """Höchste Quote je Ausgang und der Buchmacher, der sie stellt."""
    prices = {"home": 0.0, "draw": 0.0, "away": 0.0}
    books = {"home": "", "draw": "", "away": ""}
    updated: dict[str, datetime | None] = {"home": None, "draw": None, "away": None}
    fields = (
        ("home", "home_odds"),
        ("draw", "draw_odds"),
        ("away", "away_odds"),
    )
    for quote in quotes:
        for key, attr in fields:
            price = getattr(quote, attr)
            if math.isfinite(price) and price > prices[key]:
                prices[key] = price
                books[key] = quote.bookmaker
                updated[key] = quote.last_update
    return prices, books, updated


def data_quality(
    *,
    odds_age_hours: float | None,
    used_table: bool,
    bookmaker_count: int,
    api_limited: bool,
    is_demo: bool,
    stale_table: bool = False,
) -> tuple[int, list[str]]:
    """Punktzahl 0–100. Abzüge erklären sich selbst in Klartext.

    Abzüge sind so gewählt, dass veraltete Quoten, fehlende Tabellen oder ein
    API-Limit ein Value-Signal von Grün auf Gelb ziehen.
    """
    if is_demo:
        return 45, [
            "Das sind Beispiel-Daten. Die Datenqualität ist deshalb bewusst niedrig, ein Signal bleibt gelb."
        ]

    score = 100
    notes: list[str] = []
    if odds_age_hours is None:
        score -= 15
        notes.append("Zum Alter der Quote liegt keine Angabe vor.")
    elif odds_age_hours > 72:
        score -= 45
        notes.append(f"Die Quote ist rund {odds_age_hours:.0f} Stunden alt.")
    elif odds_age_hours > STALE_ODDS_HOURS:
        score -= 30
        notes.append(
            f"Die Quote ist älter als 24 Stunden (rund {odds_age_hours:.0f} Stunden). "
            "Es gibt einen Abzug bei der Datenqualität, die Rechnung läuft weiter."
        )
    elif odds_age_hours > 12:
        score -= 10
        notes.append("Die Quote ist mehrere Stunden alt, aber noch innerhalb von 24 Stunden.")

    if not used_table:
        score -= 30
        notes.append("Ohne vollständige Tabelle ist die Modellschätzung unsicherer.")
    elif stale_table:
        score -= 15
        notes.append(
            "Die Tabelle ist älter als 24 Stunden oder ihre Saison ist nicht passend belegt. Die Datenqualität ist deshalb niedriger."
        )
    if bookmaker_count < 2:
        score -= 10
        notes.append("Nur ein Buchmacher hat eine Quote geliefert.")
    if api_limited:
        score -= 30
        notes.append("Das API-Limit oder eine Störung greift. ValuePulse nutzt gespeicherte Quoten.")

    return max(0, min(100, score)), notes


def assess(
    *,
    model: StrengthModel,
    quotes: list[Quote],
    now: datetime,
    api_limited: bool = False,
    is_demo: bool = False,
    stale_table: bool = False,
) -> Assessment | None:
    """Baut Ampel, Überschrift und Klartext. Gibt None zurück, wenn Quoten fehlen."""
    if not quotes:
        return None
    prices, books, updated = best_prices(quotes)
    if min(prices.values()) <= 1.01:
        return None

    implied = {key: 1.0 / prices[key] for key in prices}
    edges = {key: expected_value(model.probs[key], prices[key]) for key in prices}
    value_keys = [key for key, value in edges.items() if value > EDGE_MIN + 1e-12
                  and value <= MAX_SIGNAL_EV + 1e-12 and prices[key] <= MAX_SINGLE_ODDS]
    if value_keys:
        pick = max(value_keys, key=lambda key: edges[key])
        is_value = True
    else:
        # Ohne Vorteil erklären wir den wahrscheinlichsten Ausgang, nicht den kleinsten Abzug.
        pick = max(model.probs, key=model.probs.get)
        is_value = False
    edge = edges[pick]

    moment = updated.get(pick)
    if moment is not None and moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    age = None if moment is None else (now - moment).total_seconds() / 3600

    quality, notes = data_quality(
        odds_age_hours=age,
        used_table=model.used_table,
        bookmaker_count=len({quote.bookmaker for quote in quotes}),
        api_limited=api_limited,
        is_demo=is_demo,
        stale_table=stale_table,
    )
    if model.note:
        notes.insert(0, model.note)

    if age is None or age < 0:
        is_value = False
        notes.append("Signal gesperrt: Quotenzeitpunkt fehlt oder liegt in der Zukunft.")
    if max(edges.values()) > MAX_SIGNAL_EV:
        notes.append("EV über 15 %: auffällige Ausgänge sind für Tipps gesperrt; Rohwerte bleiben sichtbar.")
    if not is_demo and (quality < MIN_SIGNAL_QUALITY or not model.used_table or stale_table):
        is_value = False
        notes.append("Signal gesperrt: ausreichende, aktuelle Tabellen und Datenqualität ab 60 erforderlich.")
    if is_value and quality >= QUALITY_GREEN_MIN:
        signal = "green"
        headline = f"Tipp: {OUTCOME_LABELS[pick]} | EV: {pct(edge)}"
    elif is_value:
        signal = "yellow"
        headline = "Tipp theoretisch möglich, aber Datenqualität verringert."
    else:
        signal = "red"
        headline = "Kein freigegebenes Value-Signal."

    explanation = _explain(pick, model, prices, books, implied, edge, quality, notes, is_value)
    return Assessment(
        pick=pick,
        pick_label=OUTCOME_LABELS[pick],
        edge=edge,
        model_probs=model.probs,
        odds=prices,
        implied=implied,
        bookmaker=books[pick],
        quality=quality,
        quality_notes=notes,
        signal=signal,
        headline=headline,
        explanation=explanation,
        home_xg=model.home_xg,
        away_xg=model.away_xg,
        used_table=model.used_table,
        is_demo=is_demo,
        api_limited=api_limited,
        stale_table=stale_table,
        probability_gap=model.probs[pick] - implied[pick],
        book_odds={q.bookmaker: {"home": q.home_odds, "draw": q.draw_odds, "away": q.away_odds}
                   for q in quotes if all(math.isfinite(v) and v > 1.01 for v in (q.home_odds,q.draw_odds,q.away_odds))},
    )


def _explain(
    pick: str,
    model: StrengthModel,
    prices: dict[str, float],
    books: dict[str, str],
    implied: dict[str, float],
    edge: float,
    quality: int,
    notes: list[str],
    is_value: bool,
) -> str:
    label = OUTCOME_LABELS[pick]
    sentence = (
        f"Modell sieht {label} bei {pct(model.probs[pick], 0)}, "
        f"Quote {decimal_de(prices[pick])} entspricht {pct(implied[pick], 0)} "
        f"→ {pct(edge)} EV (Modell × Quote − 1)."
    )
    if model.used_table and model.home_xg is not None and model.away_xg is not None:
        goals = (
            f" Aus der Tabelle ergeben sich etwa {decimal_de(model.home_xg)} erwartete Tore "
            f"für die Heimmannschaft und {decimal_de(model.away_xg)} für die Gäste."
        )
    else:
        goals = ""
    book = f" Beste Quote für {label}: {decimal_de(prices[pick])} bei {books[pick]}."
    if is_value:
        verdict = " Der Vorteil liegt über der Schwelle von 3 %."
    else:
        verdict = (
            " Kein freigegebener Tipp: EV, Quote oder Daten erfüllen die Schutzregeln nicht."
        )
    extra = " ".join(notes)
    quality_line = f" Datenqualität: {quality} %."
    return f"{sentence}{goals}{book}{verdict} {extra}{quality_line}"
