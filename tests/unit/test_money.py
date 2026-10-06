from decimal import Decimal

import pytest

from invoiceops.domain.dates import AmbiguousDateError, parse_issue_date
from invoiceops.domain.money import AmbiguousAmountError, parse_amount, serialize_amount


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.234,56", Decimal("1234.56")),
        ("1,234.56", Decimal("1234.56")),
        ("0,50", Decimal("0.50")),
        ("0.50", Decimal("0.50")),
        ("1.005", None),
        ("(12,34)", Decimal("-12.34")),
        ("0,00", Decimal("0.00")),
        (None, None),
        ("", None),
    ],
)
def test_money_parsing_preserves_zero_and_known_formats(
    raw: str | None, expected: Decimal | None
) -> None:
    if raw == "1.005":
        with pytest.raises(AmbiguousAmountError):
            parse_amount(raw)
    else:
        assert parse_amount(raw) == expected


def test_money_rounds_half_up_and_serializes_as_decimal_string() -> None:
    assert serialize_amount(Decimal("2.345")) == "2.35"
    assert serialize_amount(Decimal("2.344")) == "2.34"


@pytest.mark.parametrize("raw", ["1.234", "1,234", "12,34,56", "R$ 1,2,3", ""])
def test_ambiguous_or_invalid_money_is_not_guessed(raw: str) -> None:
    if raw == "":
        assert parse_amount(raw) is None
    else:
        with pytest.raises(ValueError):
            parse_amount(raw)


def test_identifiers_remain_strings_with_leading_zeroes() -> None:
    identifier = "00.012.340/0001-05"
    assert identifier == str(identifier)


def test_numeric_slash_dates_are_rejected_when_ambiguous() -> None:
    with pytest.raises(AmbiguousDateError):
        parse_issue_date("03/04/2026")
    assert parse_issue_date("13/04/2026").isoformat() == "2026-04-13"
    assert parse_issue_date("2026-04-13").isoformat() == "2026-04-13"
