"""Tippschein aus Value-Signalen.

Der Schein nimmt nur Spiele mit einem Edge über 3 %. Dieselbe Mannschaft
kommt nur einmal vor, damit ein Kombitipp nicht zweimal auf dasselbe Team setzt.
Fehlen nach diesen Prüfungen Spiele, wird der Schein gekürzt.
"""

from __future__ import annotations

from dataclasses import dataclass

from valuepulse.config import EDGE_MIN
from valuepulse.models import BookLine, MatchView
from valuepulse.names import names_match
from valuepulse.pro import fractional_kelly

MIN_LEGS = 2
MAX_LEGS = 10
LOW_RISK_MIN_PROBABILITY = 0.55
SOLID_QUALITY = 60
# Viertel-Kelly der Kombi, je Risiko gedeckelt. Spanne: 1 % bis 2 % der Bankroll.
STAKE_CAP = {
    "wenig": 0.01,
    "mittel": 0.015,
    "hoch": 0.02,
}
RISK_LABELS = {
    "wenig": "Wenig Risiko",
    "mittel": "Mittel",
    "hoch": "Hoch",
}
_EDGE_PERCENT = round(EDGE_MIN * 100, 1)


@dataclass(frozen=True)
class SlipLeg:
    competition: str
    kickoff_label: str
    home: str
    away: str
    pick_label: str
    odds: float
    probability: float
    edge: float
    quality: int


@dataclass(frozen=True)
class Slip:
    risk: str
    risk_label: str
    requested: int
    legs: tuple[SlipLeg, ...]
    shortened: bool
    warning: str
    combined_odds: float | None
    combined_probability: float | None
    stake: float
    stake_cap: float
    stake_capped: bool
    copy_text: str
    bookmaker: str = ""


def build_slip(matches: list[MatchView], *, count: int, risk: str) -> Slip:
    """Wählt die besten N Spiele für die Risikostufe und rechnet die Kombi."""
    if risk not in STAKE_CAP:
        raise ValueError(f"Unbekannte Risikostufe: {risk}")
    requested = min(MAX_LEGS, max(MIN_LEGS, int(count)))
    ranked = sorted(_eligible(matches, risk), key=lambda match: _sort_key(match, risk), reverse=True)
    chosen = _without_shared_teams(ranked, requested)
    playable, bookmaker, prices = _one_bookmaker(chosen)
    legs = tuple(_leg(match, price) for match, price in zip(playable, prices))
    shortened = len(legs) < requested
    warning = shortened_warning(len(legs), requested) if shortened else ""
    if shortened and chosen and len(playable) < len(chosen):
        warning = f"{warning}\nDer Schein nutzt nur Spiele, die derselbe Buchmacher anbietet."
    if legs:
        combined_odds = 1.0
        combined_probability = 1.0
        for leg in legs:
            combined_odds *= leg.odds
            combined_probability *= leg.probability
        raw_stake = fractional_kelly(combined_probability, combined_odds)
    else:
        combined_odds = None
        combined_probability = None
        raw_stake = 0.0
    cap = STAKE_CAP[risk]
    stake = min(raw_stake, cap)
    slip = Slip(
        risk=risk,
        risk_label=RISK_LABELS[risk],
        requested=requested,
        legs=legs,
        shortened=shortened,
        warning=warning,
        combined_odds=combined_odds,
        combined_probability=combined_probability,
        stake=stake,
        stake_cap=cap,
        stake_capped=raw_stake > cap,
        copy_text="",
        bookmaker=bookmaker,
    )
    return Slip(
        risk=slip.risk,
        risk_label=slip.risk_label,
        requested=slip.requested,
        legs=slip.legs,
        shortened=slip.shortened,
        warning=slip.warning,
        combined_odds=slip.combined_odds,
        combined_probability=slip.combined_probability,
        stake=slip.stake,
        stake_cap=slip.stake_cap,
        stake_capped=slip.stake_capped,
        copy_text=copy_text(slip),
        bookmaker=slip.bookmaker,
    )


def shortened_warning(found: int, requested: int) -> str:
    """Gelber Hinweis, wenn weniger Spiele übrig bleiben als angefordert."""
    if found == 1:
        sentence = "Es wurde nur 1 qualifiziertes Spiel mit ausreichendem Value gefunden"
    else:
        sentence = f"Es wurden nur {found} qualifizierte Spiele mit ausreichendem Value gefunden"
    return f"Spielschein gekürzt!\n{sentence} (angefordert: {requested})."


def copy_text(slip: Slip) -> str:
    """Klartext, den man in einen Wettschein übernehmen kann."""
    lines = [f"ValuePulse Tippschein · {slip.risk_label} · angefordert {slip.requested}"]
    if slip.bookmaker:
        lines.append(f"Buchmacher: {slip.bookmaker}")
    if slip.shortened:
        lines.append(slip.warning.replace("\n", " "))
    if not slip.legs:
        lines.append("Keine qualifizierten Spiele.")
        return "\n".join(lines)
    for index, leg in enumerate(slip.legs, start=1):
        lines.append(
            f"{index}. {leg.competition}: {leg.home} – {leg.away} | {leg.pick_label} | "
            f"Quote {_decimal(leg.odds)} | Modell {_percent(leg.probability)}"
        )
    lines.append(f"Gesamtquote: {_decimal(slip.combined_odds or 0.0)}")
    lines.append(f"Gesamt-Wahrscheinlichkeit: {_percent(slip.combined_probability or 0.0)}")
    lines.append(f"Empfohlener Gesamteinsatz: {_percent(slip.stake)} der Bankroll")
    lines.append("Rechenhilfe, keine Wettberatung.")
    return "\n".join(lines)


def _eligible(matches: list[MatchView], risk: str) -> list[MatchView]:
    picked: list[MatchView] = []
    for match in matches:
        item = match.assessment
        if item.signal not in {"green", "yellow"}:
            continue
        if round(item.edge * 100, 1) <= _EDGE_PERCENT:
            continue
        probability = item.model_probs.get(item.pick)
        decimal_odds = item.odds.get(item.pick)
        if probability is None or decimal_odds is None:
            continue
        if not 0 < probability < 1 or decimal_odds <= 1.01:
            continue
        if risk == "wenig" and (probability < LOW_RISK_MIN_PROBABILITY or item.quality < SOLID_QUALITY):
            continue
        picked.append(match)
    return picked


def _sort_key(match: MatchView, risk: str) -> tuple[float, float, float]:
    item = match.assessment
    probability = item.model_probs[item.pick]
    if risk == "wenig":
        return (probability, float(item.quality), item.edge)
    if risk == "mittel":
        return (item.edge * probability, item.edge, probability)
    return (item.edge, probability, float(item.quality))


def _without_shared_teams(ranked: list[MatchView], limit: int) -> list[MatchView]:
    chosen: list[MatchView] = []
    used: list[str] = []
    for match in ranked:
        teams = (match.home, match.away)
        if any(names_match(team, previous) for team in teams for previous in used):
            continue
        chosen.append(match)
        used.extend(teams)
        if len(chosen) >= limit:
            break
    return chosen


def _one_bookmaker(chosen: list[MatchView]) -> tuple[list[MatchView], str, list[float]]:
    """Preise nur von einem Anbieter. Ohne Buchmacherzeilen bleibt die alte Quote."""
    if not chosen or not any(match.books for match in chosen):
        if not chosen:
            return [], "", []
        names = {match.assessment.bookmaker for match in chosen}
        bookmaker = next(iter(names)) if len(names) == 1 else ""
        return chosen, bookmaker, [match.assessment.odds[match.assessment.pick] for match in chosen]

    current = list(chosen)
    while current:
        covered = _books_covering(current)
        if covered:
            bookmaker = _best_book(current, covered)
            return current, bookmaker, covered[bookmaker]
        current = current[:-1]
    return [], "", []


def _books_covering(matches: list[MatchView]) -> dict[str, list[float]]:
    tables: list[dict[str, float]] = []
    shared: set[str] | None = None
    for match in matches:
        prices: dict[str, float] = {}
        for line in match.books:
            price = _line_price(line, match.assessment.pick)
            if price > 1.01:
                prices[line.bookmaker] = price
        tables.append(prices)
        shared = set(prices) if shared is None else shared & set(prices)
    if not shared:
        return {}
    return {name: [table[name] for table in tables] for name in shared}


def _best_book(matches: list[MatchView], covered: dict[str, list[float]]) -> str:
    """Höchste Gesamtquote, bei Gleichstand der größere Value."""
    best_name = ""
    best_key: tuple[float, float] | None = None
    for name in sorted(covered):
        product = 1.0
        value = 0.0
        for match, price in zip(matches, covered[name]):
            product *= price
            probability = match.assessment.model_probs[match.assessment.pick]
            value += probability - (1.0 / price)
        key = (product, value)
        if best_key is None or key > best_key:
            best_name = name
            best_key = key
    return best_name


def _line_price(line: BookLine, pick: str) -> float:
    return {"home": line.home, "draw": line.draw, "away": line.away}[pick]


def _leg(match: MatchView, odds: float | None = None) -> SlipLeg:
    item = match.assessment
    price = item.odds[item.pick] if odds is None else odds
    probability = item.model_probs[item.pick]
    edge = item.edge if odds is None else probability - (1.0 / price)
    return SlipLeg(
        competition=match.competition,
        kickoff_label=match.kickoff_label,
        home=match.home,
        away=match.away,
        pick_label=item.pick_label,
        odds=price,
        probability=probability,
        edge=edge,
        quality=item.quality,
    )


def _decimal(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def _percent(value: float) -> str:
    return f"{value * 100:.1f}".replace(".", ",") + " %"
