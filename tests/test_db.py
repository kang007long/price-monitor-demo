from __future__ import annotations

from price_monitor import db
from price_monitor.models import ParsedItem
from price_monitor.sources.base import SourceSpec

SPEC = SourceSpec(
    key="books",
    name="Books",
    base_url="https://books.toscrape.com/",
    start_url="https://books.toscrape.com/catalogue/page-1.html",
    robots_url="https://books.toscrape.com/robots.txt",
    license_note="sandbox",
    default_max_pages=50,
)


def make_item(external_id: str = "/catalogue/book_1/index.html") -> ParsedItem:
    return ParsedItem(
        external_id=external_id,
        title="A Book",
        url=f"https://books.toscrape.com{external_id}",
        price=10.0,
        currency="GBP",
        in_stock=True,
        stock_text="In stock",
        rating=4,
    )


def save(conn, *, batch_id, price=10.0, in_stock=True, simulated=False, item=None):
    return db.save_observation(
        conn,
        item=item or make_item(),
        source_key="books",
        batch_id=batch_id,
        price=price,
        source_price=10.0,
        currency="GBP",
        in_stock=in_stock,
        stock_text="In stock" if in_stock else "Out of stock",
        source_in_stock=True,
        source_stock_text="In stock",
        simulated=simulated,
        recorded_at="2026-11-11T06:00:00+00:00",
    )


def test_first_observation_is_new_and_has_history(conn) -> None:
    db.upsert_source(conn, SPEC)
    first = db.start_batch(
        conn,
        source_key="books",
        kind="scrape",
        mode="real",
        started_at="2026-11-11T06:00:00+00:00",
    )
    outcome = save(conn, batch_id=first)
    conn.commit()

    assert outcome.is_new is True
    assert outcome.price_changed is False
    assert outcome.stock_changed is False
    assert db.count_items(conn, "books") == 1
    assert conn.execute("SELECT COUNT(*) AS n FROM price_history").fetchone()["n"] == 1
    assert conn.execute("SELECT COUNT(*) AS n FROM stock_history").fetchone()["n"] == 1


def _setup(conn):
    db.upsert_source(conn, SPEC)
    return db.start_batch(
        conn,
        source_key="books",
        kind="scrape",
        mode="real",
        started_at="2026-11-11T06:00:00+00:00",
    )


def test_deduplicates_by_external_id_and_detects_changes(conn) -> None:
    batch = _setup(conn)
    save(conn, batch_id=batch)
    conn.commit()
    outcome = save(conn, batch_id=batch, price=9.5, in_stock=False)
    conn.commit()

    assert outcome.is_new is False
    assert outcome.price_changed is True
    assert outcome.stock_changed is True
    assert db.count_items(conn, "books") == 1
    # Re-running the same batch updates, rather than duplicating, history rows.
    assert conn.execute("SELECT COUNT(*) AS n FROM price_history").fetchone()["n"] == 1
    row = conn.execute("SELECT price, in_stock FROM items").fetchone()
    assert row["price"] == 9.5
    assert row["in_stock"] == 0


def test_same_price_does_not_count_as_change(conn) -> None:
    batch = _setup(conn)
    save(conn, batch_id=batch)
    conn.commit()
    batch2 = db.start_batch(
        conn,
        source_key="books",
        kind="scrape",
        mode="real",
        started_at="2026-11-12T06:00:00+00:00",
    )
    outcome = save(conn, batch_id=batch2, price=10.0)
    conn.commit()
    assert outcome.price_changed is False
    assert outcome.stock_changed is False


def test_quotes_without_price_are_stored_without_history(conn) -> None:
    batch = _setup(conn)
    item = ParsedItem(
        external_id="quote:abc",
        title="A quote",
        url="https://quotes.toscrape.com/author/Someone",
        price=None,
        currency=None,
        in_stock=True,
        stock_text="n/a",
    )
    db.save_observation(
        conn,
        item=item,
        source_key="books",
        batch_id=batch,
        price=None,
        source_price=None,
        currency="",
        in_stock=True,
        stock_text="n/a",
        source_in_stock=True,
        source_stock_text="n/a",
        simulated=False,
        recorded_at="2026-11-11T06:00:00+00:00",
    )
    conn.commit()
    assert conn.execute("SELECT COUNT(*) AS n FROM price_history").fetchone()["n"] == 0


def test_stale_running_batches_are_failed(conn) -> None:
    batch = _setup(conn)
    assert batch > 0
    changed = db.mark_stale_running(
        conn,
        before_iso="2026-11-11T07:00:00+00:00",
        now_iso="2026-11-11T09:00:00+00:00",
    )
    assert changed == 1
    row = conn.execute("SELECT status, finished_at, notes FROM batches").fetchone()
    assert row["status"] == "failed"
    assert row["finished_at"] == "2026-11-11T09:00:00+00:00"
    assert "interrupted" in row["notes"]
