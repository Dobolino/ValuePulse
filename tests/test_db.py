from datetime import datetime, timezone

from valuepulse.db import connect, latest_quotes, save_quotes
from valuepulse.models import Quote


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
