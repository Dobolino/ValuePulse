import os
from datetime import date

from valuepulse.config import Settings, masked_key, save_env_keys
from valuepulse.pipeline import run
from valuepulse.providers import check_api_keys
from valuepulse.window import BERLIN
from tests.test_pipeline import NOW


class _Response:
    def __init__(self, status, payload=None):
        self.status_code = status
        self.headers = {}
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


class _Client:
    def __init__(self, odds_status=200):
        self.odds_status = odds_status

    def get(self, url, *, headers, params, timeout):
        if "the-odds-api" in url:
            return _Response(self.odds_status, [])
        return _Response(200, {"name": "Premier League"})


def test_gespeicherter_schluessel_ist_am_ende_sichtbar():
    assert masked_key("") == "nicht gespeichert"
    assert masked_key("abcd") == "gespeichert"
    assert masked_key("odds-live-key-91xz") == "gespeichert, endet auf 91xz"


def test_schluessel_werden_lokal_gespeichert(tmp_path):
    path = tmp_path / ".env"
    path.write_text("HINWEIS=bleibt\nFOOTBALL_DATA_API_KEY=alt\n", encoding="utf-8")
    previous = {
        "FOOTBALL_DATA_API_KEY": os.environ.get("FOOTBALL_DATA_API_KEY"),
        "ODDS_API_KEY": os.environ.get("ODDS_API_KEY"),
    }
    try:
        save_env_keys("fd-neu", "odds-neu", path=path)
        text = path.read_text(encoding="utf-8")
        assert "HINWEIS=bleibt" in text
        assert "FOOTBALL_DATA_API_KEY=fd-neu" in text
        assert "ODDS_API_KEY=odds-neu" in text
        assert os.environ["FOOTBALL_DATA_API_KEY"] == "fd-neu"
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def test_key_pruefung_meldet_gueltig_und_abgelehnt():
    ok = check_api_keys("fd", "odds", client=_Client())
    assert ok == {"football": "gültig", "odds": "gültig"}
    rejected = check_api_keys("fd", "odds", client=_Client(odds_status=401))
    assert rejected["football"] == "gültig"
    assert rejected["odds"] == "abgelehnt"
    missing = check_api_keys("", "", client=_Client())
    assert missing == {"football": "fehlt", "odds": "fehlt"}


def test_demo_bleibt_im_gewählten_zeitraum(tmp_path):
    data = run(
        Settings("", "", tmp_path / "valuepulse.sqlite3"),
        now=NOW,
        date_from=date(2026, 10, 1),
        date_to=date(2026, 10, 3),
    )
    assert data.mode == "demo"
    assert data.matches
    for match in data.matches:
        local = match.kickoff.astimezone(BERLIN).date()
        assert date(2026, 10, 1) <= local <= date(2026, 10, 3)
