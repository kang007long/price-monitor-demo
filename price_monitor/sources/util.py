"""Parsing helpers shared by site adapters."""

from __future__ import annotations

import re

_PRICE_RE = re.compile(
    r"(?P<symbol>[£$€])\s*(?P<amount>\d[\d,]*(?:\.\d{1,2})?)"
)
_CURRENCY_BY_SYMBOL = {"£": "GBP", "$": "USD", "€": "EUR"}

_RATING_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
}

# Some archived copies of the practice site served UTF-8 as Latin-1 (``Â£``).
_MOJIBAKE = (("Â£", "£"), ("Â€", "€"), ("Â$", "$"))


class PriceParseError(ValueError):
    pass


def parse_price(text: str) -> tuple[float, str]:
    """Return ``(amount, ISO currency)`` from text like ``£51.77``.

    Handles the mojibake form (``Â£51.77``) that old mirrors produced, thousands
    separators, and non-breaking spaces. Raises ``PriceParseError`` otherwise so
    the caller can record a parser warning instead of silently storing zero.
    """

    if text is None:
        raise PriceParseError("missing price text")
    cleaned = text.replace("\xa0", " ").strip()
    for broken, fixed in _MOJIBAKE:
        cleaned = cleaned.replace(broken, fixed)
    match = _PRICE_RE.search(cleaned)
    if not match:
        raise PriceParseError(f"unrecognised price: {text!r}")
    amount = float(match.group("amount").replace(",", ""))
    if amount <= 0:
        raise PriceParseError(f"non-positive price: {text!r}")
    return round(amount, 2), _CURRENCY_BY_SYMBOL[match.group("symbol")]


def parse_rating(class_names: list[str] | str) -> int | None:
    """Map a ``star-rating Three`` class to 3; unknown ratings become ``None``."""

    names = class_names.split() if isinstance(class_names, str) else class_names
    for name in names:
        value = _RATING_WORDS.get(name.lower())
        if value is not None:
            return value
    return None


def collapse_whitespace(text: str) -> str:
    return " ".join((text or "").split())


def parse_availability(text: str) -> tuple[bool, str]:
    label = collapse_whitespace(text)
    lowered = label.lower()
    if not label:
        return True, ""
    in_stock = "out of stock" not in lowered
    return in_stock, label
