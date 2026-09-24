"""Pfade, Schwellen und API-Schlüssel.

Schlüssel kommen aus der Datei `.env` oder aus der Umgebung.
Leere Platzhalter zählen als „kein Schlüssel“ und führen zum Demo-Modus.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "valuepulse.sqlite3"

# Vorteil gegenüber der Quote, ab dem ein Value-Signal entsteht.
EDGE_MIN = 0.03
# Ab dieser Datenqualität darf ein Value-Signal grün werden.
QUALITY_GREEN_MIN = 75
# Quoten älter als diese Grenze senken die Datenqualität, stoppen aber nicht.
STALE_ODDS_HOURS = 24
# Ligatabellen älter als diese Grenze werden neu geholt.
STANDINGS_TTL_HOURS = 24
# Nur Spiele in diesem Fenster landen im Dashboard.
LOOKAHEAD_DAYS = 7

LEAGUES = (
    {"code": "PL", "sport": "soccer_epl", "name": "Premier League"},
    {"code": "BL1", "sport": "soccer_germany_bundesliga", "name": "Bundesliga"},
    {"code": "PD", "sport": "soccer_spain_la_liga", "name": "La Liga"},
    {"code": "SA", "sport": "soccer_italy_serie_a", "name": "Serie A"},
    {"code": "FL1", "sport": "soccer_france_ligue_one", "name": "Ligue 1"},
)

FOOTBALL_DATA_BASE = "https://api.football-data.org/v4"
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

_PLACEHOLDERS = {
    "",
    "changeme",
    "your_key_here",
    "dein_token",
    "dein_key",
    "xxx",
}


@dataclass(frozen=True)
class Settings:
    football_key: str
    odds_key: str
    db_path: Path

    @property
    def has_football_key(self) -> bool:
        return bool(self.football_key)

    @property
    def has_odds_key(self) -> bool:
        return bool(self.odds_key)

    @property
    def has_live_keys(self) -> bool:
        return self.has_football_key and self.has_odds_key


def masked_key(value: str) -> str:
    """Sichtbarer Hinweis, ohne den ganzen Schlüssel zu zeigen."""
    text = (value or "").strip()
    if not text:
        return "nicht gespeichert"
    if len(text) <= 4:
        return "gespeichert"
    return f"gespeichert, endet auf {text[-4:]}"


def _clean_key(value: str | None) -> str:
    text = (value or "").strip().strip('"').strip("'")
    if text.lower() in _PLACEHOLDERS:
        return ""
    return text


def load_settings() -> Settings:
    """Liest `.env` neu, damit ein nachgetragener Schlüssel ohne Codeänderung gilt."""
    load_dotenv(ROOT / ".env", override=False)
    db_override = os.getenv("VALUEPULSE_DB", "").strip()
    return Settings(
        football_key=_clean_key(os.getenv("FOOTBALL_DATA_API_KEY")),
        odds_key=_clean_key(os.getenv("ODDS_API_KEY")),
        db_path=Path(db_override) if db_override else DB_PATH,
    )


def save_env_keys(football_key: str, odds_key: str, path: Path | None = None) -> None:
    """Schreibt die beiden Schlüssel in `.env` und in die laufende Umgebung.

    Andere Zeilen in der Datei bleiben erhalten. Leere Felder schalten den
    Demo-Modus wieder ein.
    """
    target = path or (ROOT / ".env")
    updates = {
        "FOOTBALL_DATA_API_KEY": football_key.strip(),
        "ODDS_API_KEY": odds_key.strip(),
    }
    existing = target.read_text(encoding="utf-8").splitlines() if target.exists() else []
    seen: set[str] = set()
    lines: list[str] = []
    for line in existing:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            lines.append(line)
            continue
        name = line.split("=", 1)[0].strip()
        if name in updates:
            lines.append(f"{name}={updates[name]}")
            seen.add(name)
        else:
            lines.append(line)
    for name, value in updates.items():
        if name not in seen:
            lines.append(f"{name}={value}")
    target.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    os.environ["FOOTBALL_DATA_API_KEY"] = updates["FOOTBALL_DATA_API_KEY"]
    os.environ["ODDS_API_KEY"] = updates["ODDS_API_KEY"]
