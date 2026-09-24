from datetime import datetime, timezone

from valuepulse.models import Assessment, BookLine, MatchView
from valuepulse.slip import build_slip, shortened_warning


NOW = datetime(2026, 9, 23, 15, 0, tzinfo=timezone.utc)


def _match(
    home: str,
    away: str,
    *,
    pick: str = "home",
    probability: float = 0.60,
    odds: float = 2.0,
    edge: float = 0.08,
    quality: int = 80,
    signal: str = "green",
    competition: str = "Premier League",
) -> MatchView:
    labels = {"home": "Heimsieg", "draw": "Unentschieden", "away": "Auswärtssieg"}
    probs = {"home": 0.2, "draw": 0.2, "away": 0.2}
    prices = {"home": 4.0, "draw": 4.0, "away": 4.0}
    probs[pick] = probability
    prices[pick] = odds
    assessment = Assessment(
        pick=pick,
        pick_label=labels[pick],
        edge=edge,
        model_probs=probs,
        odds=prices,
        implied={key: 1.0 / value for key, value in prices.items()},
        bookmaker="Buch",
        quality=quality,
        quality_notes=[],
        signal=signal,
        headline="Tipp",
        explanation="",
    )
    return MatchView(
        competition=competition,
        kickoff=NOW,
        kickoff_label="23.09. 17:00",
        home=home,
        away=away,
        assessment=assessment,
    )


def test_fuenf_angefordert_drei_vorhanden_kuerzt_den_schein():
    matches = [
        _match("Arsenal", "Chelsea", edge=0.09, probability=0.58),
        _match("Liverpool", "Everton", edge=0.07, probability=0.56),
        _match("Bayern", "Köln", edge=0.06, probability=0.57, competition="Bundesliga"),
        _match("Roma", "Lecce", edge=0.02, probability=0.70, signal="red"),
    ]
    slip = build_slip(matches, count=5, risk="hoch")
    assert slip.shortened
    assert len(slip.legs) == 3
    assert slip.requested == 5
    assert slip.warning == shortened_warning(3, 5)
    assert "Spielschein gekürzt!" in slip.warning
    assert "Es wurden nur 3 qualifizierte Spiele mit ausreichendem Value gefunden (angefordert: 5)." in slip.warning
    assert "Roma" not in slip.copy_text


def test_wenig_risiko_nimmt_nur_hohe_chance_und_solide_qualitaet():
    matches = [
        _match("A", "B", probability=0.70, quality=80, edge=0.04, odds=1.50),
        _match("C", "D", probability=0.54, quality=90, edge=0.12, odds=2.40),
        _match("E", "F", probability=0.66, quality=45, edge=0.08, odds=1.70),
        _match("G", "H", probability=0.62, quality=70, edge=0.05, odds=1.80),
    ]
    slip = build_slip(matches, count=3, risk="wenig")
    names = [(leg.home, leg.away) for leg in slip.legs]
    assert names == [("A", "B"), ("G", "H")]
    assert slip.shortened
    assert "angefordert: 3" in slip.warning


def test_mittel_sortiert_nach_edge_mal_trefferchance():
    matches = [
        _match("A", "B", edge=0.04, probability=0.60),
        _match("C", "D", edge=0.10, probability=0.40),
        _match("E", "F", edge=0.05, probability=0.50),
    ]
    slip = build_slip(matches, count=3, risk="mittel")
    assert [(leg.home, leg.away) for leg in slip.legs] == [("C", "D"), ("E", "F"), ("A", "B")]
    assert slip.shortened is False
    assert slip.warning == ""


def test_hoch_sortiert_nach_absolutem_edge():
    matches = [
        _match("A", "B", edge=0.04, probability=0.70, odds=1.40),
        _match("C", "D", edge=0.15, probability=0.28, odds=5.50),
        _match("E", "F", edge=0.09, probability=0.40, odds=3.20),
    ]
    slip = build_slip(matches, count=2, risk="hoch")
    assert [(leg.home, leg.away) for leg in slip.legs] == [("C", "D"), ("E", "F")]


def test_dieselbe_mannschaft_kommt_nur_einmal_vor():
    matches = [
        _match("Arsenal", "Chelsea", edge=0.12),
        _match("Arsenal", "Spurs", edge=0.10),
        _match("Liverpool", "Everton", edge=0.08),
    ]
    slip = build_slip(matches, count=3, risk="hoch")
    assert [(leg.home, leg.away) for leg in slip.legs] == [("Arsenal", "Chelsea"), ("Liverpool", "Everton")]
    assert slip.shortened
    assert "nur 2 qualifizierte Spiele" in slip.warning


def test_gesamtquote_und_einsatz_sind_produkt_und_gedeckelter_viertel_kelly():
    matches = [
        _match("A", "B", probability=0.70, odds=1.50, edge=0.04, quality=90),
        _match("C", "D", probability=0.60, odds=2.00, edge=0.10, quality=90),
    ]
    slip = build_slip(matches, count=2, risk="wenig")
    assert abs(slip.combined_odds - 3.0) < 1e-9
    assert abs(slip.combined_probability - 0.42) < 1e-9
    assert slip.stake == slip.stake_cap == 0.01
    assert slip.stake_capped
    assert "Gesamtquote: 3,00" in slip.copy_text
    assert "Gesamt-Wahrscheinlichkeit: 42,0 %" in slip.copy_text
    assert "1,0 % der Bankroll" in slip.copy_text


def test_kombi_nimmt_die_beste_quote_eines_buchmachers():
    first = _match("A", "B", odds=2.40, probability=0.55, edge=0.10)
    second = _match("C", "D", odds=3.20, probability=0.40, edge=0.08)
    first.books = (
        BookLine("Bet365", 1.80, 3.40, 4.20),
        BookLine("Pinnacle", 2.00, 3.30, 4.00),
    )
    second.books = (
        BookLine("Bet365", 1.90, 3.40, 4.00),
        BookLine("Pinnacle", 1.70, 3.50, 4.40),
        BookLine("Unibet", 3.20, 3.10, 2.40),
    )
    slip = build_slip([first, second], count=2, risk="hoch")
    assert slip.bookmaker == "Bet365"
    assert [leg.odds for leg in slip.legs] == [1.80, 1.90]
    assert abs(slip.combined_odds - 3.42) < 1e-9
    assert "Buchmacher: Bet365" in slip.copy_text
    assert slip.shortened is False


def test_ohne_gemeinsamen_buchmacher_wird_der_schein_gekuerzt():
    first = _match("A", "B", edge=0.12, odds=2.2)
    second = _match("C", "D", edge=0.08, odds=2.4)
    first.books = (BookLine("Unibet", 2.2, 3.2, 3.4),)
    second.books = (BookLine("Bet365", 2.4, 3.3, 3.1),)
    slip = build_slip([first, second], count=2, risk="hoch")
    assert [(leg.home, leg.odds) for leg in slip.legs] == [("A", 2.2)]
    assert slip.bookmaker == "Unibet"
    assert slip.shortened
    assert "derselbe Buchmacher" in slip.warning


def test_anzahl_wird_auf_zwei_bis_zehn_begrenzt():
    matches = [_match(f"H{index}", f"A{index}", edge=0.05 + index / 100) for index in range(12)]
    assert len(build_slip(matches, count=1, risk="hoch").legs) == 2
    assert len(build_slip(matches, count=99, risk="hoch").legs) == 10
    assert build_slip(matches, count=99, risk="hoch").requested == 10
