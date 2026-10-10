from datetime import date, datetime, timezone

from valuepulse.models import Assessment, MatchView
from valuepulse.monthcal import (
    apply_day_click,
    day_help,
    in_selected_range,
    month_weeks,
    range_marks,
    range_role,
    selected_range_css,
    shift_month,
    value_counts,
)
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


def test_zeitraum_markiert_inklusive_raender():
    start, end = date(2026, 10, 10), date(2026, 10, 17)
    assert in_selected_range(start, start, end)
    assert in_selected_range(end, start, end)
    assert in_selected_range(date(2026, 10, 12), start, end)
    assert not in_selected_range(date(2026, 10, 9), start, end)
    assert not in_selected_range(date(2026, 10, 18), start, end)
    assert in_selected_range(date(2026, 10, 12), end, start)


def test_anfang_mitte_und_ende_sind_unterschiedlich():
    start, end = date(2026, 10, 10), date(2026, 10, 17)
    assert range_role(start, start, end) == "start"
    assert range_role(date(2026, 10, 11), start, end) == "mid"
    assert range_role(date(2026, 10, 16), start, end) == "mid"
    assert range_role(end, start, end) == "end"
    assert range_role(date(2026, 10, 9), start, end) == "outside"
    assert range_role(date(2026, 10, 12), end, start) == "mid"
    assert range_role(start, start, start) == "single"

    marks = range_marks(2026, 10, start, end)
    assert marks[start] == "start"
    assert marks[date(2026, 10, 13)] == "mid"
    assert marks[end] == "end"
    assert date(2026, 10, 9) not in marks
    assert date(2026, 10, 18) not in marks

    october = range_marks(2026, 10, date(2026, 10, 28), date(2026, 11, 3))
    november = range_marks(2026, 11, date(2026, 10, 28), date(2026, 11, 3))
    assert october[date(2026, 10, 28)] == "start"
    assert october[date(2026, 10, 31)] == "mid"
    assert date(2026, 11, 3) not in october
    assert november[date(2026, 11, 1)] == "mid"
    assert november[date(2026, 11, 3)] == "end"
    assert date(2026, 10, 28) not in november

    css = selected_range_css(2026, 10, start, end)
    assert "/*role:start*/" in css
    assert "/*role:mid*/" in css
    assert "/*role:end*/" in css
    assert ".st-key-day-2026-10-10" in css
    assert ".st-key-day-2026-10-12" in css
    assert ".st-key-day-2026-10-17" in css
    assert ".st-key-day-2026-10-09" not in css
    assert "border-radius:12px 4px 4px 12px" in css
    assert "border-radius:4px 12px 12px 4px" in css
    assert selected_range_css(2026, 11, start, end) == ""
    assert "/*role:single*/" in selected_range_css(2026, 10, start, start)
    assert day_help("start", 0) == "Start des gewählten Zeitraums"
    assert day_help("mid", 1) == "1 Value-Signal · Liegt im gewählten Zeitraum"
    assert day_help("end", 3).startswith("3 Value-Signale")


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
