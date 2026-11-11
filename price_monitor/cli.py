"""Command line entry point.

    price-monitor scrape --simulate --ensure-history 14
    price-monitor export
"""

from __future__ import annotations

import argparse
import sys
from datetime import timedelta
from pathlib import Path

from price_monitor import __version__, config, db, export, pipeline
from price_monitor.http import PoliteClient
from price_monitor.sources import ADAPTERS, get_adapter


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="price-monitor",
        description="Polite price-monitoring demo: scrape -> SQLite -> static dashboard.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    scrape = sub.add_parser("scrape", help="run one scrape batch")
    scrape.add_argument(
        "--source", choices=sorted(ADAPTERS), default="books", help="site adapter"
    )
    scrape.add_argument("--db", type=Path, default=config.DEFAULT_DB_PATH)
    scrape.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="stop after N pages (useful for a quick local test)",
    )
    scrape.add_argument(
        "--simulate",
        action="store_true",
        help="add clearly-labelled synthetic price/stock movement (demo only)",
    )
    scrape.add_argument(
        "--ensure-history",
        type=int,
        default=0,
        metavar="DAYS",
        help="backfill missing recent days with synthetic observations (requires --simulate)",
    )
    scrape.add_argument(
        "--min-interval",
        type=float,
        default=config.MIN_REQUEST_INTERVAL,
        help="minimum seconds between requests (default: %(default)s)",
    )
    scrape.add_argument(
        "--timeout", type=float, default=config.REQUEST_TIMEOUT, help="request timeout"
    )
    scrape.add_argument(
        "--retries", type=int, default=config.MAX_RETRIES, help="retries per request"
    )
    scrape.add_argument("--notes", default=None, help="free-form note stored on the batch")
    scrape.add_argument("-q", "--quiet", action="store_true", help="only print the summary")

    export_cmd = sub.add_parser("export", help="write dashboard JSON + CSV/XLSX exports")
    export_cmd.add_argument("--db", type=Path, default=config.DEFAULT_DB_PATH)
    export_cmd.add_argument("--web-dir", type=Path, default=config.DEFAULT_WEB_DIR)
    export_cmd.add_argument("--source", choices=sorted(ADAPTERS), default="books")
    export_cmd.add_argument(
        "--history-days", type=int, default=config.MAX_HISTORY_DAYS
    )
    return parser


def _scrape(args: argparse.Namespace) -> int:
    adapter = get_adapter(args.source)
    max_pages = (
        args.max_pages
        if args.max_pages is not None
        else adapter.spec.default_max_pages
    )
    if not 1 <= max_pages <= adapter.spec.default_max_pages:
        print(
            f"error: --max-pages must be between 1 and {adapter.spec.default_max_pages}",
            file=sys.stderr,
        )
        return 2
    if args.ensure_history < 0:
        print("error: --ensure-history must be >= 0", file=sys.stderr)
        return 2
    if args.ensure_history and not args.simulate:
        print("error: --ensure-history requires --simulate", file=sys.stderr)
        return 2
    if args.min_interval < 1.0:
        print(
            "error: --min-interval must be at least 1.0 second (1 request/second cap)",
            file=sys.stderr,
        )
        return 2
    if args.timeout <= 0:
        print("error: --timeout must be > 0", file=sys.stderr)
        return 2
    if args.retries < 0:
        print("error: --retries must be >= 0", file=sys.stderr)
        return 2

    now = pipeline.utc_now()
    conn = db.connect(args.db)
    try:
        db.initialize(conn)
        stale = db.mark_stale_running(
            conn,
            before_iso=(now - timedelta(hours=2)).isoformat(timespec="seconds"),
            now_iso=now.isoformat(timespec="seconds"),
        )
        if stale:
            print(f"note: marked {stale} interrupted batch(es) as failed")

        def progress(message: str) -> None:
            if not args.quiet:
                print(f"  · {message}", flush=True)

        if not args.quiet:
            mode = "simulated" if args.simulate else "real"
            print(
                f"scraping {adapter.spec.name} ({mode}, max {max_pages} pages, "
                f">= {args.min_interval:g}s between requests)"
            )

        with PoliteClient(
            min_interval=args.min_interval,
            timeout=args.timeout,
            max_retries=args.retries,
        ) as client:
            summary = pipeline.run_scrape(
                conn,
                adapter,
                client,
                max_pages=max_pages,
                simulate=args.simulate,
                ensure_history=args.ensure_history,
                now=now,
                notes=args.notes,
                progress=progress,
            )
    finally:
        conn.close()

    print(
        f"batch #{summary.batch_id}: {summary.status} · {summary.pages_fetched} pages · "
        f"{summary.items_seen} items ({summary.items_new} new, "
        f"{summary.items_updated} updated) · {summary.price_changes} price changes · "
        f"{summary.stock_changes} stock changes · {summary.errors} errors"
    )
    if summary.backfilled_days:
        print(f"demo history: {summary.backfilled_days} synthetic day(s) generated")
    return 0 if summary.status != "failed" else 1


def _export(args: argparse.Namespace) -> int:
    conn = db.connect(args.db)
    try:
        db.initialize(conn)
        result = export.export_dashboard(
            conn,
            web_dir=args.web_dir,
            source_key=args.source,
            max_history_days=args.history_days,
        )
    finally:
        conn.close()
    print(f"dashboard: {result.dashboard_path}")
    print(f"csv:       {result.csv_path}")
    print(f"xlsx:      {result.xlsx_path}")
    print(f"history:   {result.history_csv_path}")
    print(f"exported {result.item_count} items across {result.batch_count} recent batches")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "scrape":
        return _scrape(args)
    if args.command == "export":
        return _export(args)
    parser.error(f"unknown command {args.command!r}")
    return 2  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
