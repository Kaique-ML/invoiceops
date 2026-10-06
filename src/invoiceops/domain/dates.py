from __future__ import annotations

import re
from datetime import date


class AmbiguousDateError(ValueError):
    """Raised when a numeric date has multiple plausible interpretations."""


def parse_issue_date(raw: str | None) -> date | None:
    if raw is None or not raw.strip():
        return None
    value = raw.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return date.fromisoformat(value)

    parts = value.split("/")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError("Date must be ISO YYYY-MM-DD or an unambiguous slash date")
    first, second, year = (int(part) for part in parts)
    if len(parts[2]) != 4:
        raise ValueError("Slash date must include a four-digit year")
    if first <= 12 and second <= 12 and first != second:
        raise AmbiguousDateError("Slash date could be either month/day or day/month")
    if first > 12 and second <= 12:
        day, month = first, second
    elif second > 12 and first <= 12:
        month, day = first, second
    elif first == second:
        day = month = first
    else:
        raise ValueError("Date components are out of range")
    return date(year, month, day)
