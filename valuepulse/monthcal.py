"""Monatsraster für den Kalender.

Ein Klick setzt nur den Zeitraum. Die Pipeline startet erst, wenn der
Nutzer den Zeitraum bestätigt.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from valuepulse.models import MatchView

BERLIN = ZoneInfo("Europe/Berlin")


def month_weeks(year: int, month: int) -> list[list[date | None]]:
    """Wochen ab Montag. Tage außerhalb des Monats sind None."""
    weeks = calendar.Calendar(firstweekday=calendar.MONDAY).monthdayscalendar(year, month)
    grid: list[list[date | None]] = []
    for week in weeks:
        grid.append([date(year, month, day) if day else None for day in week])
    return grid


def apply_day_click(start: date | None, phase: str, day: date) -> tuple[date, date, str]:
    """Erster Klick setzt einen Tag. Der nächste Klick spannt den Bereich auf."""
    if start is None or phase != "end":
        return day, day, "end"
    if day < start:
        return day, start, "start"
    return start, day, "start"


def value_counts(matches: list[MatchView], year: int, month: int) -> dict[date, int]:
    """Value-Signale (grün oder gelb) je Kalendertag in Europe/Berlin."""
    counts: dict[date, int] = {}
    for match in matches:
        if match.assessment.signal not in {"green", "yellow"}:
            continue
        kickoff = match.kickoff
        if kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=timezone.utc)
        local = kickoff.astimezone(BERLIN).date()
        if local.year != year or local.month != month:
            continue
        counts[local] = counts.get(local, 0) + 1
    return counts


def shift_month(year: int, month: int, step: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + step
    return index // 12, index % 12 + 1
