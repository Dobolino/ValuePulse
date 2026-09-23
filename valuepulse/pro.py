"""Pro-Metriken: Poisson-Matrix, Marge, Shin, Power und Kelly.

Die Werte erklären die Quote genauer. Sie sind keine Wettanweisung.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from valuepulse.model import poisson_pmf
from valuepulse.models import Assessment

_OUTCOMES = ("home", "draw", "away")
MATRIX_SIZE = 6


@dataclass(frozen=True)
class ProView:
    margin: float
    shin: dict[str, float]
    power: dict[str, float]
    kelly: dict[str, float]
    edge_raw: dict[str, float]
    edge_shin: dict[str, float]
    matrix: list[list[float]]
    matrix_mass: float


def bookmaker_margin(odds: list[float]) -> float:
    """Überrundung: Summe der rohen Quotenwahrscheinlichkeiten minus 1."""
    return sum(1.0 / price for price in odds) - 1.0


def kelly_fraction(probability: float, decimal_odds: float) -> float:
    """Voller Kelly-Anteil des Budgets. Negativ wird zu 0."""
    net_odds = decimal_odds - 1.0
    if net_odds <= 0 or probability <= 0:
        return 0.0
    fraction = (probability * net_odds - (1.0 - probability)) / net_odds
    return max(0.0, fraction)


def shin_probabilities(odds: list[float]) -> dict[str, float]:
    """Shin-Methode: faire Wahrscheinlichkeiten nach Abzug der Marge.

    z ist der Anteil informierter Einsätze. Er wird so gewählt, dass die
    fairen Wahrscheinlichkeiten zusammen 100 % ergeben.
    """
    implied = [1.0 / price for price in odds]
    total = sum(implied)
    if total <= 1.0000001:
        fair = [value / total for value in implied]
        return dict(zip(_OUTCOMES, fair, strict=True))

    def at(insider: float) -> list[float]:
        insider = min(0.999, max(1e-8, insider))
        values = []
        for price in implied:
            root = math.sqrt(insider**2 + 4 * (1 - insider) * price**2 / total)
            values.append((root - insider) / (2 * (1 - insider)))
        return values

    low, high = 1e-8, 0.999
    for _ in range(60):
        mid = (low + high) / 2
        if sum(at(mid)) > 1:
            low = mid
        else:
            high = mid
    solved = at((low + high) / 2)
    scale = sum(solved) or 1.0
    return dict(zip(_OUTCOMES, [value / scale for value in solved], strict=True))


def power_probabilities(odds: list[float]) -> dict[str, float]:
    """Power-Methode: Exponent so wählen, dass die Quotenwahrscheinlichkeiten 100 % ergeben."""
    implied = [1.0 / price for price in odds]
    total = sum(implied)
    if abs(total - 1.0) <= 1e-9:
        return dict(zip(_OUTCOMES, implied, strict=True))

    def total_at(exponent: float) -> float:
        return sum(price**exponent for price in implied)

    low, high = 0.05, 8.0
    for _ in range(60):
        mid = (low + high) / 2
        if total_at(mid) > 1:
            low = mid
        else:
            high = mid
    exponent = (low + high) / 2
    solved = [price**exponent for price in implied]
    scale = sum(solved) or 1.0
    return dict(zip(_OUTCOMES, [value / scale for value in solved], strict=True))


def score_matrix(home_xg: float, away_xg: float, size: int = MATRIX_SIZE) -> tuple[list[list[float]], float]:
    """Wahrscheinlichkeit je Spielstand von 0:0 bis 5:5, plus die Summe dieser Felder."""
    rows: list[list[float]] = []
    mass = 0.0
    for home_goals in range(size):
        row = []
        home_p = poisson_pmf(home_goals, home_xg)
        for away_goals in range(size):
            probability = home_p * poisson_pmf(away_goals, away_xg)
            row.append(probability)
            mass += probability
        rows.append(row)
    return rows, mass


def build_pro_view(item: Assessment) -> ProView:
    odds = [item.odds[key] for key in _OUTCOMES]
    shin = shin_probabilities(odds)
    power = power_probabilities(odds)
    edge_raw = {key: item.model_probs[key] - (1.0 / item.odds[key]) for key in _OUTCOMES}
    edge_shin = {key: item.model_probs[key] - shin[key] for key in _OUTCOMES}
    kelly = {key: kelly_fraction(item.model_probs[key], item.odds[key]) for key in _OUTCOMES}
    if item.home_xg is None or item.away_xg is None:
        matrix, mass = [], 0.0
    else:
        matrix, mass = score_matrix(item.home_xg, item.away_xg)
    return ProView(
        margin=bookmaker_margin(odds),
        shin=shin,
        power=power,
        kelly=kelly,
        edge_raw=edge_raw,
        edge_shin=edge_shin,
        matrix=matrix,
        matrix_mass=mass,
    )
