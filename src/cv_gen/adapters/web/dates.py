"""Parsing the date ranges people write on web pages into ISO partial dates.

Handles what "about" pages and timelines actually say: ``2022``, ``2021–``,
``2013–2019``, ``Jan 2020 - present``, ``2006–2007, 2010–2013``. Every date comes out
in the model's ISO form (``2020`` or ``2020-01``).
"""

from __future__ import annotations

import re
from typing import Any

MONTHS = {
    name: index
    for index, names in enumerate(
        [
            ("jan", "january"),
            ("feb", "february"),
            ("mar", "march"),
            ("apr", "april"),
            ("may",),
            ("jun", "june"),
            ("jul", "july"),
            ("aug", "august"),
            ("sep", "sept", "september"),
            ("oct", "october"),
            ("nov", "november"),
            ("dec", "december"),
        ],
        start=1,
    )
    for name in names
}

# Month alternatives restrict "YYYY-MM" to real months, so "2006-2007" can only be read
# as a range of two years, never as a year and month "20".
_ISO = r"\d{4}(?:-(?:0[1-9]|1[0-2])(?:-(?:0[1-9]|[12]\d|3[01]))?)?"
_NAMED = r"[A-Za-z]{3,9}\.?\s+\d{4}"
_NUMERIC = r"(?:0?[1-9]|1[0-2])/\d{4}"
_DATE = rf"(?:{_ISO}|{_NAMED}|{_NUMERIC})"
_OPEN = r"(?:present|now|current|today|ongoing)"
_SEPARATOR = r"(?:–|—|-|\bto\b|\buntil\b|\bthrough\b)"
_PERIOD = re.compile(
    rf"^\s*(?P<start>{_DATE})\s*(?:(?P<sep>{_SEPARATOR})\s*(?P<end>{_DATE}|{_OPEN})?)?\s*$",
    re.IGNORECASE,
)


def to_iso(text: str) -> str:
    """Convert one written date (``2021``, ``2021-04``, ``Apr 2021``, ``4/2021``) to ISO."""
    text = text.strip()
    if re.fullmatch(_ISO, text):
        return text
    if match := re.fullmatch(r"([A-Za-z]{3,9})\.?\s+(\d{4})", text):
        month = MONTHS.get(match.group(1).lower())
        if month is None:
            raise ValueError(f"unknown month in {text!r}")
        return f"{match.group(2)}-{month:02d}"
    if match := re.fullmatch(r"(\d{1,2})/(\d{4})", text):
        return f"{match.group(2)}-{int(match.group(1)):02d}"
    raise ValueError(f"cannot read {text!r} as a date")


def parse_period(text: str) -> dict[str, str]:
    """Parse one range: ``2013–2019``, ``2021–`` (open), ``2022`` (that year only)."""
    match = _PERIOD.match(text)
    if not match:
        raise ValueError(f"cannot read {text!r} as a date range")
    start = to_iso(match.group("start"))
    end_text = match.group("end")
    if match.group("sep") is None:
        return {"startDate": start, "endDate": start}
    if end_text is None or re.fullmatch(_OPEN, end_text, re.IGNORECASE):
        return {"startDate": start}
    return {"startDate": start, "endDate": to_iso(end_text)}


def parse_date_range(text: str) -> dict[str, Any]:
    """Parse one or more comma- or semicolon-separated ranges.

    Returns ``startDate`` (the first period's start), ``endDate`` (the last period's
    end, absent when it is open) and, when there is more than one period, ``periods``.
    """
    parts = [part for part in re.split(r"[,;]", text) if part.strip()]
    if not parts:
        raise ValueError("empty date range")
    periods = [parse_period(part) for part in parts]
    result: dict[str, Any] = {"startDate": periods[0]["startDate"]}
    if "endDate" in periods[-1]:
        result["endDate"] = periods[-1]["endDate"]
    if len(periods) > 1:
        result["periods"] = periods
    return result
