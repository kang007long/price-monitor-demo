from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import httpx
import pytest

from price_monitor import db, pipeline
from price_monitor.http import PoliteClient
from price_monitor.sources.books import BooksAdapter

from tests.helpers import read_fixture

NOW = datetime(2026, 11, 11, 6, 0, tzinfo=timezone.utc)
PAGE_1 = read_fixture("books-page-1.html")
PAGE_2 = read_fixture("books-page-2.html")


def make_client(handler) -> PoliteClient:
    return PoliteClient(
        transport=httpx.MockTransport(handler),
        min_interval=0,
        max_retries=0,
        sleep=lambda _seconds: None,
        clock=lambda: 0.0,
    )


def site(handler, *, page_1=PAGE_1, page_2=PAGE_2):
    def wrapped(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404, request=request)
        if request.url.path == "/catalogue/page-1.html":
            return httpx.Response(200, text=page_1, request=request)
        if request.url.path == "/catalogue/page-2.html":
            return httpx.Response(200, text=page_2, request=request)
        raise AssertionError(f"unexpected request: {request.url}")

    return make_client(wrapped)


def test_two_page_simulated_run_with_backfill(conn) -> None:
    summary = pipeline.run_scrape(
        conn,
        BooksAdapter(),
        site(None),
        max_pages=2,
        simulate=True,
        ensure_history=3,
        now=NOW,
    )

    assert summary.status == "success"
    assert summary.pages_fetched == 2
    assert summary.items_seen == 40
    assert summary.items_new == 40
    assert summary.backfilled_days == 2
    assert summary.simulated is True
    assert db.count_items(conn, "books") == 40
    assert db.count_batches(conn, "books", kind="scrape") == 1
    assert db.count_batches(conn, "books", kind="backfill") == 2

    history_count = conn.execute("SELECT COUNT(*) AS n FROM price_history").fetchone()["n"]
    assert history_count == 40 * 3
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM price_history WHERE simulated = 1"
    ).fetchone()["n"] == history_count
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM price_history WHERE price < source_price * 0.8 "
        "OR price > source_price * 1.2"
    ).fetchone()["n"] == 0

    batch_rows = conn.execute(
        "SELECT status, kind FROM batches ORDER BY id"
    ).fetchall()
    assert [row["status"] for row in batch_rows] == ["success", "success", "success"]
    assert [row["kind"] for row in batch_rows] == ["scrape", "backfill", "backfill"]


def test_rerun_on_same_day_does_not_duplicate_items_or_backfill(conn) -> None:
    pipeline.run_scrape(
        conn,
        BooksAdapter(),
        site(None),
        max_pages=2,
        simulate=True,
        ensure_history=3,
        now=NOW,
    )
    first_price = conn.execute(
        "SELECT price FROM items ORDER BY id LIMIT 1"
    ).fetchone()["price"]
    second = pipeline.run_scrape(
        conn,
        BooksAdapter(),
        site(None),
        max_pages=2,
        simulate=True,
        ensure_history=3,
        now=NOW,
    )
    second_price = conn.execute(
        "SELECT price FROM items ORDER BY id LIMIT 1"
    ).fetchone()["price"]

    assert second.backfilled_days == 0
    assert db.count_items(conn, "books") == 40
    assert first_price == second_price
    assert db.count_batches(conn, "books", kind="backfill") == 2


def test_later_page_failure_marks_partial_and_keeps_first_page(conn) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404, request=request)
        if request.url.path == "/catalogue/page-1.html":
            return httpx.Response(200, text=PAGE_1, request=request)
        return httpx.Response(503, request=request)

    summary = pipeline.run_scrape(
        conn, BooksAdapter(), make_client(handler), max_pages=2, now=NOW
    )

    assert summary.status == "partial"
    assert summary.pages_fetched == 1
    assert summary.items_seen == 20
    assert summary.errors == 1
    assert db.count_items(conn, "books") == 20
    batch = conn.execute("SELECT status, error_count FROM batches").fetchone()
    assert batch["status"] == "partial"
    assert batch["error_count"] == 1
    error = conn.execute("SELECT kind FROM scrape_errors").fetchone()
    assert error["kind"] == "fetch"


def test_robots_denial_marks_failed_and_stores_nothing(conn) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nDisallow: /catalogue\n",
                request=request,
            )
        raise AssertionError("page must not be requested when robots disallows it")

    summary = pipeline.run_scrape(conn, BooksAdapter(), make_client(handler), now=NOW)

    assert summary.status == "failed"
    assert summary.pages_fetched == 0
    assert summary.items_seen == 0
    assert db.count_items(conn, "books") == 0
    assert conn.execute("SELECT kind FROM scrape_errors").fetchone()["kind"] == "robots"


def test_duplicate_cards_across_pages_are_deduplicated(conn) -> None:
    summary = pipeline.run_scrape(
        conn,
        BooksAdapter(),
        site(None, page_2=PAGE_1),
        max_pages=2,
        now=NOW,
    )
    assert summary.status == "success"
    assert summary.items_seen == 20
    assert summary.items_new == 20
    assert db.count_items(conn, "books") == 20


def test_real_mode_stores_source_price_and_no_simulation(conn) -> None:
    summary = pipeline.run_scrape(
        conn, BooksAdapter(), site(None), max_pages=2, simulate=False, now=NOW
    )
    assert summary.status == "success"
    rows = conn.execute(
        "SELECT i.price, i.source_price, i.in_stock, ph.simulated "
        "FROM items i JOIN price_history ph ON ph.item_id = i.id"
    ).fetchall()
    assert rows
    for row in rows:
        assert row["price"] == row["source_price"]
        assert row["in_stock"] == 1
        assert row["simulated"] == 0


def test_ensure_history_requires_simulation(conn) -> None:
    with pytest.raises(ValueError, match="requires simulate"):
        pipeline.run_scrape(
            conn,
            BooksAdapter(),
            site(None),
            max_pages=1,
            simulate=False,
            ensure_history=3,
            now=NOW,
        )
    assert conn.execute("SELECT COUNT(*) AS n FROM batches").fetchone()["n"] == 0


def test_parse_failure_marks_batch_failed(conn) -> None:
    summary = pipeline.run_scrape(
        conn,
        BooksAdapter(),
        site(None, page_1="<html><body>maintenance</body></html>"),
        max_pages=1,
        now=NOW,
    )
    assert summary.status == "failed"
    assert summary.pages_fetched == 0
    assert conn.execute("SELECT kind FROM scrape_errors").fetchone()["kind"] == "parse"


def test_backfill_does_not_change_current_state(conn) -> None:
    pipeline.run_scrape(
        conn,
        BooksAdapter(),
        site(None),
        max_pages=1,
        simulate=True,
        ensure_history=4,
        now=NOW,
    )
    before = conn.execute(
        "SELECT id, price, last_seen_at FROM items ORDER BY id LIMIT 1"
    ).fetchone()
    pipeline.backfill_demo_history(conn, source_key="books", days=6, now=NOW)
    after = conn.execute(
        "SELECT id, price, last_seen_at FROM items ORDER BY id LIMIT 1"
    ).fetchone()
    assert dict(before) == dict(after)


def test_a_failed_page_is_skipped_when_pagination_allows(conn) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404, request=request)
        if request.url.path == "/catalogue/page-1.html":
            return httpx.Response(200, text=PAGE_1, request=request)
        if request.url.path == "/catalogue/page-2.html":
            return httpx.Response(503, request=request)
        if request.url.path == "/catalogue/page-3.html":
            return httpx.Response(200, text=PAGE_2, request=request)
        raise AssertionError(f"unexpected request: {request.url}")

    summary = pipeline.run_scrape(
        conn, BooksAdapter(), make_client(handler), max_pages=3, now=NOW
    )

    assert summary.status == "partial"
    assert summary.pages_fetched == 2
    assert summary.items_seen == 40
    assert summary.errors == 1
    assert db.count_items(conn, "books") == 40
    assert [row["url"] for row in conn.execute("SELECT url FROM scrape_errors")] == [
        "https://books.toscrape.com/catalogue/page-2.html"
    ]


def test_a_404_page_is_skipped(conn) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404, request=request)
        if request.url.path == "/catalogue/page-1.html":
            return httpx.Response(200, text=PAGE_1, request=request)
        if request.url.path == "/catalogue/page-2.html":
            return httpx.Response(404, request=request)
        if request.url.path == "/catalogue/page-3.html":
            return httpx.Response(200, text=PAGE_2, request=request)
        raise AssertionError(f"unexpected request: {request.url}")

    summary = pipeline.run_scrape(
        conn, BooksAdapter(), make_client(handler), max_pages=3, now=NOW
    )
    assert summary.status == "partial"
    assert summary.pages_fetched == 2
    assert summary.items_seen == 40
    assert summary.errors == 1


def test_three_consecutive_bad_pages_then_recovery(conn) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404, request=request)
        if request.url.path == "/catalogue/page-1.html":
            return httpx.Response(200, text=PAGE_1, request=request)
        if request.url.path in {
            "/catalogue/page-2.html",
            "/catalogue/page-3.html",
            "/catalogue/page-4.html",
        }:
            return httpx.Response(503, request=request)
        if request.url.path == "/catalogue/page-5.html":
            return httpx.Response(200, text=PAGE_2, request=request)
        raise AssertionError(f"unexpected request: {request.url}")

    summary = pipeline.run_scrape(
        conn, BooksAdapter(), make_client(handler), max_pages=5, now=NOW
    )
    assert summary.status == "partial"
    assert summary.pages_fetched == 2
    assert summary.items_seen == 40
    assert summary.errors == 3


def test_same_day_rerun_keeps_the_days_simulated_price(conn) -> None:
    day_one = datetime(2026, 11, 10, 6, 0, tzinfo=timezone.utc)
    day_two = datetime(2026, 11, 11, 6, 0, tzinfo=timezone.utc)

    pipeline.run_scrape(
        conn, BooksAdapter(), site(None), max_pages=1, simulate=True, now=day_one
    )
    first = conn.execute(
        "SELECT id, price FROM items ORDER BY id LIMIT 1"
    ).fetchone()
    pipeline.run_scrape(
        conn, BooksAdapter(), site(None), max_pages=1, simulate=True, now=day_two
    )
    second = conn.execute(
        "SELECT id, price FROM items ORDER BY id LIMIT 1"
    ).fetchone()
    assert second["price"] != first["price"]

    summary = pipeline.run_scrape(
        conn, BooksAdapter(), site(None), max_pages=1, simulate=True, now=day_two
    )
    third = conn.execute(
        "SELECT id, price FROM items ORDER BY id LIMIT 1"
    ).fetchone()
    assert third["price"] == second["price"]
    assert summary.items_updated == 20

    same_day_prices = conn.execute(
        "SELECT ph.price FROM price_history ph "
        "WHERE ph.item_id = ? AND substr(ph.recorded_at, 1, 10) = '2026-11-11'",
        (second["id"],),
    ).fetchall()
    assert len(same_day_prices) == 2
    assert {row["price"] for row in same_day_prices} == {second["price"]}


def test_pipeline_uses_the_adapters_robots_url(conn) -> None:
    adapter = BooksAdapter()
    adapter.spec = replace(
        adapter.spec,
        robots_url="https://books.toscrape.com/custom-robots.txt",
    )

    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == "/custom-robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nDisallow: /catalogue\n",
                request=request,
            )
        raise AssertionError(f"unexpected request: {request.url}")

    summary = pipeline.run_scrape(
        conn, adapter, make_client(handler), now=NOW
    )
    assert summary.status == "failed"
    assert summary.items_seen == 0
    assert seen == ["/custom-robots.txt"]


def _pages(statuses: dict[int, object]):
    """Fake books site: page N returns statuses[N] (int status, or "bad" for unparseable HTML)."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404, request=request)
        name = request.url.path.rsplit("/", 1)[-1]
        if name.startswith("page-") and name.endswith(".html"):
            n = int(name[len("page-") : -len(".html")])
            what = statuses.get(n, 200)
            if what == "bad":
                return httpx.Response(200, text="<html><body>nothing here</body></html>", request=request)
            if what != 200:
                return httpx.Response(int(what), request=request)
            return httpx.Response(200, text=PAGE_1 if n == 1 else PAGE_2, request=request)
        raise AssertionError(f"unexpected request: {request.url}")

    return handler


def test_parse_failure_is_skipped_and_the_round_continues(conn) -> None:
    requested: list[str] = []
    inner = _pages({2: "bad"})

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        return inner(request)

    summary = pipeline.run_scrape(conn, BooksAdapter(), make_client(handler), max_pages=3, now=NOW)
    assert summary.status == "partial"
    assert "/catalogue/page-3.html" in requested, "page 3 must still be fetched after page 2 failed to parse"
    assert summary.pages_fetched == 2
    kinds = [row["kind"] for row in conn.execute("SELECT kind FROM scrape_errors")]
    assert kinds == ["parse"]


def test_consecutive_404s_recover_like_other_failures(conn) -> None:
    requested: list[str] = []
    inner = _pages({2: 404, 3: 404})

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        return inner(request)

    summary = pipeline.run_scrape(conn, BooksAdapter(), make_client(handler), max_pages=4, now=NOW)
    assert "/catalogue/page-4.html" in requested
    assert summary.pages_fetched == 2
    assert summary.errors == 2


def test_stops_after_five_failures_in_a_row_mixing_fetch_and_parse(conn) -> None:
    requested: list[str] = []
    inner = _pages({2: 404, 3: "bad", 4: 503, 5: "bad", 6: 410})

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        return inner(request)

    summary = pipeline.run_scrape(conn, BooksAdapter(), make_client(handler), max_pages=10, now=NOW)
    assert "/catalogue/page-6.html" in requested
    assert "/catalogue/page-7.html" not in requested, "five failures in a row ends the source"
    assert summary.errors == 5
