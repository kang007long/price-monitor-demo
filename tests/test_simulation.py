from __future__ import annotations

from price_monitor.simulation import backfill_prices, simulate_price, simulate_stock


def test_simulation_is_deterministic() -> None:
    first = simulate_price(10.0, 9.8, "book-1", "2026-11-11")
    second = simulate_price(10.0, 9.8, "book-1", "2026-11-11")
    assert first == second
    assert first != simulate_price(10.0, 9.8, "book-2", "2026-11-11")


def test_simulation_stays_within_bounds() -> None:
    previous = 10.0
    for day in range(1, 365):
        price = simulate_price(10.0, previous, "book-1", f"2026-{day:03d}")
        assert 8.0 <= price <= 12.0
        assert price > 0
        previous = price


def test_simulation_always_moves_from_previous_price() -> None:
    price = simulate_price(10.0, 10.0, "book-1", "2026-11-11")
    assert price != 10.0


def test_simulation_rejects_invalid_source_price() -> None:
    try:
        simulate_price(0, None, "book-1", "2026-11-11")
    except ValueError as exc:
        assert "positive" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def test_backfill_is_anchored_and_covers_all_dates() -> None:
    dates = ["2026-11-08", "2026-11-09", "2026-11-10"]
    prices = backfill_prices(
        current_price=10.5, source_price=10.0, key="book-1", dates=dates
    )
    assert sorted(prices) == dates
    assert all(8.0 <= value <= 12.0 for value in prices.values())


def test_stock_simulation_rules() -> None:
    assert simulate_stock(False, "book-1", "2026-11-11") == (
        False,
        "Out of stock (reported)",
    )
    assert simulate_stock(True, "book-1", "2026-11-11", probability=0.0) == (
        True,
        "In stock",
    )
    assert simulate_stock(True, "book-1", "2026-11-11", probability=1.0) == (
        False,
        "Out of stock (simulated)",
    )
