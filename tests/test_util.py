from __future__ import annotations

import pytest

from price_monitor.sources.util import (
    PriceParseError,
    parse_availability,
    parse_price,
    parse_rating,
)


@pytest.mark.parametrize(
    ("text", "amount", "currency"),
    [
        ("£51.77", 51.77, "GBP"),
        (" Â£1,234.56 ", 1234.56, "GBP"),
        ("$19.99", 19.99, "USD"),
        ("€ 7.00", 7.0, "EUR"),
        ("£0.99", 0.99, "GBP"),
    ],
)
def test_parse_price(text: str, amount: float, currency: str) -> None:
    assert parse_price(text) == (amount, currency)


@pytest.mark.parametrize("text", ["free", "", "£0.00", "12.34"])
def test_parse_price_rejects_unusable_values(text: str) -> None:
    with pytest.raises(PriceParseError):
        parse_price(text)


def test_parse_rating() -> None:
    assert parse_rating(["star-rating", "Three"]) == 3
    assert parse_rating("star-rating Five") == 5
    assert parse_rating(["star-rating", "Zero"]) is None
    assert parse_rating([]) is None


def test_parse_availability() -> None:
    assert parse_availability("  In   stock \n") == (True, "In stock")
    assert parse_availability("Out of stock") == (False, "Out of stock")
    assert parse_availability("") == (True, "")
