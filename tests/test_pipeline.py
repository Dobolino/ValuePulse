from datetime import datetime, timedelta, timezone

from valuepulse.config import Settings
from valuepulse.pipeline import run
from valuepulse.providers import league_by_code


NOW = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
KICKOFF = (NOW + timedelta(days=2)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class FakeResponse:
    def __init__(self, payload, status=200, headers=None):
        self._payload = payload
        self.status_code = status
        self.headers = headers or {}

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, by_status=None, payload=None, matches=None, odds=None, football_status=None, odds_by_region=None):
        self.by_status = by_status
        self.payload = payload
        self.matches = matches
        self.odds = odds
        self.football_status = football_status
        self.odds_by_region = odds_by_region
        self.calls = 0
        self.params = []

    def get(self, url, *, headers, params, timeout):
        self.calls += 1
        self.params.append(params)
        if self.by_status is not None:
            return FakeResponse({"message": "limit"}, status=self.by_status)
        if self.football_status is not None and ("/matches" in url or "/standings" in url):
            return FakeResponse({"message": "limit"}, status=self.football_status)
        if "/matches" in url:
            if self.matches is not None:
                return FakeResponse({"matches": self.matches})
            return FakeResponse(
                {
                    "matches": [
                        {
                            "id": 7,
                            "utcDate": KICKOFF,
                            "status": "TIMED",
                            "homeTeam": {"name": "Arsenal FC"},
                            "awayTeam": {"name": "Chelsea FC"},
                        }
                    ]
                }
            )
        if "/standings" in url:
            return FakeResponse(
                {
                    "standings": [
                        {
                            "type": "TOTAL",
                            "table": [
                                _row("Arsenal FC", 20, 8, 30),
                                _row("Liverpool FC", 16, 10, 22),
                                _row("Chelsea FC", 9, 16, 10),
                                _row("Everton FC", 10, 14, 11),
                            ],
                        }
                    ]
                }
            )
        if "/odds" in url:
            if self.odds_by_region is not None:
                payload = self.odds_by_region.get(params.get("regions"), [])
            else:
                payload = self.odds if self.odds is not None else _odds_payload()
            return FakeResponse(payload, headers={"x-requests-remaining": "412"})
        raise AssertionError(url)


def _row(name, goals_for, goals_against, points):
    return {
        "team": {"name": name},
        "playedGames": 8,
        "points": points,
        "goalsFor": goals_for,
        "goalsAgainst": goals_against,
    }


def _odds_payload():
    outcomes = [
        {"name": "Arsenal", "price": 2.10},
        {"name": "Draw", "price": 3.60},
        {"name": "Chelsea", "price": 3.40},
    ]
    long_odds = [
        {"name": "Arsenal", "price": 2.05},
        {"name": "Draw", "price": 3.50},
        {"name": "Chelsea", "price": 3.30},
    ]
    def book(title, rows):
        return {
            "key": title,
            "title": title,
            "last_update": NOW.isoformat().replace("+00:00", "Z"),
            "markets": [{"key": "h2h", "outcomes": rows}],
        }
    return [
        {
            "id": "evt",
            "commence_time": KICKOFF,
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "bookmakers": [book("Pinnacle", outcomes), book("Unibet", long_odds)],
        }
    ]


def test_ohne_schluessel_startet_demo(tmp_path):
    client = FakeClient()
    data = run(Settings("", "", tmp_path / "valuepulse.sqlite3"), client=client, now=NOW)
    assert client.calls == 0
    assert data.mode == "demo"
    assert data.matches
    assert any(match.assessment.signal == "yellow" for match in data.matches)
    assert any(match.assessment.signal == "red" for match in data.matches)
    assert all(match.assessment.signal != "green" for match in data.matches)
    assert any("Datenqualität verringert" in match.assessment.headline for match in data.matches)
    assert any(match.assessment.headline == "Kein Vorteil gegenüber dem Buchmacher." for match in data.matches)


def test_live_speichert_quoten_und_findet_value(tmp_path):
    path = tmp_path / "valuepulse.sqlite3"
    client = FakeClient()
    data = run(Settings("fd-key", "odds-key", path), client=client, now=NOW)
    assert data.mode == "live"
    assert data.odds_requests_remaining == 412
    assert path.exists()
    home = next(match for match in data.matches if match.home == "Arsenal FC")
    assert home.assessment.edge > 0.03
    assert home.assessment.signal == "green"
    assert "Modell sieht" in home.assessment.explanation
    assert client.calls > 0
    assert any(params.get("regions") == "eu" for params in client.params)


def test_football_429_nutzt_trotzdem_die_odds_api(tmp_path):
    data = run(
        Settings("fd-key", "odds-key", tmp_path / "valuepulse.sqlite3"),
        client=FakeClient(football_status=429),
        now=NOW,
    )
    assert data.mode != "demo"
    assert any(match.home == "Arsenal" for match in data.matches)
    assert "The Odds API werden trotzdem verwendet" in data.banner
    assert "Nordstern" not in {match.home for match in data.matches}


def test_europa_ohne_quote_weicht_auf_grossbritannien_aus(tmp_path):
    kickoff = KICKOFF
    bare = [
        {
            "id": "evt",
            "commence_time": kickoff,
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "bookmakers": [],
        }
    ]
    client = FakeClient(
        football_status=429,
        odds_by_region={"eu": bare, "uk": _odds_payload()},
    )
    data = run(Settings("fd-key", "odds-key", tmp_path / "valuepulse.sqlite3"), client=client, now=NOW)
    assert data.mode != "demo"
    assert any(match.home == "Arsenal" for match in data.matches)
    assert any(params.get("regions") == "uk" for params in client.params)


def test_unentschieden_wird_als_remis_gelesen(tmp_path):
    payload = _odds_payload()
    for book in payload[0]["bookmakers"]:
        for outcome in book["markets"][0]["outcomes"]:
            if outcome["name"] == "Draw":
                outcome["name"] = "Unentschieden"
    data = run(
        Settings("fd-key", "odds-key", tmp_path / "valuepulse.sqlite3"),
        client=FakeClient(odds=payload),
        now=NOW,
    )
    assert data.mode == "live"
    assert any(match.home == "Arsenal FC" for match in data.matches)


def test_http_429_ohne_speicher_wird_demo(tmp_path):
    data = run(
        Settings("fd-key", "odds-key", tmp_path / "valuepulse.sqlite3"),
        client=FakeClient(by_status=429),
        now=NOW,
    )
    assert data.mode == "demo"
    assert data.matches


def test_http_429_nutzt_gespeicherte_quoten(tmp_path):
    path = tmp_path / "valuepulse.sqlite3"
    first = run(Settings("fd-key", "odds-key", path), client=FakeClient(), now=NOW)
    assert first.mode == "live"
    second = run(Settings("fd-key", "odds-key", path), client=FakeClient(by_status=429), now=NOW)
    assert second.mode == "cache"
    assert second.matches
    assert any("gespeicherte" in note.lower() or "API-Limit" in note for match in second.matches for note in match.assessment.quality_notes)
    assert all(match.assessment.quality <= 70 for match in second.matches)


def _assert_demo_fallback(data, reason_part: str) -> None:
    assert data.mode == "demo"
    assert data.matches
    assert reason_part in data.banner
    assert "TypeError" not in data.banner
    assert "Unerwarteter Fehler" not in data.banner


def test_ohne_quoten_faellt_auf_demo_zurueck(tmp_path):
    data = run(
        Settings("fd-key", "odds-key", tmp_path / "valuepulse.sqlite3"),
        client=FakeClient(odds=[]),
        now=NOW,
    )
    _assert_demo_fallback(data, "keine lesbare 1X2-Quote")


def test_ohne_spiele_im_zeitfenster_faellt_auf_demo_zurueck(tmp_path):
    from valuepulse.db import connect, save_quotes
    from valuepulse.models import Quote

    path = tmp_path / "valuepulse.sqlite3"
    conn = connect(path)
    stored_at = datetime.now(timezone.utc) - timedelta(days=10)
    save_quotes(
        conn,
        [
            Quote(
                competition="Premier League",
                kickoff=datetime(2026, 1, 15, 15, 0, tzinfo=timezone.utc),
                home="Arsenal",
                away="Chelsea",
                bookmaker="Alt",
                home_odds=2.0,
                draw_odds=3.4,
                away_odds=3.8,
                last_update=stored_at,
                source="the-odds-api",
            )
        ],
        stored_at,
    )
    conn.close()
    data = run(
        Settings("fd-key", "odds-key", path),
        client=FakeClient(matches=[], odds=[]),
        now=NOW,
    )
    _assert_demo_fallback(data, "Zeitfenster")


def test_ohne_zuordnung_faellt_auf_demo_zurueck(tmp_path):
    other = (NOW + timedelta(days=3)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    odds = [
        {
            "id": "other",
            "commence_time": other,
            "home_team": "Bayern Munich",
            "away_team": "Borussia Dortmund",
            "bookmakers": [
                {
                    "key": "book",
                    "title": "Buch",
                    "last_update": NOW.isoformat().replace("+00:00", "Z"),
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Bayern Munich", "price": 1.7},
                                {"name": "Draw", "price": 3.8},
                                {"name": "Borussia Dortmund", "price": 4.6},
                            ],
                        }
                    ],
                }
            ],
        }
    ]
    data = run(
        Settings("fd-key", "odds-key", tmp_path / "valuepulse.sqlite3"),
        client=FakeClient(odds=odds),
        now=NOW,
    )
    _assert_demo_fallback(data, "keinem gemeinsamen Spiel")


def test_ligen_sind_die_grossen_fuenf():
    codes = set(league_by_code())
    assert codes == {"PL", "BL1", "PD", "SA", "FL1"}
