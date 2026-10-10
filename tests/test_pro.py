from valuepulse.model import assess, strength_from_table
from valuepulse.pro import (
    bookmaker_margin,
    build_pro_view,
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
    assert view.kelly["home"] > 0
    assert abs(view.recommended_stake["home"] - min(.01, view.kelly["home"] * 0.25)) < 1e-9
    assert abs(sum(view.shin.values()) - 1) < 1e-6
    assert view.matrix


def test_power_two_way_and_invalid_prices():
    import pytest
    assert power_probabilities([1.91,1.91]) == pytest.approx({'over':.5,'under':.5})
    assert power_probabilities([2.,2.],('yes','no')) == {'yes':.5,'no':.5}
    for odds in ([float('nan'),2.],[float('inf'),2.],[1.,2.]):
        with pytest.raises(ValueError): power_probabilities(odds)


def test_margin_uses_one_actual_bookmaker():
    from tests.test_slip import _match
    match=_match()
    # Synthetic best prices are deliberately different from the actual market.
    match.assessment.odds={'home':2.5,'draw':5.,'away':5.}
    view=build_pro_view(match.assessment)
    prices=match.assessment.book_odds['Book']
    assert abs(view.margin-(sum(1/v for v in prices.values())-1)) < 1e-12
