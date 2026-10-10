"""Tippschein aus Value-Signalen.

Der Schein nimmt nur Spiele mit einem Edge über 3 %. Dieselbe Mannschaft
kommt nur einmal vor, damit ein Kombitipp nicht zweimal auf dasselbe Team setzt.
Fehlen nach diesen Prüfungen Spiele, wird der Schein gekürzt.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import math

from valuepulse.config import EDGE_MIN, MAX_SIGNAL_EV, MIN_SIGNAL_QUALITY, MAX_SINGLE_ODDS, MAX_COMBINED_ODDS, QUOTE_CONFIRM_MINUTES
from valuepulse.model import data_quality, expected_value, OUTCOME_LABELS
from valuepulse.models import MatchView
from valuepulse.names import names_match
from valuepulse.pro import fractional_kelly

MIN_LEGS = 2
MAX_LEGS = 10
LOW_RISK_MIN_PROBABILITY = 0.55
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
    checked_at: datetime | None = None
    exclusions: tuple[str, ...] = ()


def build_slip(matches: list[MatchView], *, count: int, risk: str,
               now: datetime | None = None, require_live: bool = False, only_pick: str | None = None) -> Slip:
    """Validate each actual bookmaker price before ranking and combining.

    No invented/mixed bookmaker fallback. The shortlist is rebuilt separately
    for each provider; every leg uses fresh data and the final quoted EV.
    """
    if risk not in STAKE_CAP:
        raise ValueError(f"Unbekannte Risikostufe: {risk}")
    if only_pick is not None and only_pick not in OUTCOME_LABELS:
        raise ValueError("Unbekannter Ausgang.")
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    requested = min(MAX_LEGS, max(MIN_LEGS, int(count)))
    by_book: dict[str, list[tuple[MatchView, SlipLeg]]] = {}
    reasons: set[str] = set()
    for match in matches:
        item = match.assessment
        if (set(item.model_probs) != set(OUTCOME_LABELS) or
            any(not math.isfinite(p) or not 0 <= p <= 1 for p in item.model_probs.values()) or
            not math.isclose(sum(item.model_probs.values()),1.0,abs_tol=1e-6)):
            reasons.add("Ungültige Modellwahrscheinlichkeiten ausgeschlossen.")
            continue
        if match.kickoff <= moment:
            reasons.add("Bereits begonnene Spiele ausgeschlossen.")
            continue
        if item.is_demo or not item.used_table or item.stale_table:
            reasons.add("Demo oder fehlende/veraltete Tabellen: kein spielbarer Tipp.")
            continue
        if not match.books:
            reasons.add("Ohne nachgewiesene Buchmacherquoten kein Tipp.")
            continue
        for line in match.books:
            stamp = line.last_update
            if stamp is None:
                reasons.add("Quoten ohne bestätigten Zeitstempel ausgeschlossen.")
                continue
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            age = (moment - stamp).total_seconds() / 3600
            max_age = QUOTE_CONFIRM_MINUTES / 60 if require_live else 24
            if age < 0 or age > max_age or line.source not in {"the-odds-api", "cache"} or (require_live and line.source != "the-odds-api"):
                reasons.add("Quote nicht frisch bestätigt; gespeicherte oder alte Preise gesperrt.")
                continue
            quality, _ = data_quality(odds_age_hours=age, used_table=True,
                bookmaker_count=len({b.bookmaker for b in match.books}),
                api_limited=item.api_limited, is_demo=False, stale_table=item.stale_table)
            quality = min(quality, item.quality)
            if quality < MIN_SIGNAL_QUALITY:
                reasons.add("Datenqualität unter 60: Tipp gesperrt.")
                continue
            candidates = []
            for pick, price in (("home",line.home),("draw",line.draw),("away",line.away)):
                if only_pick is not None and pick != only_pick:
                    continue
                probability = item.model_probs.get(pick, 0)
                if not math.isfinite(price) or not 1.01 < price <= MAX_SINGLE_ODDS:
                    continue
                if not math.isfinite(probability) or not 0 < probability < 1:
                    continue
                ev = expected_value(probability, price)
                if not EDGE_MIN + 1e-12 < ev <= MAX_SIGNAL_EV + 1e-12:
                    continue
                if risk == "wenig" and probability < LOW_RISK_MIN_PROBABILITY:
                    continue
                candidates.append(SlipLeg(match.competition, match.kickoff_label,
                    match.home, match.away, OUTCOME_LABELS[pick], price, probability, ev, quality))
            if candidates:
                leg = max(candidates, key=lambda leg: _rank(leg, risk))
                by_book.setdefault(line.bookmaker, []).append((match,leg))
            else:
                reasons.add("EV außerhalb (3 %, 15 %], Quote über 8 oder Risikoregel nicht erfüllt.")

    best_legs: tuple[SlipLeg, ...] = ()
    best_book = ""
    best_key = None
    for book, candidates in sorted(by_book.items()):
        chosen: list[SlipLeg] = []
        used: list[str] = []
        product = 1.0
        for match, leg in sorted(candidates, key=lambda pair: _rank(pair[1], risk), reverse=True):
            if any(names_match(team, previous) for team in (match.home,match.away) for previous in used):
                continue
            if product * leg.odds > MAX_COMBINED_ODDS:
                reasons.add("Gesamtquote auf höchstens 100 begrenzt.")
                continue
            chosen.append(leg)
            used.extend((match.home,match.away))
            product *= leg.odds
            if len(chosen) == requested:
                break
        if not chosen:
            continue
        # Prefer a complete admissible slip, then the chosen risk criterion.
        key = (len(chosen), sum(_rank(leg,risk)[0] for leg in chosen), product)
        if best_key is None or key > best_key:
            best_key, best_book, best_legs = key, book, tuple(chosen)
    combined_odds = math.prod(leg.odds for leg in best_legs) if best_legs else None
    combined_probability = math.prod(leg.probability for leg in best_legs) if best_legs else None
    raw_stake = fractional_kelly(combined_probability, combined_odds) if best_legs else 0.0
    cap = STAKE_CAP[risk]
    shortened = len(best_legs) < requested
    warning = shortened_warning(len(best_legs), requested) if shortened else ""
    if shortened:
        warning += "\nNur qualifizierte Quoten desselben Buchmachers werden kombiniert."
    slip = Slip(risk, RISK_LABELS[risk], requested, best_legs, shortened, warning,
        combined_odds, combined_probability, min(raw_stake,cap),cap,raw_stake > cap,"",
        best_book, moment, tuple(sorted(reasons)))
    return replace(slip, copy_text=copy_text(slip))


def _rank(leg: SlipLeg, risk: str) -> tuple[float, float, float]:
    if risk == "wenig":
        return leg.probability, float(leg.quality), leg.edge
    if risk == "mittel":
        return leg.edge * leg.probability, leg.edge, leg.probability
    return leg.edge, leg.probability, float(leg.quality)


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
    lines.append(f"Modellchance (Unabhängigkeit angenommen): {_percent(slip.combined_probability or 0.0)}")
    lines.append(f"Empfohlener Gesamteinsatz: {_percent(slip.stake)} der Bankroll")
    lines.append("Keine automatische Wettabgabe. Quoten vor Übernahme erneut prüfen.")
    return "\n".join(lines)


def _decimal(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def _percent(value: float) -> str:
    return f"{value * 100:.1f}".replace(".", ",") + " %"
