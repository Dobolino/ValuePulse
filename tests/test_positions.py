from datetime import datetime, timezone

from valuepulse.db import connect
from valuepulse.positions import add_position, list_positions, settle, summarize


def test_position_bilanz_aus_gewonnen_verloren_offen(tmp_path):
    conn = connect(tmp_path / "valuepulse.sqlite3")
    moment = datetime(2026, 9, 24, 12, tzinfo=timezone.utc)
    won = add_position(
        conn,
        sport="football",
        competition="Premier League",
        match_label="Arsenal – Chelsea",
        kickoff="2026-09-26T14:00:00+00:00",
        pick_label="Heimsieg",
        odds=2.0,
        probability=0.55,
        stake=2.0,
        created_at=moment,
    )
    lost = add_position(
        conn,
        sport="football",
        competition="Bundesliga",
        match_label="Bayern – Köln",
        kickoff="2026-09-27T16:30:00+00:00",
        pick_label="Heimsieg",
        odds=1.5,
        probability=0.62,
        stake=4.0,
        created_at=moment,
    )
    add_position(
        conn,
        sport="tennis",
        competition="ATP",
        match_label="Faria – Altmane",
        kickoff="2026-09-25T07:30:00+00:00",
        pick_label="Faria",
        odds=1.8,
        probability=0.6,
        stake=1.0,
        created_at=moment,
    )
    settle(conn, won, "won")
    settle(conn, lost, "lost")
    rows = list_positions(conn)
    summary = summarize(rows)
    assert summary.pnl == 2.0 - 4.0
    assert summary.wins == 1
    assert summary.losses == 1
    assert summary.open_count == 1
    assert summary.win_rate == 0.5
    assert summary.roi == (2.0 - 4.0) / 6.0
    assert any(row.status == "open" and row.pnl is None for row in rows)


def test_storno_zahlt_null_und_zaehlt_nicht_zur_quote(tmp_path):
    conn = connect(tmp_path / "valuepulse.sqlite3")
    position_id = add_position(
        conn,
        sport="football",
        competition="Demo-Liga",
        match_label="Nordstern – Westbrück",
        kickoff="2026-09-25T13:30:00+00:00",
        pick_label="Heimsieg",
        odds=1.33,
        probability=0.85,
        stake=5.0,
    )
    settle(conn, position_id, "void")
    summary = summarize(list_positions(conn))
    assert summary.pnl == 0.0
    assert summary.voids == 1
    assert summary.win_rate is None
    assert summary.roi is None
    assert summary.settled_stake == 0.0
