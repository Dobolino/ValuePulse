"""Persistenter SQLite-Speicher. Fehler ersetzen oder löschen niemals Datenbanken."""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from valuepulse.models import Quote, Standing

SCHEMA_VERSION = "2"
SNAPSHOT_KEEP_DAYS = 90
CONNECT_TIMEOUT_SECONDS = 10.0
LOCK_ATTEMPTS = 3
LOCK_WAIT_SECONDS = 0.5

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


def connect(path: Path, *, timeout: float = CONNECT_TIMEOUT_SECONDS) -> sqlite3.Connection:
    """Öffnet und migriert additive Schemata. Sperren werden begrenzt wiederholt."""
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, LOCK_ATTEMPTS + 1):
        try:
            return _open(path, timeout)
        except sqlite3.OperationalError as exc:
            if not _is_locked(exc):
                raise
            if attempt == LOCK_ATTEMPTS:
                raise
            time.sleep(LOCK_WAIT_SECONDS)
    raise sqlite3.OperationalError("database is locked")


def _open(path: Path, timeout: float) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=timeout)
    conn.row_factory = sqlite3.Row
    try:
        _ensure_schema(conn)
        delete_old_snapshots(conn)
    except Exception:
        conn.close()
        raise
    return conn


def _is_locked(exc: sqlite3.OperationalError) -> bool:
    return (getattr(exc, "sqlite_errorcode", 0) & 255) in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED) or "locked" in str(exc).lower()


def _ensure_schema(conn: sqlite3.Connection) -> None:
    version = None
    try:
        row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        version = row["value"] if row else None
    except sqlite3.OperationalError as exc:
        if "no such table: meta" not in str(exc):
            raise
    if version not in (None, "1", SCHEMA_VERSION):
        raise sqlite3.DatabaseError(f"schema {version}")
    conn.executescript(_SCHEMA)
    # Serialize additive migration across simultaneous connections.
    conn.execute("BEGIN IMMEDIATE")
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(standings)")}
    for column in ("season", "season_end"):
        if column not in columns:
            conn.execute(f"ALTER TABLE standings ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
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
        SELECT o.* FROM odds_snapshots o
        WHERE o.source != 'demo' AND o.id = (
            SELECT newer.id FROM odds_snapshots newer
            WHERE newer.source != 'demo' AND newer.competition = o.competition
              AND newer.home_team = o.home_team AND newer.away_team = o.away_team
              AND newer.kickoff = o.kickoff AND newer.bookmaker = o.bookmaker
            ORDER BY newer.fetched_at DESC, newer.id DESC LIMIT 1
        )
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
            competition, team, played, points, goals_for, goals_against, updated_at, season, season_end
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                row.season,
                row.season_end,
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
            updated_at=_parse_dt(row["updated_at"]),
            season=row["season"],
            season_end=row["season_end"],
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
