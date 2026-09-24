from valuepulse.model import assess, strength_from_table
from valuepulse.pro import (
    bookmaker_margin,
    build_pro_view,
    expected_value,
    fractional_kelly,
    kelly_fraction,
    power_probabilities,
    score_matrix,
    shin_probabilities,
)
from tests.test_model import NOW, _quotes, _table


def test_shin_und_power_liegen_bei_100_prozent():
    odds = [1.91, 3.40, 4.20]
    shin = shin_probabilities(odds)
    power = power_probabilities(odds)
    assert abs(sum(shin.values()) - 1) < 1e-6
    assert abs(sum(power.values()) - 1) < 1e-6
    assert bookmaker_margin(odds) > 0.04
    assert shin["home"] > shin["away"]
    assert power["home"] > power["away"]


def test_edge_ist_der_erwartungswert():
    """Quote 2,90 und Modell 49 % ergeben (0,49 × 2,90) − 1 = +42,1 %."""
    assert abs(expected_value(0.49, 2.90) - 0.421) < 1e-12
    assert abs(expected_value(0.49, 2.90) - (0.49 - 1.0 / 2.90)) > 0.2


def test_kelly_ist_null_ohne_vorteil():
    assert abs(kelly_fraction(0.60, 2.0) - 0.20) < 1e-9
    assert kelly_fraction(0.40, 2.0) == 0.0
    assert abs(fractional_kelly(0.60, 2.0) - 0.05) < 1e-9


def test_matrix_hat_sechs_mal_sechs_felder():
    rows, mass = score_matrix(1.45, 1.15)
    assert len(rows) == 6
    assert all(len(row) == 6 for row in rows)
    assert 0.7 < mass < 1


def test_pro_sicht_enthaelt_kelly_und_shin():
    model = strength_from_table("Nordstern", "Westbrück", _table())
    result = assess(model=model, quotes=_quotes(model.probs, home_edge=0.08, age_hours=1), now=NOW)
    view = build_pro_view(result)
    home_prob = result.model_probs["home"]
    home_odds = result.odds["home"]
    assert view.kelly["home"] > 0
    assert abs(view.recommended_stake["home"] - view.kelly["home"] * 0.25) < 1e-9
    assert abs(sum(view.shin.values()) - 1) < 1e-6
    assert abs(view.edge_raw["home"] - (home_prob * home_odds - 1)) < 1e-9
    assert abs(view.edge_shin["home"] - (home_prob / view.shin["home"] - 1)) < 1e-9
    assert view.matrix
