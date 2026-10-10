"""Gespeicherte Tipps und ihre Bilanz.

Eine Position startet offen. Nach dem Spiel wird sie gewonnen, verloren
oder storniert. Daraus entstehen Gewinn, Gewinnrate und ROI.
"""

from __future__ import annotations

import sqlite3
import math
import json
from dataclasses import dataclass
from datetime import datetime, timezone

STATUSES = ("open", "won", "lost", "void")
STATUS_LABELS = {
    "open": "Offen",
    "won": "Gewonnen",
    "lost": "Verloren",
    "void": "Storniert",
}


@dataclass(frozen=True)
class Position:
    id: int
    created_at: str
    sport: str
    competition: str
    match_label: str
    kickoff: str
    pick_label: str
    odds: float
    probability: float
    stake: float
    status: str
    pnl: float | None
    mode: str = "legacy"
    bookmaker: str = ""
    source: str = "legacy"
    model_version: str = ""
    event_key: str = ""
    legs_json: str = "[]"


@dataclass(frozen=True)
class Performance:
    pnl: float
    wins: int
    losses: int
    voids: int
    open_count: int
    settled_stake: float
    win_rate: float | None
    roi: float | None
    open_stake: float = 0.0


def ensure_positions(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            sport TEXT NOT NULL,
            competition TEXT NOT NULL,
            match_label TEXT NOT NULL,
            kickoff TEXT NOT NULL,
            pick_label TEXT NOT NULL,
            odds REAL NOT NULL,
            probability REAL NOT NULL,
            stake REAL NOT NULL,
            status TEXT NOT NULL,
            pnl REAL
        )
        """
    )
    # Old rows have unknown provenance: never silently label them as real bets.
    conn.execute("BEGIN IMMEDIATE")
    try:
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(positions)")}
        for name, default in (("mode","legacy"),("bookmaker",""),("source","legacy"),
                              ("model_version",""),("event_key",""),("legs_json","[]")):
            if name not in existing:
                conn.execute(f"ALTER TABLE positions ADD COLUMN {name} TEXT NOT NULL DEFAULT '{default}'")
        conn.execute("""CREATE TABLE IF NOT EXISTS position_changes (
            id INTEGER PRIMARY KEY, position_id INTEGER NOT NULL, changed_at TEXT NOT NULL,
            previous_status TEXT NOT NULL, status TEXT NOT NULL, pnl REAL NOT NULL)""")
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def add_position(
    conn: sqlite3.Connection,
    *,
    sport: str,
    competition: str,
    match_label: str,
    kickoff: str,
    pick_label: str,
    odds: float,
    probability: float,
    stake: float,
    created_at: datetime | None = None,
    mode: str = "paper",
    bookmaker: str = "",
    source: str = "manual",
    model_version: str = "",
    event_key: str = "",
    legs: list[dict] | None = None,
) -> int:
    if mode not in {"paper", "real"}:
        raise ValueError("Neue Positionen gehören zu Paper-Trading oder Echtpositionen.")
    if source == "demo":
        raise ValueError("Demo-Beispiele werden nicht im Positionsbuch gespeichert.")
    if not math.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("Ungültige Wahrscheinlichkeit.")
    if not math.isfinite(stake) or stake <= 0:
        raise ValueError("Der Einsatz muss größer als 0 sein.")
    if not math.isfinite(odds) or odds <= 1:
        raise ValueError("Die Quote muss über 1 liegen.")
    ensure_positions(conn)
    moment = created_at or datetime.now(timezone.utc)
    cursor = conn.execute(
        """
        INSERT INTO positions (
            created_at, sport, competition, match_label, kickoff,
            pick_label, odds, probability, stake, status, pnl,
            mode, bookmaker, source, model_version, event_key, legs_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', NULL, ?, ?, ?, ?, ?, ?)
        """,
        (
            moment.replace(microsecond=0).isoformat(),
            sport,
            competition,
            match_label,
            kickoff,
            pick_label,
            float(odds),
            float(probability),
            float(stake),
            mode, bookmaker, source, model_version, event_key, json.dumps(legs or []),
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def settle(conn: sqlite3.Connection, position_id: int, status: str) -> None:
    if status not in {"won", "lost", "void"}:
        raise ValueError(f"Unbekanntes Ergebnis: {status}")
    ensure_positions(conn)
    row = conn.execute("SELECT stake, odds, status FROM positions WHERE id = ?", (position_id,)).fetchone()
    if row is None:
        raise ValueError("Diese Position gibt es nicht.")
    pnl = _result_pnl(status, float(row["stake"]), float(row["odds"]))
    with conn:
        conn.execute("INSERT INTO position_changes(position_id,changed_at,previous_status,status,pnl) VALUES(?,?,?,?,?)",
            (position_id,datetime.now(timezone.utc).isoformat(),row['status'],status,pnl))
        conn.execute("UPDATE positions SET status = ?, pnl = ? WHERE id = ?", (status, pnl, position_id))


def list_positions(conn: sqlite3.Connection, mode: str | None = None) -> list[Position]:
    ensure_positions(conn)
    if mode is None:
        rows = conn.execute("SELECT * FROM positions ORDER BY created_at DESC, id DESC").fetchall()
    else:
        rows = conn.execute("SELECT * FROM positions WHERE mode=? ORDER BY created_at DESC, id DESC", (mode,)).fetchall()
    return [_position(row) for row in rows]


def summarize(positions: list[Position]) -> Performance:
    wins = losses = voids = open_count = 0
    pnl = 0.0
    settled_stake = 0.0
    for position in positions:
        if position.status == "open":
            open_count += 1
            continue
        if position.status == "won":
            wins += 1
        elif position.status == "lost":
            losses += 1
        elif position.status == "void":
            voids += 1
        pnl += position.pnl or 0.0
        if position.status in {"won", "lost"}:
            settled_stake += position.stake
    decided = wins + losses
    win_rate = (wins / decided) if decided else None
    roi = (pnl / settled_stake) if settled_stake else None
    return Performance(
        pnl=pnl,
        wins=wins,
        losses=losses,
        voids=voids,
        open_count=open_count,
        settled_stake=settled_stake,
        win_rate=win_rate,
        roi=roi,
        open_stake=sum(row.stake for row in positions if row.status == "open"),
    )


def _result_pnl(status: str, stake: float, odds: float) -> float:
    if status == "won":
        return stake * (odds - 1.0)
    if status == "lost":
        return -stake
    return 0.0


def _position(row: sqlite3.Row) -> Position:
    return Position(
        id=int(row["id"]),
        created_at=row["created_at"],
        sport=row["sport"],
        competition=row["competition"],
        match_label=row["match_label"],
        kickoff=row["kickoff"],
        pick_label=row["pick_label"],
        odds=float(row["odds"]),
        probability=float(row["probability"]),
        stake=float(row["stake"]),
        status=row["status"],
        pnl=None if row["pnl"] is None else float(row["pnl"]),
        mode=row["mode"], bookmaker=row["bookmaker"], source=row["source"],
        model_version=row["model_version"], event_key=row["event_key"], legs_json=row["legs_json"],
    )


def exposure_by_team(positions: list[Position]) -> list[dict]:
    """One full position stake is at risk for each team involved (not additive across teams)."""
    from valuepulse.names import canonical
    grouped = {}
    for position in positions:
        if position.status != "open":
            continue
        seen = set()
        for leg in json.loads(position.legs_json):
            for team in (leg.get('home',''),leg.get('away','')):
                key=canonical(team)
                if not key or key in seen:
                    continue
                seen.add(key)
                entry=grouped.setdefault(key, {'Team':team,'Offene Positionen':0,'Einsatz':0.0})
                entry['Offene Positionen']+=1
                entry['Einsatz']+=position.stake
    return sorted(grouped.values(),key=lambda item:item['Einsatz'],reverse=True)
