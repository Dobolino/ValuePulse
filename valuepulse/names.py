"""Gleicht Teamnamen aus zwei APIs aneinander an.

Football-Data schreibt „FC Bayern München“, die Odds-API oft „Bayern Munich“.
Wir falten Akzente, streichen Vereinszusätze und gleiche Spitznamen an.
"""

from __future__ import annotations

import re
import unicodedata

_STOP = {
    "fc",
    "afc",
    "cf",
    "sc",
    "ac",
    "as",
    "ss",
    "sv",
    "tsg",
    "vfl",
    "vfb",
    "bsc",
    "rcd",
    "cd",
    "ud",
    "ca",
    "fk",
    "sk",
    "fsv",
    "osc",
    "ogc",
    "losc",
    "rc",
    "ssc",
    "acf",
    "bc",
    "club",
    "de",
    "the",
    "and",
    "calcio",
}

# Längere Ausdrücke zuerst, damit „manchester united“ nicht zu „manchester“ zerfällt.
_PHRASES = (
    ("wolverhampton wanderers", "wolves"),
    ("wolverhampton", "wolves"),
    ("tottenham hotspur", "tottenham"),
    ("bayern munich", "bayern munchen"),
    ("internazionale milano", "inter"),
    ("inter milan", "inter"),
    ("internazionale", "inter"),
    ("ac milan", "milan"),
    ("athletic bilbao", "athletic"),
    ("athletic club", "athletic"),
    ("paris saint germain", "psg"),
    ("paris saint-germain", "psg"),
    ("paris sg", "psg"),
    ("manchester united", "man utd"),
    ("manchester utd", "man utd"),
    ("man united", "man utd"),
    ("manchester city", "man city"),
    ("nottingham forest", "nottm forest"),
    ("nottm forest", "nottm forest"),
    ("rasenballsport leipzig", "rb leipzig"),
    ("rasen ballsport leipzig", "rb leipzig"),
    ("olympique marseille", "marseille"),
    ("olympique lyon", "lyon"),
    ("olympique lyonnais", "lyon"),
    ("sporting lisbon", "sporting cp"),
    ("sporting lisboa", "sporting cp"),
)


def fold(text: str) -> str:
    """Kleinschreibung, ohne Akzente, Bindestriche werden Leerzeichen."""
    normalized = unicodedata.normalize("NFKD", text)
    without_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    lowered = without_marks.lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", " ", lowered).strip()


def canonical(name: str) -> str:
    text = fold(name)
    for source, target in _PHRASES:
        text = text.replace(source, target)
    tokens = [tok for tok in text.split() if tok not in _STOP and not tok.isdigit()]
    if not tokens:
        tokens = [tok for tok in text.split() if tok not in _STOP] or text.split()
    return " ".join(tokens)


def similarity(left: str, right: str) -> float:
    a = set(canonical(left).split())
    b = set(canonical(right).split())
    if not a or not b:
        return 0.0
    if a == b or canonical(left) == canonical(right):
        return 1.0
    return len(a & b) / len(a | b)


def names_match(left: str, right: str, threshold: float = 0.6) -> bool:
    if canonical(left) == canonical(right):
        return True
    return similarity(left, right) >= threshold
