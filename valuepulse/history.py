"""Immutable forecasts, explicit results, prospective replay and quote history.

Backtests use forecasts actually recorded before kickoff. No current league
standings are applied retroactively. One forecast per event and bookmaker is
selected to prevent repeated API polls from inflating the sample size.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from valuepulse.config import LEAGUES, MODEL_VERSION, EDGE_MIN, MAX_SIGNAL_EV, MAX_SINGLE_ODDS, MIN_SIGNAL_QUALITY
from valuepulse.model import expected_value, data_quality
from valuepulse.models import MatchView, Standing
from valuepulse.names import canonical, names_match

OUTCOMES = ("home", "draw", "away")


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def event_key(competition: str, home: str, away: str, kickoff: datetime) -> str:
    raw = [competition, canonical(home), canonical(away), utc(kickoff).isoformat()]
    return hashlib.sha256(json.dumps(raw).encode()).hexdigest()


def ensure_history(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY, event_key TEXT NOT NULL,
        competition TEXT NOT NULL, home TEXT NOT NULL, away TEXT NOT NULL,
        kickoff TEXT NOT NULL, recorded_at TEXT NOT NULL, quote_at TEXT NOT NULL,
        bookmaker TEXT NOT NULL, model_version TEXT NOT NULL, source TEXT NOT NULL,
        probabilities TEXT NOT NULL, odds TEXT NOT NULL, inputs TEXT NOT NULL,
        quality INTEGER NOT NULL, pick TEXT NOT NULL, eligible INTEGER NOT NULL,
        fingerprint TEXT UNIQUE NOT NULL
    );
    CREATE INDEX IF NOT EXISTS prediction_event ON predictions(event_key, bookmaker, recorded_at);
    CREATE TABLE IF NOT EXISTS results (
        event_key TEXT PRIMARY KEY, home_goals INTEGER NOT NULL, away_goals INTEGER NOT NULL,
        recorded_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS result_changes (
        id INTEGER PRIMARY KEY, event_key TEXT NOT NULL, changed_at TEXT NOT NULL,
        previous_home INTEGER, previous_away INTEGER, home_goals INTEGER NOT NULL, away_goals INTEGER NOT NULL
    );
    """)


def record_predictions(conn: sqlite3.Connection, matches: list[MatchView], tables: list[Standing], now: datetime) -> int:
    ensure_history(conn)
    moment = utc(now)
    saved = 0
    for match in matches:
        item = match.assessment
        if item.is_demo or utc(match.kickoff) <= moment:
            continue
        probabilities = item.model_probs
        if (set(probabilities) != set(OUTCOMES) or
            any(not math.isfinite(p) or not 0 <= p <= 1 for p in probabilities.values()) or
            not math.isclose(sum(probabilities.values()), 1., abs_tol=1e-6)):
            continue
        # Store actual inputs, not merely a reference to a mutable standings table.
        code = next((league['code'] for league in LEAGUES if league['name']==match.competition), None)
        scoped = [row for row in tables if row.competition_code == code]
        inputs = json.dumps({'standings':[asdict(row) for row in scoped],
            'home_xg':item.home_xg,'away_xg':item.away_xg}, default=str, sort_keys=True)
        for line in match.books:
            if line.source != "the-odds-api" or line.last_update is None:
                continue
            quote_at = utc(line.last_update)
            age = (moment-quote_at).total_seconds()/3600
            prices = dict(zip(OUTCOMES, (line.home,line.draw,line.away)))
            if age < 0 or age > 24 or any(not math.isfinite(v) or v <= 1 for v in prices.values()):
                continue
            quality, _ = data_quality(odds_age_hours=age, used_table=item.used_table,
                bookmaker_count=len({b.bookmaker for b in match.books}), api_limited=item.api_limited,
                is_demo=False, stale_table=item.stale_table)
            quality = min(quality,item.quality)
            evs = {key:expected_value(probabilities[key],prices[key]) for key in OUTCOMES}
            qualifying = [key for key in OUTCOMES if EDGE_MIN+1e-12 < evs[key] <= MAX_SIGNAL_EV+1e-12
                          and prices[key] <= MAX_SINGLE_ODDS]
            pick = max(qualifying or list(OUTCOMES),key=lambda key:evs[key])
            eligible = bool(qualifying) and item.used_table and not item.stale_table and quality >= MIN_SIGNAL_QUALITY
            key = event_key(match.competition,match.home,match.away,match.kickoff)
            fingerprint = hashlib.sha256(json.dumps([key,line.bookmaker,MODEL_VERSION,quote_at.isoformat(),
                probabilities, prices,inputs,quality,eligible],sort_keys=True).encode()).hexdigest()
            cursor = conn.execute("""INSERT OR IGNORE INTO predictions
                (event_key,competition,home,away,kickoff,recorded_at,quote_at,bookmaker,model_version,source,
                 probabilities,odds,inputs,quality,pick,eligible,fingerprint)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                    key,match.competition,match.home,match.away,utc(match.kickoff).isoformat(),moment.isoformat(),
                    quote_at.isoformat(),line.bookmaker,MODEL_VERSION,line.source,json.dumps(probabilities),
                    json.dumps(prices),inputs,quality,pick,int(eligible),fingerprint))
            saved += cursor.rowcount
    conn.commit()
    return saved


def forecasts(conn: sqlite3.Connection) -> list[dict]:
    ensure_history(conn)
    return [dict(row) for row in conn.execute("""SELECT p.*, r.home_goals, r.away_goals
        FROM predictions p LEFT JOIN results r USING(event_key) ORDER BY p.recorded_at DESC, p.id DESC""")]


def save_result(conn: sqlite3.Connection, key: str, home_goals: int, away_goals: int,
                now: datetime | None = None) -> None:
    ensure_history(conn)
    if any(type(v) is not int or not 0 <= v <= 50 for v in (home_goals,away_goals)):
        raise ValueError("Tore müssen ganze Zahlen zwischen 0 und 50 sein.")
    moment=utc(now or datetime.now(timezone.utc))
    event=conn.execute("SELECT kickoff FROM predictions WHERE event_key=? LIMIT 1",(key,)).fetchone()
    if event is None or moment <= datetime.fromisoformat(event['kickoff']):
        raise ValueError("Nur Ergebnisse bekannter, bereits begonnener Spiele speichern.")
    with conn:
        previous=conn.execute("SELECT * FROM results WHERE event_key=?",(key,)).fetchone()
        conn.execute("INSERT INTO result_changes(event_key,changed_at,previous_home,previous_away,home_goals,away_goals) VALUES (?,?,?,?,?,?)",
            (key,moment.isoformat(),previous['home_goals'] if previous else None,previous['away_goals'] if previous else None,home_goals,away_goals))
        conn.execute("INSERT INTO results VALUES(?,?,?,?) ON CONFLICT(event_key) DO UPDATE SET home_goals=excluded.home_goals,away_goals=excluded.away_goals,recorded_at=excluded.recorded_at",
            (key,home_goals,away_goals,moment.isoformat()))


def backtest(rows: list[dict], *, bookmaker: str, model_version: str,
             selection: str = "first", competition: str | None = None) -> dict:
    """Replay pre-recorded forecasts, flat one-unit stakes on eligible tips.

    Brier is the multiclass sum of squared errors (range 0..2).
    Market baseline uses proportional de-margining of the same bookmaker.
    """
    if selection not in {"first","last"}:
        raise ValueError("Pro Spiel erste oder letzte Prognose wählen.")
    selected = {}
    for row in sorted(rows,key=lambda row:(row['recorded_at'],row['id']),reverse=selection=='last'):
        if row['bookmaker'] != bookmaker or row['model_version'] != model_version or row['source'] != 'the-odds-api':
            continue
        if competition and row['competition'] != competition:
            continue
        recorded,quote,kickoff = (datetime.fromisoformat(row[field]) for field in ('recorded_at','quote_at','kickoff'))
        if not quote <= recorded < kickoff or (recorded-quote).total_seconds() > 86400:
            continue
        selected.setdefault(row['event_key'],row)
    details=[]
    for row in selected.values():
        if row['home_goals'] is None:
            continue
        probs=json.loads(row['probabilities']); odds=json.loads(row['odds'])
        outcome='home' if row['home_goals']>row['away_goals'] else 'away' if row['home_goals']<row['away_goals'] else 'draw'
        total=sum(1/v for v in odds.values()); market={k:1/v/total for k,v in odds.items()}
        pick=row['pick']; hit=int(pick==outcome); eligible=bool(row['eligible'])
        details.append({'event_key':row['event_key'],'Spiel':f"{row['home']} – {row['away']}",
            'Liga':row['competition'],'Prognosezeit':row['recorded_at'],'Anpfiff':row['kickoff'],
            'p':probs[pick],'Treffer':hit,'Quote':odds[pick],'Value-Tipp':eligible,
            'G&V':odds[pick]-1 if eligible and hit else -1. if eligible else 0.,
            'Brier':sum((probs[k]-int(k==outcome))**2 for k in OUTCOMES),
            'Markt-Brier':sum((market[k]-int(k==outcome))**2 for k in OUTCOMES),
            'LogLoss':-math.log(max(probs[outcome],1e-15)),
            'Markt-LogLoss':-math.log(max(market[outcome],1e-15))})
    n=len(details); bets=sum(r['Value-Tipp'] for r in details); pnl=sum(r['G&V'] for r in details)
    calibration=[]
    for low in range(0,100,10):
        group=[r for r in details if low/100 <= r['p'] < (low+10)/100 or (low==90 and r['p']==1)]
        if group:
            calibration.append({'Band':f'{low}–{low+10} %','N':len(group),
                'Modell':sum(r['p'] for r in group)/len(group), 'Beobachtet':sum(r['Treffer'] for r in group)/len(group)})
    return {'n':n,'unsettled':len(selected)-n,'bets':bets,'pnl':pnl,'roi':pnl/bets if bets else None,
        'brier':sum(r['Brier'] for r in details)/n if n else None,
        'market_brier':sum(r['Markt-Brier'] for r in details)/n if n else None,
        'log_loss':sum(r['LogLoss'] for r in details)/n if n else None,
        'market_log_loss':sum(r['Markt-LogLoss'] for r in details)/n if n else None,
        'details':details,'calibration':calibration}


def quote_history(conn: sqlite3.Connection, match: MatchView) -> list[dict]:
    # Provider names and kickoff times can differ. Use the same team aliases as
    # the ingestion pipeline instead of requiring byte-identical team labels.
    rows = conn.execute("""SELECT fetched_at, last_update, bookmaker,
        home_odds, draw_odds, away_odds, source, home_team, away_team, kickoff
        FROM odds_snapshots WHERE competition=? AND source != 'demo'
        AND julianday(kickoff) BETWEEN julianday(?) AND julianday(?)
        ORDER BY fetched_at,id""", (match.competition,
        (utc(match.kickoff)-timedelta(hours=6)).isoformat(),
        (utc(match.kickoff)+timedelta(hours=6)).isoformat()))
    history = []
    for row in rows:
        direct = names_match(row['home_team'],match.home) and names_match(row['away_team'],match.away)
        swapped = names_match(row['home_team'],match.away) and names_match(row['away_team'],match.home)
        if not direct and not swapped:
            continue
        point = dict(row)
        if swapped and not direct:
            point['home_odds'],point['away_odds'] = point['away_odds'],point['home_odds']
        history.append(point)
    return history
