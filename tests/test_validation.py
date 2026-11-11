from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services.errors import ValidationError
from app.services.holdings import (
    validate_positive_decimal,
    validate_purchase_date,
    validate_ticker,
)


def test_lowercase_ticker_is_uppercased() -> None:
    assert validate_ticker("aapl") == "AAPL"


def test_invalid_ticker_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_ticker("!!")
    assert exc.value.field == "ticker"


def test_zero_quantity_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_positive_decimal("0", field="quantity", label="Quantity")
    assert exc.value.field == "quantity"


def test_negative_quantity_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_positive_decimal("-1", field="quantity", label="Quantity")
    assert exc.value.field == "quantity"


def test_nan_quantity_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_positive_decimal("NaN", field="quantity", label="Quantity")
    assert exc.value.field == "quantity"


def test_infinity_quantity_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_positive_decimal("Infinity", field="quantity", label="Quantity")
    assert exc.value.field == "quantity"


def test_nine_decimal_places_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_positive_decimal(
            "1.123456789", field="quantity", label="Quantity"
        )
    assert "decimal places" in exc.value.message


def test_too_large_value_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_positive_decimal(
            "1000000000000", field="quantity", label="Quantity"
        )
    assert exc.value.message == "Quantity is too large."


def test_future_purchase_date_rejected() -> None:
    future = date.today() + timedelta(days=1)
    with pytest.raises(ValidationError) as exc:
        validate_purchase_date(future)
    assert exc.value.field == "purchase_date"
