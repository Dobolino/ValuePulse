from datetime import date, datetime, timezone

from valuepulse.models import Assessment, MatchView
from valuepulse.monthcal import apply_day_click, month_weeks, shift_month, value_counts
from valuepulse.sports import SPORTS, provider_plan


def test_kein_esport_und_fussball_ist_die_einzige_live_sportart():
    ids = [sport.id for sport in SPORTS]
    names = " ".join(sport.name.casefold() for sport in SPORTS)
    assert "esports" not in ids
    assert "valorant" not in names
    assert "cs2" not in names
    assert ids[0] == "football"
    for required in ("tennis", "basketball", "baseball", "ufc", "american_football", "darts"):
        assert required in ids
    assert provider_plan("football") == "football-data+the-odds-api"
    assert provider_plan("tennis").startswith("nicht-angeschlossen")
    assert sum(1 for sport in SPORTS if sport.live) == 1


def test_monatsraster_startet_am_montag():
    weeks = month_weeks(2026, 9)
    assert weeks[0][0] is None or weeks[0][0].weekday() == 0
    days = [day for week in weeks for day in week if day is not None]
    assert days[0] == date(2026, 9, 1)
    assert days[-1] == date(2026, 9, 30)
    assert shift_month(2026, 12, 1) == (2027, 1)


def test_tagesklick_setzt_nur_den_zeitraum():
    start, end, phase = apply_day_click(None, "start", date(2026, 9, 24))
    assert (start, end, phase) == (date(2026, 9, 24), date(2026, 9, 24), "end")
    start, end, phase = apply_day_click(start, phase, date(2026, 9, 27))
    assert (start, end, phase) == (date(2026, 9, 24), date(2026, 9, 27), "start")
    start, end, phase = apply_day_click(start, "end", date(2026, 9, 20))
    assert start == date(2026, 9, 20)
    assert end == date(2026, 9, 24)


def test_kalender_zaehlt_nur_value_signale_im_monat():
    green = _view("A", "B", "green", datetime(2026, 9, 26, 14, tzinfo=timezone.utc))
    yellow = _view("C", "D", "yellow", datetime(2026, 9, 26, 18, tzinfo=timezone.utc))
    red = _view("E", "F", "red", datetime(2026, 9, 26, 20, tzinfo=timezone.utc))
    later = _view("G", "H", "green", datetime(2026, 10, 2, 14, tzinfo=timezone.utc))
    counts = value_counts([green, yellow, red, later], 2026, 9)
    assert counts == {date(2026, 9, 26): 2}


def _view(home: str, away: str, signal: str, kickoff: datetime) -> MatchView:
    assessment = Assessment(
        pick="home",
        pick_label="Heimsieg",
        edge=0.05,
        model_probs={"home": 0.6, "draw": 0.2, "away": 0.2},
        odds={"home": 2.0, "draw": 3.4, "away": 4.0},
        implied={"home": 0.5, "draw": 0.29, "away": 0.25},
        bookmaker="Buch",
        quality=80,
        quality_notes=[],
        signal=signal,
        headline="Tipp",
        explanation="",
    )
    return MatchView(competition="Liga", kickoff=kickoff, kickoff_label="", home=home, away=away, assessment=assessment)
