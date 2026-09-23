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
    def __init__(self, by_status=None, payload=None):
        self.by_status = by_status
        self.payload = payload
        self.calls = 0

    def get(self, url, *, headers, params, timeout):
        self.calls += 1
        if self.by_status is not None:
            return FakeResponse({"message": "limit"}, status=self.by_status)
        if "/matches" in url:
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
            return FakeResponse(_odds_payload(), headers={"x-requests-remaining": "412"})
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


def test_ligen_sind_die_grossen_fuenf():
    codes = set(league_by_code())
    assert codes == {"PL", "BL1", "PD", "SA", "FL1"}
