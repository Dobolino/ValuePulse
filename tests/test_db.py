import sqlite3
import pytest
from datetime import datetime, timedelta, timezone

from valuepulse.db import LOCK_WAIT_SECONDS, connect, delete_old_snapshots, latest_quotes, save_quotes
from valuepulse.models import Quote
from valuepulse.positions import add_position, list_positions


def _quote() -> Quote:
    moment = datetime(2026, 9, 23, 10, 0, tzinfo=timezone.utc)
    return Quote(
        competition="Bundesliga",
        kickoff=moment,
        home="FC Bayern München",
        away="Borussia Dortmund",
        bookmaker="Beispiel",
        home_odds=1.55,
        draw_odds=4.2,
        away_odds=5.6,
        last_update=moment,
        source="the-odds-api",
    )


def test_quote_wird_gespeichert_und_gelesen(tmp_path):
    path = tmp_path / "valuepulse.sqlite3"
    conn = connect(path)
    save_quotes(conn, [_quote()], datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc))
    conn.close()

    again = connect(path)
    rows = latest_quotes(again)
    again.close()
    assert len(rows) == 1
    assert rows[0].home == "FC Bayern München"
    assert rows[0].home_odds == 1.55
    assert rows[0].source == "cache"


def test_beschaedigte_datei_wird_neu_angelegt(tmp_path):
    path = tmp_path / "valuepulse.sqlite3"
    path.write_bytes(b"das ist keine datenbank")
    conn = connect(path)
    save_quotes(conn, [_quote()], datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc))
    assert latest_quotes(conn)
    conn.close()
    assert path.with_suffix(".sqlite3.bak").exists() or path.with_suffix(path.suffix + ".bak").exists()


def test_fremdes_schema_wird_ersetzt(tmp_path):
    path = tmp_path / "valuepulse.sqlite3"
    conn = connect(path)
    conn.execute("UPDATE meta SET value = '0' WHERE key = 'schema_version'")
    conn.commit()
    conn.close()

    healed = connect(path)
    version = healed.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()["value"]
    healed.close()
    assert version == "1"


def test_datenbank_sperre_loescht_die_datei_nicht(tmp_path, monkeypatch):
    path = tmp_path / "valuepulse.sqlite3"
    holder = connect(path)
    add_position(
        holder,
        sport="football",
        competition="Premier League",
        match_label="Arsenal – Chelsea",
        kickoff="2026-09-26T14:00:00+00:00",
        pick_label="Heimsieg",
        odds=2.0,
        probability=0.55,
        stake=1.0,
    )
    holder.execute("BEGIN EXCLUSIVE")
    sleeps = []
    monkeypatch.setattr("valuepulse.db.time.sleep", lambda seconds: sleeps.append(seconds))
    try:
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            connect(path, timeout=0)
    finally:
        holder.rollback()
    assert sleeps == [LOCK_WAIT_SECONDS, LOCK_WAIT_SECONDS]
    assert not list(tmp_path.glob("*.bak"))
    again = connect(path)
    assert len(list_positions(again)) == 1
    again.close()
    holder.close()


def test_snapshots_aelter_als_90_tage_werden_geloescht(tmp_path):
    path = tmp_path / "valuepulse.sqlite3"
    conn = connect(path)
    moment = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    old = _quote()
    fresh = Quote(
        competition="Bundesliga",
        kickoff=moment,
        home="FC Bayern München",
        away="Borussia Dortmund",
        bookmaker="Neu",
        home_odds=1.6,
        draw_odds=4.0,
        away_odds=5.4,
        last_update=moment,
        source="the-odds-api",
    )
    save_quotes(conn, [old], moment - timedelta(days=100))
    save_quotes(conn, [fresh], moment)
    removed = delete_old_snapshots(conn, now=moment)
    conn.close()
    assert removed == 1
    again = connect(path)
    rows = latest_quotes(again)
    again.close()
    assert [row.bookmaker for row in rows] == ["Neu"]
