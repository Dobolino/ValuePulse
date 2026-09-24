"""Holt Daten, speichert Quoten und baut die Ampel.

Ablauf:
1. Schlüssel fehlen → Demo-Modus.
2. Sonst APIs abfragen und jede Quote in SQLite schreiben.
3. Bei HTTP 429, Auth- oder Netzfehler: gespeicherte Quoten nutzen.
4. Liegt nichts Speicherbares vor: Demo-Modus.
5. Alte Quoten senken die Datenqualität, stoppen die Rechnung aber nicht.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from valuepulse.config import LEAGUES, Settings, load_settings
from valuepulse.db import connect, latest_quotes, load_standings, save_quotes, save_standings
from valuepulse.demo import build_demo
from valuepulse.model import assess, strength_from_table
from valuepulse.models import DashboardData, Fixture, MatchView, Quote, Standing
from valuepulse.names import names_match, similarity
from valuepulse.providers import (
    AuthError,
    ProviderError,
    RateLimitError,
    default_client,
    fetch_matches,
    fetch_odds,
    fetch_standings,
)
from valuepulse.window import BERLIN, Window, resolve_window

_SIGNAL_ORDER = {"green": 0, "yellow": 1, "red": 2}
_MATCH_WINDOW_SECONDS = 6 * 3600


def run(
    settings: Settings | None = None,
    client=None,
    now: datetime | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> DashboardData:
    """Einstieg für das Dashboard. Wirft keine Fehler bis in die Oberfläche."""
    settings = settings or load_settings()
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    window = resolve_window(moment, date_from, date_to)
    http = client or default_client()

    if not settings.has_live_keys:
        missing = []
        if not settings.has_football_key:
            missing.append("FOOTBALL_DATA_API_KEY")
        if not settings.has_odds_key:
            missing.append("ODDS_API_KEY")
        reason = "Es fehlt: " + ", ".join(missing) + "."
        return _safe_demo(moment, reason, window)

    try:
        conn = connect(settings.db_path)
    except Exception as exc:
        return _safe_demo(moment, f"Die lokale Datenbank ließ sich nicht öffnen ({exc}).", window)

    try:
        return _collect(settings, http, conn, moment, window)
    except Exception as exc:
        return _safe_demo(moment, f"Unerwarteter Fehler bei den Live-Daten ({exc}).", window)
    finally:
        conn.close()


def _collect(settings: Settings, client, conn, now: datetime, window: Window) -> DashboardData:
    warnings: list[str] = []
    fixtures: list[Fixture] = []
    standings: list[Standing] = []
    quotes: list[Quote] = []
    football_limited = False
    odds_limited = False
    odds_remaining: int | None = None

    football_budget: int | None = None
    cached_standings = load_standings(conn)
    have_table = {row.competition_code for row in cached_standings}

    for league in LEAGUES:
        if football_budget is not None and football_budget < 1:
            football_limited = True
            warnings.append("Football-Data: Das Minutenlimit ist erreicht, weitere Ligen warten.")
            break
        try:
            batch, football_budget = fetch_matches(
                client,
                settings.football_key,
                league,
                date_from=window.start_day.isoformat(),
                date_to=window.end_day.isoformat(),
            )
            fixtures.extend(batch)
        except RateLimitError:
            football_limited = True
            warnings.append("Football-Data hat das Abruf-Limit erreicht (HTTP 429).")
            break
        except AuthError:
            warnings.append("Football-Data hat den Schlüssel abgelehnt.")
            break
        except ProviderError as exc:
            warnings.append(f"{league['name']}: Spieldaten nicht ladbar ({exc}).")

    # Tabellen nicht im selben Schwung wie die Spiele ziehen, wenn das Minutenlimit
    # schon eng ist. Eine gespeicherte Tabelle reicht, sonst rechnet das Modell neutral.
    if not football_limited:
        for league in LEAGUES:
            if league["code"] in have_table:
                continue
            if football_budget is not None and football_budget < 1:
                football_limited = True
                warnings.append("Football-Data: Tabelle übersprungen, das Minutenlimit ist erreicht.")
                break
            try:
                rows, football_budget = fetch_standings(client, settings.football_key, league)
                standings.extend(rows)
            except RateLimitError:
                football_limited = True
                warnings.append("Football-Data hat das Abruf-Limit erreicht (HTTP 429).")
                break
            except AuthError:
                warnings.append("Football-Data hat den Schlüssel abgelehnt.")
                break
            except ProviderError as exc:
                warnings.append(f"{league['name']}: Tabelle nicht ladbar ({exc}).")

    if standings:
        save_standings(conn, standings, now)
        fresh_codes = {row.competition_code for row in standings}
        standings.extend(row for row in cached_standings if row.competition_code not in fresh_codes)

    odds_outside = 0
    for league in LEAGUES:
        try:
            batch, remaining, outside = fetch_odds(
                client,
                settings.odds_key,
                league,
                window_start=_utc_start(window),
                window_end=_utc_end(window),
                fetched_at=now,
            )
            quotes.extend(batch)
            odds_outside += outside
            if remaining is not None:
                odds_remaining = remaining
        except RateLimitError:
            odds_limited = True
            warnings.append("The Odds API hat das Abruf-Limit erreicht (HTTP 429).")
            break
        except AuthError:
            warnings.append("The Odds API hat den Schlüssel abgelehnt.")
            break
        except ProviderError as exc:
            warnings.append(f"{league['name']}: Quoten nicht ladbar ({exc}).")

    used_cache = False
    if quotes:
        save_quotes(conn, quotes, now)
    else:
        cached = latest_quotes(conn)
        if cached:
            quotes = cached
            used_cache = True
            warnings.append("Keine frischen Quoten. Gespeicherte Quoten werden verwendet.")
        else:
            if odds_outside and "Zeitraum" not in " ".join(warnings):
                warnings.append(
                    "The Odds API hat Spiele geliefert, aber keines liegt im gewählten Zeitraum."
                )
            elif not odds_limited and not any("Odds API" in note for note in warnings):
                warnings.append("The Odds API hat im Zeitraum keine lesbare 1X2-Quote geliefert.")
            reason = " ".join(dict.fromkeys(warnings)) or "Es lagen keine Quoten vor."
            return _safe_demo(now, reason, window, odds_remaining=odds_remaining)

    if not fixtures:
        fixtures = _fixtures_from_quotes(quotes, window)
        if fixtures:
            warnings.append("Die Spielleiste kommt aus den Quoten, nicht aus Football-Data.")
        else:
            return _safe_demo(now, "Weder Live-Spiele noch gespeicherte Quoten im Zeitfenster.", window)

    if not standings:
        standings = load_standings(conn)
        if standings:
            warnings.append("Die Tabelle stammt aus dem lokalen Speicher.")
        else:
            warnings.append("Keine Tabelle vorhanden. Das Modell nutzt Neutralwerte.")

    api_limited = football_limited or odds_limited or used_cache
    matches = _evaluate(
        fixtures, standings, quotes, now, window, api_limited=api_limited, is_demo=False
    )
    if not matches:
        return _safe_demo(now, "Quoten und Spiele ließen sich keinem gemeinsamen Spiel zuordnen.", window)

    if football_limited and quotes and not used_cache:
        mode = "eingeschraenkt"
        banner = (
            "Football-Data hat das Abruf-Limit erreicht (HTTP 429). "
            "Die Quoten von The Odds API werden trotzdem verwendet. "
            "Die Datenqualität ist deshalb etwas niedriger."
        )
    elif used_cache or odds_limited:
        mode = "cache"
        banner = (
            "Gelbe Warnung: API-Limit oder Störung. "
            "ValuePulse rechnet mit gespeicherten Daten weiter und zieht Datenqualität ab."
        )
    elif warnings:
        mode = "eingeschraenkt"
        banner = "Live-Daten mit Lücken. Betroffene Spiele haben eine geringere Datenqualität."
    else:
        mode = "live"
        banner = "Live-Daten geladen. Quoten sind in valuepulse.sqlite3 gespeichert."

    return DashboardData(
        mode=mode,
        banner=banner,
        matches=matches,
        warnings=list(dict.fromkeys(warnings)),
        odds_requests_remaining=odds_remaining,
        generated_at=now,
    )


def _safe_demo(
    now: datetime,
    reason: str,
    window: Window,
    *,
    odds_remaining: int | None = None,
) -> DashboardData:
    try:
        data = _from_demo(now, reason, window)
    except Exception:
        data = DashboardData(
            mode="demo",
            banner=(
                "Demo-Modus: Die Beispiel-Daten ließen sich nicht aufbauen. "
                f"Grund: {reason}"
            ),
            matches=[],
            generated_at=now,
        )
    data.odds_requests_remaining = odds_remaining
    return data


def _from_demo(now: datetime, reason: str, window: Window) -> DashboardData:
    fixtures, table, quotes, banner = build_demo(now, reason, window)
    matches = _evaluate(fixtures, table, quotes, now, window, api_limited=False, is_demo=True)
    return DashboardData(
        mode="demo",
        banner=banner,
        matches=matches,
        warnings=[],
        generated_at=now,
    )


def _fixtures_from_quotes(quotes: list[Quote], window: Window) -> list[Fixture]:
    seen: set[tuple] = set()
    fixtures: list[Fixture] = []
    for quote in quotes:
        if not window.contains(quote.kickoff):
            continue
        key = (quote.home, quote.away, quote.kickoff.replace(minute=0, second=0, microsecond=0))
        if key in seen:
            continue
        seen.add(key)
        fixtures.append(
            Fixture(
                competition=quote.competition,
                competition_code=_code_for_competition(quote.competition),
                kickoff=quote.kickoff,
                home=quote.home,
                away=quote.away,
                match_id=f"odds-{quote.home}-{quote.away}",
            )
        )
    return fixtures


def _evaluate(
    fixtures: list[Fixture],
    standings: list[Standing],
    quotes: list[Quote],
    now: datetime,
    window: Window,
    *,
    api_limited: bool,
    is_demo: bool,
) -> list[MatchView]:
    views: list[MatchView] = []
    for fixture in fixtures:
        if not window.contains(fixture.kickoff):
            continue
        if not is_demo and fixture.kickoff < now - timedelta(hours=3):
            continue
        table = _table_for(fixture, standings)
        attached = _attach_quotes(fixture, quotes)
        model = strength_from_table(fixture.home, fixture.away, table)
        result = assess(
            model=model,
            quotes=attached,
            now=now,
            api_limited=api_limited,
            is_demo=is_demo,
        )
        if result is None:
            continue
        views.append(
            MatchView(
                competition=fixture.competition,
                kickoff=fixture.kickoff,
                kickoff_label=_kickoff_label(fixture.kickoff),
                home=fixture.home,
                away=fixture.away,
                assessment=result,
            )
        )
    views.sort(key=lambda item: (_SIGNAL_ORDER[item.assessment.signal], item.kickoff))
    return views


def _code_for_competition(name: str) -> str:
    for league in LEAGUES:
        if league["name"] == name:
            return league["code"]
    return ""


def _table_for(fixture: Fixture, standings: list[Standing]) -> list[Standing]:
    """Tabelle der Liga. Fehlt der Code, nur wenn beide Teams eindeutig darin stehen."""
    if fixture.competition_code:
        scoped = [row for row in standings if row.competition_code == fixture.competition_code]
        if scoped:
            return scoped
    matching_codes = []
    for code in sorted({row.competition_code for row in standings}):
        rows = [row for row in standings if row.competition_code == code]
        home_ok = any(names_match(row.team, fixture.home) for row in rows)
        away_ok = any(names_match(row.team, fixture.away) for row in rows)
        if home_ok and away_ok:
            matching_codes.append(code)
    if len(matching_codes) == 1:
        code = matching_codes[0]
        return [row for row in standings if row.competition_code == code]
    return []


def _attach_quotes(fixture: Fixture, quotes: list[Quote]) -> list[Quote]:
    matched: list[Quote] = []
    for quote in quotes:
        if abs((fixture.kickoff - quote.kickoff).total_seconds()) > _MATCH_WINDOW_SECONDS:
            continue
        direct = similarity(fixture.home, quote.home) + similarity(fixture.away, quote.away)
        swapped = similarity(fixture.home, quote.away) + similarity(fixture.away, quote.home)
        if direct >= 1.2 and direct >= swapped:
            matched.append(quote)
        elif swapped >= 1.2 and swapped > direct:
            matched.append(_swap_quote(quote))
    return matched


def _swap_quote(quote: Quote) -> Quote:
    return Quote(
        competition=quote.competition,
        kickoff=quote.kickoff,
        home=quote.away,
        away=quote.home,
        bookmaker=quote.bookmaker,
        home_odds=quote.away_odds,
        draw_odds=quote.draw_odds,
        away_odds=quote.home_odds,
        last_update=quote.last_update,
        source=quote.source,
    )


def _utc_start(window: Window) -> datetime:
    return datetime.combine(window.start_day, time.min, tzinfo=BERLIN).astimezone(timezone.utc)


def _utc_end(window: Window) -> datetime:
    return datetime.combine(window.end_day, time.max, tzinfo=BERLIN).astimezone(timezone.utc)


def _kickoff_label(moment: datetime) -> str:
    try:
        from zoneinfo import ZoneInfo

        local = moment.astimezone(ZoneInfo("Europe/Berlin"))
    except Exception:
        local = moment
    return local.strftime("%d.%m.%Y, %H:%M Uhr")
