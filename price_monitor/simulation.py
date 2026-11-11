"""Deterministic, clearly-labelled simulation for the demo.

The practice sites never change their prices, so a price *trend* would be a flat
line. This module produces synthetic movement that is:

* deterministic (same item + day -> same price, so reruns are reproducible),
* bounded to +/-20% of the real scraped price,
* always flagged as simulated in the database and in the UI.

It never changes the scraped ``source_price``; that value is preserved for
comparison on the chart and in exports.
"""

from __future__ import annotations

import hashlib
import random

from price_monitor import config


def _rng(key: str, day: str, salt: str = "") -> random.Random:
    digest = hashlib.sha256(f"{salt}|{key}|{day}".encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))


def simulate_price(
    source_price: float,
    previous_price: float | None,
    key: str,
    day: str,
    *,
    max_drift: float = config.SIMULATION_MAX_DRIFT,
    sigma: float = config.SIMULATION_DAILY_SIGMA,
) -> float:
    """One step of a bounded, mean-reverting random walk."""

    if source_price <= 0:
        raise ValueError("source_price must be positive")
    anchor = previous_price if previous_price and previous_price > 0 else source_price
    rng = _rng(key, day)
    noise = rng.gauss(0, sigma)
    # Pull back toward the real price so long walks do not drift to a bound.
    reversion = ((source_price - anchor) / source_price) * 0.12
    candidate = anchor * (1.0 + noise + reversion)

    low = source_price * (1.0 - max_drift)
    high = source_price * (1.0 + max_drift)
    price = round(min(max(candidate, low), high), 2)

    if previous_price is not None and abs(price - previous_price) < 0.01:
        nudge = 0.01 if rng.random() < 0.5 else -0.01
        price = round(min(max(price + nudge, low), high), 2)
    return max(0.01, price)


def simulate_stock(
    real_in_stock: bool,
    key: str,
    day: str,
    *,
    probability: float = config.SIMULATION_STOCK_PROBABILITY,
) -> tuple[bool, str]:
    """Occasionally mark an in-stock title as unavailable (clearly labelled)."""

    if not real_in_stock:
        return False, "Out of stock (reported)"
    if _rng(key, day, salt="stock").random() < probability:
        return False, "Out of stock (simulated)"
    return True, "In stock"


def backfill_prices(
    *,
    current_price: float,
    source_price: float,
    key: str,
    dates: list[str],
) -> dict[str, float]:
    """Generate history for ``dates`` (oldest last), anchored to today's price.

    Walking backwards keeps the synthetic history continuous with the latest
    observation instead of producing a jump at the end of the chart.
    """

    prices: dict[str, float] = {}
    previous = current_price
    for day in sorted(dates, reverse=True):
        price = simulate_price(source_price, previous, key, day)
        prices[day] = price
        previous = price
    return prices
