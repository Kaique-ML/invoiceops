from __future__ import annotations

from decimal import Decimal
from typing import Any


def safe_export_text(value: str | None) -> str | None:
    if value is None:
        return None
    probe = value.lstrip(" \t\r\n")
    if value.startswith(("\t", "\r", "\n")) or probe.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def export_cell(value: Any) -> Any:
    if isinstance(value, str):
        return safe_export_text(value)
    if isinstance(value, Decimal):
        return value
    return value
