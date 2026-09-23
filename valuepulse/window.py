"""Zeitraum, den der Kalender ausdrücklich zur Berechnung freigibt.

Die Tage gelten als Kalendertage in Europe/Berlin, damit ein Abendspiel
nicht auf den nächsten UTC-Tag rutscht.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from valuepulse.config import LOOKAHEAD_DAYS

BERLIN = ZoneInfo("Europe/Berlin")


@dataclass(frozen=True)
class Window:
    start_day: date
    end_day: date

    def contains(self, moment: datetime) -> bool:
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        local_day = moment.astimezone(BERLIN).date()
        return self.start_day <= local_day <= self.end_day


def resolve_window(now: datetime, date_from: date | None, date_to: date | None) -> Window:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    start = date_from or now.astimezone(BERLIN).date()
    end = date_to or (start + timedelta(days=LOOKAHEAD_DAYS))
    if end < start:
        start, end = end, start
    return Window(start, end)
