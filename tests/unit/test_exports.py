from decimal import Decimal

import pytest

from invoiceops.domain.exports import export_cell, safe_export_text


@pytest.mark.parametrize("prefix", ["=", "+", "-", "@", "\t", "\r", "\n"])
def test_formula_like_text_is_neutralized(prefix: str) -> None:
    assert safe_export_text(prefix + "SUM(A1:A2)") == "'" + prefix + "SUM(A1:A2)"


def test_numbers_and_missing_text_keep_their_types() -> None:
    assert export_cell(Decimal("-12.30")) == Decimal("-12.30")
    assert isinstance(export_cell(Decimal("-12.30")), Decimal)
    assert safe_export_text(None) is None
    assert safe_export_text("Cafe Aurora") == "Cafe Aurora"
