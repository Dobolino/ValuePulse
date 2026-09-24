"""Abruf von Football-Data.org und The Odds API.

Einzelne fehlerhafte Datensätze werden übersprungen. HTTP 429 und
Netzwerkfehler wandern als klare Fehler nach oben; die Pipeline entscheidet
dann über Speicher oder Demo-Modus.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol

import requests

from valuepulse.config import FOOTBALL_DATA_BASE, LEAGUES, ODDS_API_BASE
from valuepulse.models import Fixture, Quote, Standing
from valuepulse.names import names_match


class ProviderError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class RateLimitError(ProviderError):
    """HTTP 429: Abruf-Kontingent ist aufgebraucht."""


class AuthError(ProviderError):
    """Schlüssel fehlt der API oder wurde abgelehnt."""


class HttpClient(Protocol):
    def get(self, url: str, *, headers: dict, params: dict, timeout: float) -> Any:
        ...


def default_client() -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = "ValuePulse/1.0"
    return session


def parse_dt(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _request_json(client: HttpClient, url: str, *, headers: dict, params: dict) -> tuple[Any, Any]:
    last_error: Exception | None = None
    for attempt in (1, 2):
        try:
            response = client.get(url, headers=headers, params=params, timeout=12)
        except requests.RequestException as exc:
            last_error = exc
            if attempt == 1:
                continue
            raise ProviderError("Die Verbindung zur API ist fehlgeschlagen.") from exc
        status = getattr(response, "status_code", 0)
        if status == 429:
            raise RateLimitError("API-Limit erreicht (HTTP 429).", status=429)
        if status == 401:
            raise AuthError("Der API-Schlüssel wurde abgelehnt.", status=status)
        if status == 403:
            raise ProviderError("Zugriff verweigert (HTTP 403).", status=403)
        if status >= 500 and attempt == 1:
            continue
        if status >= 400:
            raise ProviderError(f"Die API antwortete mit Fehler {status}.", status=status)
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderError("Die API lieferte keine lesbaren Daten.") from exc
        return payload, getattr(response, "headers", {})
    raise ProviderError("Die Verbindung zur API ist fehlgeschlagen.") from last_error


def fetch_matches(
    client: HttpClient,
    api_key: str,
    league: dict,
    *,
    date_from: str,
    date_to: str,
) -> tuple[list[Fixture], int | None]:
    payload, headers = _request_json(
        client,
        f"{FOOTBALL_DATA_BASE}/competitions/{league['code']}/matches",
        headers={"X-Auth-Token": api_key},
        params={"dateFrom": date_from, "dateTo": date_to},
    )
    fixtures: list[Fixture] = []
    for item in payload.get("matches") or []:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "")
        if status not in {"SCHEDULED", "TIMED"}:
            continue
        kickoff = parse_dt(item.get("utcDate"))
        home = (item.get("homeTeam") or {}).get("name") or (item.get("homeTeam") or {}).get("shortName")
        away = (item.get("awayTeam") or {}).get("name") or (item.get("awayTeam") or {}).get("shortName")
        if kickoff is None or not home or not away:
            continue
        fixtures.append(
            Fixture(
                competition=league["name"],
                competition_code=league["code"],
                kickoff=kickoff,
                home=str(home),
                away=str(away),
                match_id=str(item.get("id") or f"{league['code']}-{home}-{away}"),
            )
        )
    return fixtures, _minute_budget(headers)


def fetch_standings(client: HttpClient, api_key: str, league: dict) -> tuple[list[Standing], int | None]:
    payload, headers = _request_json(
        client,
        f"{FOOTBALL_DATA_BASE}/competitions/{league['code']}/standings",
        headers={"X-Auth-Token": api_key},
        params={},
    )
    table: list[dict] = []
    for block in payload.get("standings") or []:
        if isinstance(block, dict) and block.get("type") == "TOTAL":
            table = block.get("table") or []
            break
    rows: list[Standing] = []
    for item in table:
        if not isinstance(item, dict):
            continue
        team = (item.get("team") or {}).get("name")
        if not team:
            continue
        try:
            rows.append(
                Standing(
                    competition_code=league["code"],
                    team=str(team),
                    played=int(item.get("playedGames") or 0),
                    points=int(item.get("points") or 0),
                    goals_for=int(item.get("goalsFor") or 0),
                    goals_against=int(item.get("goalsAgainst") or 0),
                )
            )
        except (TypeError, ValueError):
            continue
    return rows, _minute_budget(headers)


def fetch_odds(
    client: HttpClient,
    api_key: str,
    league: dict,
    *,
    window_start: datetime,
    window_end: datetime,
    fetched_at: datetime,
) -> tuple[list[Quote], list[Quote], int | None, int]:
    """Lädt 1X2-Quoten. Europa zuerst, Großbritannien nur wenn dort keine Quote lesbar ist.

    Der zweite Wert sind lesbare Quoten nach dem Zeitraum. Der vierte zählt
    Spiele, die außerhalb lagen.
    """
    quotes, later, remaining, outside = _fetch_odds_region(
        client,
        api_key,
        league,
        region="eu",
        window_start=window_start,
        window_end=window_end,
        fetched_at=fetched_at,
    )
    if quotes or later or outside:
        return quotes, later, remaining, outside
    uk_quotes, uk_later, uk_remaining, uk_outside = _fetch_odds_region(
        client,
        api_key,
        league,
        region="uk",
        window_start=window_start,
        window_end=window_end,
        fetched_at=fetched_at,
    )
    if uk_remaining is not None:
        remaining = uk_remaining
    return uk_quotes, uk_later, remaining, outside + uk_outside


def _fetch_odds_region(
    client: HttpClient,
    api_key: str,
    league: dict,
    *,
    region: str,
    window_start: datetime,
    window_end: datetime,
    fetched_at: datetime,
) -> tuple[list[Quote], list[Quote], int | None, int]:
    payload, headers = _request_json(
        client,
        f"{ODDS_API_BASE}/sports/{league['sport']}/odds",
        headers={},
        params={
            "apiKey": api_key,
            "regions": region,
            "markets": "h2h",
            "oddsFormat": "decimal",
            "dateFormat": "iso",
        },
    )
    remaining = _remaining(headers)
    if not isinstance(payload, list):
        raise ProviderError("Die Quoten-API lieferte ein unerwartetes Format.")

    quotes: list[Quote] = []
    later: list[Quote] = []
    outside = 0
    for event in payload:
        if not isinstance(event, dict):
            continue
        kickoff = parse_dt(event.get("commence_time"))
        home = event.get("home_team")
        away = event.get("away_team")
        if kickoff is None or not home or not away:
            continue
        if kickoff < window_start or kickoff > window_end:
            outside += 1
            if kickoff > window_end:
                later.extend(_quotes_for_event(event, league, kickoff, str(home), str(away), fetched_at))
            continue
        quotes.extend(_quotes_for_event(event, league, kickoff, str(home), str(away), fetched_at))
    return quotes, later, remaining, outside


def _minute_budget(headers: Any) -> int | None:
    """Restliche Football-Data-Abrufe in dieser Minute, falls die API sie nennt."""
    if headers is None:
        return None
    getter = getattr(headers, "get", None)
    if getter is None:
        return None
    raw = getter("X-Requests-Available-Minute") or getter("x-requests-available-minute")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _remaining(headers: Any) -> int | None:
    if headers is None:
        return None
    getter = getattr(headers, "get", None)
    if getter is None:
        return None
    raw = getter("x-requests-remaining") or getter("X-Requests-Remaining")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _quotes_for_event(
    event: dict,
    league: dict,
    kickoff: datetime,
    home: str,
    away: str,
    fetched_at: datetime,
) -> list[Quote]:
    quotes: list[Quote] = []
    for book in event.get("bookmakers") or []:
        quote = _quote_from_book(book, league["name"], kickoff, home, away, fetched_at)
        if quote is not None:
            quotes.append(quote)
    return quotes


def _quote_from_book(
    book: dict,
    competition: str,
    kickoff: datetime,
    home: str,
    away: str,
    fetched_at: datetime,
) -> Quote | None:
    if not isinstance(book, dict):
        return None
    title = str(book.get("title") or book.get("key") or "").strip()
    if not title:
        return None
    outcomes = []
    for market in book.get("markets") or []:
        if isinstance(market, dict) and market.get("key") == "h2h":
            outcomes = market.get("outcomes") or []
            break
    prices = {"home": None, "draw": None, "away": None}
    unnamed: list[float] = []
    for outcome in outcomes:
        if not isinstance(outcome, dict):
            continue
        name = str(outcome.get("name") or "")
        try:
            price = float(outcome.get("price"))
        except (TypeError, ValueError):
            continue
        if price <= 1.01:
            continue
        slot = _slot(name, home, away)
        if slot is None:
            unnamed.append(price)
            continue
        if prices[slot] is None or price > prices[slot]:
            prices[slot] = price
    if prices["draw"] is None and len(unnamed) == 1 and prices["home"] is not None and prices["away"] is not None:
        prices["draw"] = unnamed[0]
    if any(value is None for value in prices.values()):
        return None
    last_update = parse_dt(book.get("last_update")) or fetched_at
    return Quote(
        competition=competition,
        kickoff=kickoff,
        home=home,
        away=away,
        bookmaker=title,
        home_odds=float(prices["home"]),
        draw_odds=float(prices["draw"]),
        away_odds=float(prices["away"]),
        last_update=last_update,
        source="the-odds-api",
    )


_DRAW_NAMES = {"draw", "tie", "x", "unentschieden", "the draw", "remis", "nul"}


def _slot(name: str, home: str, away: str) -> str | None:
    if name.strip().lower() in _DRAW_NAMES:
        return "draw"
    if names_match(name, home):
        return "home"
    if names_match(name, away):
        return "away"
    return None


def league_by_code() -> dict[str, dict]:
    return {league["code"]: league for league in LEAGUES}


def check_api_keys(football_key: str, odds_key: str, client: HttpClient | None = None) -> dict[str, str]:
    """Prüft die Schlüssel mit je einem kleinen Abruf. Speichert nichts."""
    http = client or default_client()
    return {
        "football": _check_one(football_key, lambda key: _ping_football(http, key)),
        "odds": _check_one(odds_key, lambda key: _ping_odds(http, key)),
    }


def _check_one(key: str, call) -> str:
    if not key.strip():
        return "fehlt"
    try:
        call(key.strip())
    except AuthError:
        return "abgelehnt"
    except RateLimitError:
        return "limit"
    except ProviderError as exc:
        if exc.status == 403:
            return "abgelehnt"
        return "nicht erreichbar"
    return "gültig"


def _ping_football(client: HttpClient, key: str) -> None:
    _request_json(
        client,
        f"{FOOTBALL_DATA_BASE}/competitions/PL",
        headers={"X-Auth-Token": key},
        params={},
    )


def _ping_odds(client: HttpClient, key: str) -> None:
    _request_json(
        client,
        f"{ODDS_API_BASE}/sports",
        headers={},
        params={"apiKey": key},
    )
