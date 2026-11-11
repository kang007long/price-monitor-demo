"""Batch orchestration: crawl a source, store observations, generate demo history."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from price_monitor import db
from price_monitor.http import FetchError, PoliteClient, RobotsDenied
from price_monitor.models import ParseError
from price_monitor.simulation import backfill_prices, simulate_price, simulate_stock
from price_monitor.sources.base import SiteAdapter

logger = logging.getLogger(__name__)

# Stop skipping after a run of bad pages. This keeps a broken source from being
# hammered for all 50 page slots while still surviving isolated/several failures.
MAX_CONSECUTIVE_PAGE_FAILURES = 5


@dataclass(slots=True)
class ScrapeSummary:
    batch_id: int
    source_key: str
    status: str
    pages_fetched: int
    items_seen: int
    items_new: int
    items_updated: int
    price_changes: int
    stock_changes: int
    errors: int
    simulated: bool
    backfilled_days: int
    started_at: str
    finished_at: str


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def run_scrape(
    conn,
    adapter: SiteAdapter,
    client: PoliteClient,
    *,
    max_pages: int | None = None,
    simulate: bool = False,
    ensure_history: int = 0,
    now: datetime | None = None,
    finished_at: datetime | None = None,
    notes: str | None = None,
    progress: Callable[[str], None] | None = None,
) -> ScrapeSummary:
    """Run one scrape batch, always leaving a batch row behind.

    A failed page never aborts the whole run: earlier pages stay stored, the
    error is recorded, and the batch is marked ``partial``. If no page could be
    fetched the batch is marked ``failed``.
    """

    if ensure_history and not simulate:
        raise ValueError("ensure_history requires simulate=True")
    if ensure_history < 0:
        raise ValueError("ensure_history must be >= 0")
    if max_pages is not None and max_pages < 1:
        raise ValueError("max_pages must be >= 1")

    spec = adapter.spec
    started = now or utc_now()
    started_at = _iso(started)
    db.upsert_source(conn, spec)
    conn.commit()
    client.register_robots(spec.robots_url)

    mode = "simulated" if simulate else "real"
    batch_id = db.start_batch(
        conn, source_key=spec.key, kind="scrape", mode=mode, started_at=started_at, notes=notes
    )

    counters = {
        "pages": 0,
        "items_seen": 0,
        "items_new": 0,
        "items_updated": 0,
        "price_changes": 0,
        "stock_changes": 0,
        "errors": 0,
    }
    seen_external: set[str] = set()
    seen_pages: set[str] = set()
    status = "running"

    try:
        status = _crawl(
            conn,
            adapter,
            client,
            batch_id=batch_id,
            simulate=simulate,
            max_pages=max_pages,
            now=started,
            counters=counters,
            seen_external=seen_external,
            seen_pages=seen_pages,
            progress=progress,
        )
    except Exception as exc:  # pragma: no cover - defensive; tests cover known paths
        logger.exception("unexpected scrape failure")
        db.record_error(
            conn,
            batch_id=batch_id,
            url=spec.start_url,
            kind="unexpected",
            message=f"{type(exc).__name__}: {exc}",
            occurred_at=_iso(started),
        )
        counters["errors"] += 1
        status = "failed"

    finished = finished_at or utc_now()
    finished_iso = _iso(finished)
    db.finish_batch(
        conn,
        batch_id,
        status=status,
        finished_at=finished_iso,
        pages_fetched=counters["pages"],
        items_seen=counters["items_seen"],
        items_new=counters["items_new"],
        items_updated=counters["items_updated"],
        price_changes=counters["price_changes"],
        stock_changes=counters["stock_changes"],
        error_count=counters["errors"],
    )

    backfilled = 0
    if ensure_history and status != "failed" and counters["items_seen"] > 0:
        backfilled = backfill_demo_history(
            conn,
            source_key=spec.key,
            days=ensure_history,
            now=started,
            progress=progress,
        )

    summary = ScrapeSummary(
        batch_id=batch_id,
        source_key=spec.key,
        status=status,
        pages_fetched=counters["pages"],
        items_seen=counters["items_seen"],
        items_new=counters["items_new"],
        items_updated=counters["items_updated"],
        price_changes=counters["price_changes"],
        stock_changes=counters["stock_changes"],
        errors=counters["errors"],
        simulated=simulate,
        backfilled_days=backfilled,
        started_at=started_at,
        finished_at=finished_iso,
    )
    return summary


def _crawl(
    conn,
    adapter: SiteAdapter,
    client: PoliteClient,
    *,
    batch_id: int,
    simulate: bool,
    max_pages: int | None,
    now: datetime,
    counters: dict[str, int],
    seen_external: set[str],
    seen_pages: set[str],
    progress: Callable[[str], None] | None,
) -> str:
    spec = adapter.spec
    day = now.date().isoformat()
    limit = max_pages if max_pages is not None else spec.default_max_pages
    if limit < 1:
        raise ValueError("max_pages must be >= 1")
    url: str | None = spec.start_url
    page_number = 0
    consecutive_failures = 0

    while url is not None and page_number < limit:
        if url in seen_pages:
            _record(
                conn,
                batch_id,
                url,
                "pagination",
                "pagination loop detected; stopping this source",
                now,
            )
            counters["errors"] += 1
            break
        seen_pages.add(url)
        page_number += 1

        def skip_after_failure(kind: str, message: str) -> str | None:
            """Record a failed page and return the next page to try, or None to stop.

            Fetch and parse failures share one policy: skip the bad page and keep
            going, until MAX_CONSECUTIVE_PAGE_FAILURES pages in a row have failed
            (whatever the status code) or there is no page left to try.
            """
            nonlocal consecutive_failures
            _record(conn, batch_id, url, kind, message, now)
            counters["errors"] += 1
            consecutive_failures += 1
            if consecutive_failures >= MAX_CONSECUTIVE_PAGE_FAILURES:
                return None
            return _fallback_after_failure(adapter, url, page_number, limit, seen_pages)

        try:
            response = client.get(url)
        except RobotsDenied as exc:
            _record(conn, batch_id, url, "robots", str(exc), now)
            counters["errors"] += 1
            break
        except FetchError as exc:
            url = skip_after_failure("fetch", str(exc))
            continue

        try:
            page = adapter.parse_page(response.text, str(response.url))
        except ParseError as exc:
            url = skip_after_failure("parse", str(exc))
            continue

        consecutive_failures = 0

        for warning in page.warnings:
            _record(conn, batch_id, warning.page_url, "parse", warning.message, now)
            counters["errors"] += 1

        for item in page.items:
            if item.external_id in seen_external:
                continue
            seen_external.add(item.external_id)
            counters["items_seen"] += 1

            source_price = item.price
            display_price = source_price
            display_in_stock = item.in_stock
            display_stock_text = item.stock_text
            simulated_row = False

            if simulate and source_price is not None:
                previous = db.get_item_state(conn, spec.key, item.external_id)
                same_day = (
                    previous is not None
                    and previous["last_seen_at"][:10] == day
                )
                # A same-day rerun must not overwrite the day's simulated value.
                # Reuse the observation when it came from the same mode; a mode
                # switch still recomputes from the scraped source price.
                if (
                    same_day
                    and previous is not None
                    and previous["last_simulated"] == 1
                    and previous["price"] is not None
                ):
                    display_price = float(previous["price"])
                    display_in_stock = bool(previous["in_stock"])
                    display_stock_text = previous["stock_text"]
                else:
                    previous_price = None
                    if previous is not None and not same_day:
                        previous_price = previous["price"]
                    display_price = simulate_price(
                        source_price, previous_price, item.external_id, day
                    )
                    display_in_stock, display_stock_text = simulate_stock(
                        item.in_stock, item.external_id, day
                    )
                simulated_row = True

            try:
                outcome = db.save_observation(
                    conn,
                    item=item,
                    source_key=spec.key,
                    batch_id=batch_id,
                    price=display_price,
                    source_price=source_price,
                    currency=item.currency or spec.currency,
                    in_stock=display_in_stock,
                    stock_text=display_stock_text,
                    source_in_stock=item.in_stock,
                    source_stock_text=item.stock_text,
                    simulated=simulated_row,
                    recorded_at=_iso(now),
                )
            except (ValueError, OverflowError) as exc:
                _record(conn, batch_id, item.url, "store", str(exc), now)
                counters["errors"] += 1
                continue

            if outcome.is_new:
                counters["items_new"] += 1
            else:
                counters["items_updated"] += 1
            if outcome.price_changed:
                counters["price_changes"] += 1
            if outcome.stock_changed:
                counters["stock_changes"] += 1

        counters["pages"] += 1
        conn.commit()
        if progress:
            total = f"/{page.total_pages}" if page.total_pages else ""
            progress(
                f"page {page_number}{total}: {len(page.items)} items "
                f"({counters['items_seen']} unique so far)"
            )

        url = page.next_url

    if counters["pages"] == 0:
        return "failed"
    if counters["errors"]:
        return "partial"
    return "success"


def _fallback_after_failure(
    adapter: SiteAdapter,
    url: str,
    page_number: int,
    limit: int,
    seen_pages: set[str],
) -> str | None:
    if page_number >= limit:
        return None
    guess = getattr(adapter, "fallback_next_url", None)
    if guess is None:
        return None
    next_url = guess(url, page_number)
    if next_url is None or next_url in seen_pages:
        return None
    return next_url


def _record(conn, batch_id: int, url: str, kind: str, message: str, now: datetime) -> None:
    db.record_error(
        conn,
        batch_id=batch_id,
        url=url,
        kind=kind,
        message=message,
        occurred_at=_iso(now),
    )
    conn.commit()


def backfill_demo_history(
    conn,
    *,
    source_key: str,
    days: int,
    now: datetime,
    progress: Callable[[str], None] | None = None,
) -> int:
    """Fill missing recent days with clearly-labelled synthetic observations.

    This only runs when explicitly asked (``--ensure-history``) and only creates
    batches whose ``kind`` is ``backfill``. It never touches current item state
    and never performs a network request.
    """

    if days <= 0:
        return 0
    today = now.astimezone(timezone.utc).date()
    target_days = [(today - timedelta(days=offset)).isoformat() for offset in range(days)]
    existing = db.history_days(conn, source_key)
    missing = sorted(day for day in target_days if day not in existing)
    if not missing:
        return 0

    items = db.list_items(conn, source_key)
    priced = [
        item
        for item in items
        if item["source_price"] is not None and item["price"] is not None
    ]
    if not priced:
        return 0

    batch_by_day: dict[str, int] = {}
    note = "Synthetic demo history (no HTTP request); generated to make the trend chart meaningful."
    for day in missing:
        timestamp = f"{day}T06:00:00+00:00"
        batch_by_day[day] = db.start_batch(
            conn,
            source_key=source_key,
            kind="backfill",
            mode="simulated",
            started_at=timestamp,
            notes=note,
        )

    for item in priced:
        prices = backfill_prices(
            current_price=float(item["price"]),
            source_price=float(item["source_price"]),
            key=item["external_id"],
            dates=missing,
        )
        for day in missing:
            display_in_stock, display_stock_text = simulate_stock(
                bool(item["source_in_stock"]), item["external_id"], day
            )
            db.insert_history(
                conn,
                item_id=int(item["id"]),
                batch_id=batch_by_day[day],
                price=prices[day],
                source_price=float(item["source_price"]),
                currency=item["currency"] or "GBP",
                simulated=True,
                recorded_at=f"{day}T06:00:00+00:00",
                in_stock=display_in_stock,
                stock_text=display_stock_text,
                source_in_stock=bool(item["source_in_stock"]),
                source_stock_text=item["source_stock_text"] or "",
            )
    conn.commit()

    for day, batch_id in batch_by_day.items():
        db.finish_batch(
            conn,
            batch_id,
            status="success",
            finished_at=f"{day}T06:00:01+00:00",
            pages_fetched=0,
            items_seen=len(priced),
            items_new=0,
            items_updated=0,
            price_changes=0,
            stock_changes=0,
            error_count=0,
            notes=note,
        )
    if progress:
        progress(
            f"backfilled {len(missing)} synthetic day(s) for {len(priced)} item(s) "
            "(demo data, no network)"
        )
    return len(missing)
