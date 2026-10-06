from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENT = Decimal("0.01")
SUPPORTED_CURRENCIES = frozenset({"BRL", "USD", "EUR"})


class AmbiguousAmountError(ValueError):
    """Raised when punctuation does not determine one monetary value."""


def parse_amount(raw: str | None) -> Decimal | None:
    if raw is None or not raw.strip():
        return None

    value = re.sub(r"[\s\u00a0]", "", raw).replace("R$", "").replace("$", "").replace("€", "")
    if value.startswith("(") and value.endswith(")"):
        value = f"-{value[1:-1]}"
    if value in {"-", "+", ".", ","}:
        raise ValueError("Amount does not contain digits")
    if not re.fullmatch(r"[+-]?\d[\d.,]*", value):
        raise ValueError("Amount contains unsupported characters")

    body = value.lstrip("+-")
    comma_count = body.count(",")
    dot_count = body.count(".")

    if comma_count and dot_count:
        decimal_mark = "," if body.rfind(",") > body.rfind(".") else "."
        grouping_mark = "." if decimal_mark == "," else ","
        integer, fraction = body.rsplit(decimal_mark, 1)
        if not fraction.isdigit() or not 1 <= len(fraction) <= 2:
            raise AmbiguousAmountError("Amount separators are not unambiguous")
        groups = integer.replace("+", "").replace("-", "").split(grouping_mark)
        if not _valid_integer_groups(groups):
            raise AmbiguousAmountError("Grouping separators are not valid")
        normalized = "".join(groups) + "." + fraction
    elif comma_count or dot_count:
        mark = "," if comma_count else "."
        parts = body.split(mark)
        if len(parts) == 2:
            integer, fraction = parts
            if not integer.isdigit() or not fraction.isdigit():
                raise ValueError("Amount is not a valid decimal")
            if len(fraction) == 3:
                raise AmbiguousAmountError("A single three-digit separator is ambiguous")
            if len(fraction) not in {1, 2}:
                raise AmbiguousAmountError("Amount precision is unsupported")
            normalized = integer + "." + fraction
        elif _valid_integer_groups(parts):
            normalized = "".join(parts)
        else:
            raise AmbiguousAmountError("Grouping separators are not valid")
    else:
        normalized = body

    if value.startswith("-"):
        normalized = "-" + normalized
    try:
        amount = Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError("Amount is not a valid decimal") from exc
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def _valid_integer_groups(groups: list[str]) -> bool:
    return (
        len(groups) > 1
        and groups[0].isdigit()
        and 1 <= len(groups[0]) <= 3
        and all(part.isdigit() and len(part) == 3 for part in groups[1:])
    )


def serialize_amount(amount: Decimal | None) -> str | None:
    if amount is None:
        return None
    return str(amount.quantize(CENT, rounding=ROUND_HALF_UP))
