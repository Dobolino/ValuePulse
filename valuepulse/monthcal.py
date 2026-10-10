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


def range_role(day: date, start: date, end: date) -> str:
    """Rolle eines Tages im gewählten Zeitraum.

    ``start`` und ``end`` dürfen vertauscht sein. Ein einzelner Tag ist
    ``single``. Sonst sind die Ränder ``start`` und ``end``, Tage dazwischen
    ``mid``, alles außerhalb ``outside``.
    """
    if end < start:
        start, end = end, start
    if day < start or day > end:
        return "outside"
    if start == end:
        return "single"
    if day == start:
        return "start"
    if day == end:
        return "end"
    return "mid"


def in_selected_range(day: date, start: date, end: date) -> bool:
    """True, wenn der Tag im gewählten Zeitraum liegt, inklusive der Ränder."""
    return range_role(day, start, end) != "outside"


ROLE_HELP = {
    "start": "Start des gewählten Zeitraums",
    "end": "Ende des gewählten Zeitraums",
    "mid": "Liegt im gewählten Zeitraum",
    "single": "Gewählter Tag",
    "outside": "Tag in den Zeitraum aufnehmen",
}

# Drei Zustände plus Einzeltag. Die Farben bleiben im Grün der App,
# unterscheiden sich aber in Fläche, Rand und Ecken.
RANGE_STYLE = {
    "single": (
        "background:#00e699 !important;background-color:#00e699 !important;"
        "color:#06281c !important;border:2px solid #d9fff2 !important;"
        "border-radius:10px !important;box-shadow:inset 0 0 0 2px #067a52 !important;"
    ),
    "start": (
        "background:#00e699 !important;background-color:#00e699 !important;"
        "color:#06281c !important;border:2px solid #00e699 !important;"
        "border-radius:12px 4px 4px 12px !important;"
    ),
    "mid": (
        "background:rgba(0,230,153,0.28) !important;background-color:rgba(0,230,153,0.28) !important;"
        "color:#e7fff6 !important;border:1px solid #1f8f68 !important;"
        "border-radius:4px !important;box-shadow:none !important;"
    ),
    "end": (
        "background:#06281c !important;background-color:#06281c !important;"
        "color:#00e699 !important;border:2px solid #00e699 !important;"
        "border-radius:4px 12px 12px 4px !important;"
        "box-shadow:inset 0 0 0 1px #00e699 !important;"
    ),
}


def day_help(role: str, count: int) -> str:
    """Kurzer Hinweis am Tag: Zeitraumrolle und, falls vorhanden, Value-Signale."""
    parts: list[str] = []
    if count == 1:
        parts.append("1 Value-Signal")
    elif count > 1:
        parts.append(f"{count} Value-Signale")
    parts.append(ROLE_HELP[role])
    return " · ".join(parts)


def range_marks(year: int, month: int, start: date, end: date) -> dict[date, str]:
    """Tage dieses Monats, die im Zeitraum liegen, mit ihrer Rolle."""
    marks: dict[date, str] = {}
    for week in month_weeks(year, month):
        for day in week:
            if day is None:
                continue
            role = range_role(day, start, end)
            if role != "outside":
                marks[day] = role
    return marks


def selected_range_css(year: int, month: int, start: date, end: date) -> str:
    """CSS, das Start, Tage dazwischen und Ende auf den Tagesbuttons unterscheidet."""
    rules: list[str] = []
    for day, role in range_marks(year, month, start, end).items():
        iso = day.isoformat()
        selector = (
            f".st-key-day-{iso} button, "
            f".st-key-day-{iso} button:hover, "
            f".st-key-day-{iso} [data-testid^='stBaseButton'], "
            f".st-key-day-{iso} [data-testid^='stBaseButton']:hover"
        )
        rules.append(f"{selector}{{/*role:{role}*/{RANGE_STYLE[role]}}}")
    if not rules:
        return ""
    return "<style>\n" + "\n".join(rules) + "\n</style>"


def shift_month(year: int, month: int, step: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + step
    return index // 12, index % 12 + 1
