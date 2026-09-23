"""SQLite-Speicher für jede abgerufene Quote.

Die Datei ist ein Zwischenspeicher. Ist sie beschädigt oder stammt sie aus
einer anderen Programmversion, legt ValuePulse sie beiseite und beginnt neu.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from valuepulse.models import Quote, Standing

SCHEMA_VERSION = "1"
SNAPSHOT_KEEP_DAYS = 90

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS odds_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fetched_at TEXT NOT NULL,
    source TEXT NOT NULL,
    competition TEXT NOT NULL,
    kickoff TEXT NOT NULL,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    bookmaker TEXT NOT NULL,
    home_odds REAL NOT NULL,
    draw_odds REAL NOT NULL,
    away_odds REAL NOT NULL,
    last_update TEXT
);

CREATE TABLE IF NOT EXISTS standings (
    competition TEXT NOT NULL,
    team TEXT NOT NULL,
    played INTEGER NOT NULL,
    points INTEGER NOT NULL,
    goals_for INTEGER NOT NULL,
    goals_against INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (competition, team)
);

CREATE INDEX IF NOT EXISTS idx_odds_lookup
    ON odds_snapshots (home_team, away_team, kickoff);
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _backup(path: Path) -> None:
    if not path.exists():
        return
    bak = path.with_suffix(path.suffix + ".bak")
    if bak.exists():
        bak.unlink()
    path.replace(bak)


def connect(path: Path) -> sqlite3.Connection:
    """Öffnet die Datenbank und heilt Schema oder Dateischäden."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        _ensure_schema(conn)
        delete_old_snapshots(conn)
        return conn
    except sqlite3.DatabaseError:
        try:
            conn.close()
        except Exception:
            pass
        _backup(path)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        _ensure_schema(conn)
        delete_old_snapshots(conn)
        return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    version = None
    try:
        row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        version = row["value"] if row else None
    except sqlite3.DatabaseError:
        version = None
    if version not in (None, SCHEMA_VERSION):
        raise sqlite3.DatabaseError(f"schema {version}")
    conn.executescript(_SCHEMA)
    conn.execute(
        "INSERT INTO meta (key, value) VALUES ('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (SCHEMA_VERSION,),
    )
    conn.commit()


def save_quotes(conn: sqlite3.Connection, quotes: list[Quote], fetched_at: datetime) -> None:
    stamp = fetched_at.replace(microsecond=0).isoformat()
    conn.executemany(
        """
        INSERT INTO odds_snapshots (
            fetched_at, source, competition, kickoff, home_team, away_team,
            bookmaker, home_odds, draw_odds, away_odds, last_update
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                stamp,
                quote.source,
                quote.competition,
                quote.kickoff.replace(microsecond=0).isoformat(),
                quote.home,
                quote.away,
                quote.bookmaker,
                quote.home_odds,
                quote.draw_odds,
                quote.away_odds,
                quote.last_update.replace(microsecond=0).isoformat() if quote.last_update else None,
            )
            for quote in quotes
        ],
    )
    conn.commit()


def latest_quotes(conn: sqlite3.Connection) -> list[Quote]:
    """Jüngste Quote je Spiel und Buchmacher, ohne Demo-Zeilen."""
    rows = conn.execute(
        """
        SELECT o.*
        FROM odds_snapshots o
        JOIN (
            SELECT home_team, away_team, kickoff, bookmaker, MAX(fetched_at) AS fetched_at
            FROM odds_snapshots
            WHERE source != 'demo'
            GROUP BY home_team, away_team, kickoff, bookmaker
        ) latest
          ON o.home_team = latest.home_team
         AND o.away_team = latest.away_team
         AND o.kickoff = latest.kickoff
         AND o.bookmaker = latest.bookmaker
         AND o.fetched_at = latest.fetched_at
        WHERE o.source != 'demo'
        """
    ).fetchall()
    quotes: list[Quote] = []
    for row in rows:
        last = row["last_update"]
        quotes.append(
            Quote(
                competition=row["competition"],
                kickoff=_parse_dt(row["kickoff"]),
                home=row["home_team"],
                away=row["away_team"],
                bookmaker=row["bookmaker"],
                home_odds=row["home_odds"],
                draw_odds=row["draw_odds"],
                away_odds=row["away_odds"],
                last_update=_parse_dt(last) if last else None,
                source="cache",
            )
        )
    return quotes


def save_standings(conn: sqlite3.Connection, rows: list[Standing], updated_at: datetime) -> None:
    stamp = updated_at.replace(microsecond=0).isoformat()
    codes = sorted({row.competition_code for row in rows})
    for code in codes:
        conn.execute("DELETE FROM standings WHERE competition = ?", (code,))
    conn.executemany(
        """
        INSERT INTO standings (
            competition, team, played, points, goals_for, goals_against, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row.competition_code,
                row.team,
                row.played,
                row.points,
                row.goals_for,
                row.goals_against,
                stamp,
            )
            for row in rows
        ],
    )
    conn.commit()


def load_standings(conn: sqlite3.Connection) -> list[Standing]:
    rows = conn.execute("SELECT * FROM standings").fetchall()
    return [
        Standing(
            competition_code=row["competition"],
            team=row["team"],
            played=row["played"],
            points=row["points"],
            goals_for=row["goals_for"],
            goals_against=row["goals_against"],
        )
        for row in rows
    ]


def delete_old_snapshots(conn: sqlite3.Connection, *, now: datetime | None = None, keep_days: int = SNAPSHOT_KEEP_DAYS) -> int:
    """Löscht gespeicherte Quoten, die älter als 90 Tage sind."""
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    cutoff = (moment - timedelta(days=keep_days)).replace(microsecond=0).isoformat()
    cursor = conn.execute("DELETE FROM odds_snapshots WHERE fetched_at < ?", (cutoff,))
    conn.commit()
    return cursor.rowcount


def _parse_dt(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
