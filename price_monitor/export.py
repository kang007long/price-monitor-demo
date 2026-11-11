"""Build the static dashboard payload and downloadable reports from SQLite."""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from price_monitor import config, db

DASHBOARD_SCHEMA_VERSION = 1

# Text from a scraped page is untrusted. A leading formula marker would make
# Excel/Sheets treat a title (or URL) as a formula when the export is opened.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _safe_spreadsheet_text(value: object) -> object:
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return f"'{value}"
    return value


@dataclass(slots=True)
class ExportResult:
    dashboard_path: Path
    csv_path: Path
    xlsx_path: Path
    history_csv_path: Path
    item_count: int
    batch_count: int


def _money(value: float | None) -> float | None:
    return None if value is None else round(float(value), 2)


def _history_by_item(
    conn, source_key: str, max_history_days: int
) -> dict[int, list[dict[str, object]]]:
    rows = db.fetch_price_history(conn, source_key)
    per_item: dict[int, dict[str, dict[str, object]]] = {}
    for row in rows:
        date = row["recorded_at"][:10]
        # Rows are ordered oldest -> newest; the last batch on a date wins.
        per_item.setdefault(int(row["item_id"]), {})[date] = {
            "date": date,
            "price": _money(row["price"]),
            "sourcePrice": _money(row["source_price"]),
            "simulated": bool(row["simulated"]),
            "inStock": bool(row["in_stock"]),
            "sourceInStock": bool(row["source_in_stock"]),
        }
    result: dict[int, list[dict[str, object]]] = {}
    for item_id, by_date in per_item.items():
        points = [by_date[day] for day in sorted(by_date)]
        result[item_id] = points[-max_history_days:] if max_history_days > 0 else points
    return result


def _batch_dict(row) -> dict[str, object]:
    return {
        "id": int(row["id"]),
        "kind": row["kind"],
        "mode": row["mode"],
        "status": row["status"],
        "startedAt": row["started_at"],
        "finishedAt": row["finished_at"],
        "pages": int(row["pages_fetched"]),
        "itemsSeen": int(row["items_seen"]),
        "itemsNew": int(row["items_new"]),
        "itemsUpdated": int(row["items_updated"]),
        "priceChanges": int(row["price_changes"]),
        "stockChanges": int(row["stock_changes"]),
        "errorCount": int(row["error_count"]),
        "notes": row["notes"],
    }


def build_dashboard(
    conn,
    *,
    source_key: str = "books",
    generated_at: datetime | None = None,
    max_history_days: int = config.MAX_HISTORY_DAYS,
) -> dict[str, object]:
    generated = generated_at or datetime.now(timezone.utc)
    item_rows = db.fetch_items(conn, source_key)
    history = _history_by_item(conn, source_key, max_history_days)

    items: list[dict[str, object]] = []
    simulated_items = 0
    for row in item_rows:
        item_id = int(row["id"])
        points = history.get(item_id, [])
        # Availability is about the whole history, not just today's value: a
        # later real run must not hide older simulated observations.
        if any(bool(point["simulated"]) for point in points):
            simulated_items += 1
        items.append(
            {
                "id": row["external_id"],
                "title": row["title"],
                "url": row["url"],
                "category": row["category"],
                "rating": row["rating"],
                "currency": row["currency"] or "GBP",
                "price": _money(row["price"]),
                "sourcePrice": _money(row["source_price"]),
                "inStock": bool(row["in_stock"]),
                "stockText": row["stock_text"],
                "sourceInStock": bool(row["source_in_stock"]),
                "simulated": bool(points and points[-1]["simulated"]),
                "firstSeenAt": row["first_seen_at"],
                "lastSeenAt": row["last_seen_at"],
                "history": points,
            }
        )

    batch_rows = db.fetch_batches(conn, source_key, limit=30)
    batches = [_batch_dict(row) for row in batch_rows]
    batch_ids = [int(row["id"]) for row in batch_rows]
    errors = [
        {
            "batchId": int(row["batch_id"]),
            "url": row["url"],
            "kind": row["kind"],
            "message": row["message"],
            "occurredAt": row["occurred_at"],
        }
        for row in db.fetch_errors(conn, batch_ids, limit=50)
    ]

    latest_row = db.fetch_latest_scrape(conn, source_key)
    latest_batch = _batch_dict(latest_row) if latest_row is not None else None
    priced = [float(item["price"]) for item in items if item["price"] is not None]
    in_stock = sum(1 for item in items if item["inStock"])
    backfilled_batches = db.count_batches(conn, source_key, kind="backfill")
    scrape_batches = db.count_batches(conn, source_key, kind="scrape")
    total_errors = db.count_errors(conn, source_key)

    source_row = conn.execute(
        "SELECT key, name, base_url, license_note FROM sources WHERE key = ?",
        (source_key,),
    ).fetchone()
    source = (
        {
            "key": source_row["key"],
            "name": source_row["name"],
            "url": source_row["base_url"],
            "note": source_row["license_note"],
        }
        if source_row is not None
        else {
            "key": source_key,
            "name": source_key,
            "url": "",
            "note": "",
        }
    )

    simulated_latest = bool(latest_batch and latest_batch["mode"] == "simulated")
    payload = {
        "schemaVersion": DASHBOARD_SCHEMA_VERSION,
        "generatedAt": generated.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "source": source,
        "demo": {
            "simulationEnabled": simulated_latest,
            "simulatedItems": simulated_items,
            "backfilledBatches": backfilled_batches,
            "note": (
                "This is a portfolio demo on a public scraping sandbox. Real prices "
                "never change there, so daily price movement is simulated. Every "
                "simulated value is flagged; the scraped source price is kept beside "
                "it. No real shops, accounts, or customer data are involved."
            ),
        },
        "summary": {
            "items": len(items),
            "inStock": in_stock,
            "outOfStock": len(items) - in_stock,
            "averagePrice": round(sum(priced) / len(priced), 2) if priced else None,
            "currency": items[0]["currency"] if items else "GBP",
            "batches": scrape_batches,
            "backfillBatches": backfilled_batches,
            "errors": total_errors,
            "historyDays": max((len(points) for points in history.values()), default=0),
        },
        "lastBatch": latest_batch,
        "batches": batches,
        "errors": errors,
        "items": items,
        "exports": {
            "csv": "exports/price-monitor-latest.csv",
            "xlsx": "exports/price-monitor-latest.xlsx",
            "historyCsv": "exports/price-monitor-history.csv",
        },
    }
    return payload


def _write_atomic(path: Path, writer) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        writer(tmp)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def _write_json(path: Path, payload: dict[str, object]) -> None:
    def writer(tmp: Path) -> None:
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

    _write_atomic(path, writer)


def _item_rows(payload: dict[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in payload["items"]:  # type: ignore[union-attr]
        history = item["history"]  # type: ignore[index]
        previous = history[-2]["price"] if len(history) >= 2 else None
        change = None
        change_pct = None
        if previous is not None and item["price"] is not None:
            change = round(item["price"] - previous, 2)
            change_pct = round((change / previous) * 100, 2) if previous else None
        rows.append(
            {
                "id": item["id"],
                "title": item["title"],
                "rating": item["rating"],
                "currency": item["currency"],
                "price": item["price"],
                "source_price": item["sourcePrice"],
                "is_simulated": int(bool(item["simulated"])),
                "in_stock": int(bool(item["inStock"])),
                "stock_text": item["stockText"],
                "source_in_stock": int(bool(item["sourceInStock"])),
                "change_vs_previous": change,
                "change_pct_vs_previous": change_pct,
                "first_seen_at": item["firstSeenAt"],
                "last_seen_at": item["lastSeenAt"],
                "url": item["url"],
            }
        )
    return rows


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    def writer(tmp: Path) -> None:
        # utf-8-sig keeps the pound sign readable when opened in Excel.
        with tmp.open("w", newline="", encoding="utf-8-sig") as handle:
            out = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            out.writeheader()
            out.writerows(
                {
                    key: _safe_spreadsheet_text(value)
                    for key, value in row.items()
                }
                for row in rows
            )

    _write_atomic(path, writer)


def _history_rows(payload: dict[str, object]) -> list[dict[str, object]]:
    titles = {item["id"]: item["title"] for item in payload["items"]}  # type: ignore[union-attr]
    rows: list[dict[str, object]] = []
    for item in payload["items"]:  # type: ignore[union-attr]
        for point in item["history"]:  # type: ignore[index]
            rows.append(
                {
                    "item_id": item["id"],
                    "title": titles[item["id"]],
                    "date": point["date"],
                    "price": point["price"],
                    "source_price": point["sourcePrice"],
                    "simulated": int(bool(point["simulated"])),
                    "in_stock": int(bool(point["inStock"])),
                    "source_in_stock": int(bool(point["sourceInStock"])),
                }
            )
    return rows


def _style_header(ws) -> None:
    fill = PatternFill("solid", fgColor="111827")
    font = Font(color="FFFFFF", bold=True)
    for cell in ws[1]:
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(vertical="center")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    ws.row_dimensions[1].height = 20


def _autosize(ws, widths: list[int]) -> None:
    for index, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(index)].width = width


def _write_xlsx(
    path: Path,
    items: list[dict[str, object]],
    history: list[dict[str, object]],
    batches: list[dict[str, object]],
) -> None:
    def writer(tmp: Path) -> None:
        wb = Workbook()
        ws = wb.active
        ws.title = "Items"
        item_headers = list(items[0].keys()) if items else ["id", "title"]
        ws.append(item_headers)
        for row in items:
            ws.append([_safe_spreadsheet_text(row[key]) for key in item_headers])
        _style_header(ws)
        _autosize(ws, [28, 48, 8, 9, 10, 12, 11, 9, 22, 15, 16, 18, 22, 22, 50])
        price_columns = [
            index
            for index, key in enumerate(item_headers, start=1)
            if key in {"price", "source_price", "change_vs_previous"}
        ]
        for column in price_columns:
            for cell in ws.iter_cols(
                min_col=column, max_col=column, min_row=2, max_row=ws.max_row
            ):
                for c in cell:
                    c.number_format = '"£"#,##0.00'

        hist = wb.create_sheet("Price history")
        hist_headers = list(history[0].keys()) if history else ["item_id", "date"]
        hist.append(hist_headers)
        for row in history:
            hist.append([_safe_spreadsheet_text(row[key]) for key in hist_headers])
        _style_header(hist)
        _autosize(hist, [28, 48, 12, 10, 12, 10, 9, 15])
        for column in (4, 5):
            for cell in hist.iter_cols(
                min_col=column, max_col=column, min_row=2, max_row=hist.max_row
            ):
                for c in cell:
                    c.number_format = '"£"#,##0.00'

        batch = wb.create_sheet("Scrape batches")
        batch_headers = [
            "id",
            "kind",
            "mode",
            "status",
            "startedAt",
            "finishedAt",
            "pages",
            "itemsSeen",
            "itemsNew",
            "itemsUpdated",
            "priceChanges",
            "stockChanges",
            "errorCount",
            "notes",
        ]
        batch.append(batch_headers)
        for row in batches:
            batch.append([_safe_spreadsheet_text(row.get(key)) for key in batch_headers])
        _style_header(batch)
        _autosize(batch, [6, 10, 10, 9, 24, 24, 7, 11, 9, 12, 13, 13, 10, 70])

        # Explicitly keep text cells as text even if a value looks like a formula.
        for sheet in (ws, hist, batch):
            for row_cells in sheet.iter_rows(min_row=2):
                for cell in row_cells:
                    if isinstance(cell.value, str):
                        cell.data_type = "s"

        wb.save(tmp)

    _write_atomic(path, writer)


def export_dashboard(
    conn,
    *,
    web_dir: str | Path = config.DEFAULT_WEB_DIR,
    source_key: str = "books",
    generated_at: datetime | None = None,
    max_history_days: int = config.MAX_HISTORY_DAYS,
) -> ExportResult:
    web_dir = Path(web_dir)
    payload = build_dashboard(
        conn,
        source_key=source_key,
        generated_at=generated_at,
        max_history_days=max_history_days,
    )
    data_dir = web_dir / "public" / "data"
    exports_dir = web_dir / "public" / "exports"

    dashboard_path = data_dir / "dashboard.json"
    _write_json(dashboard_path, payload)

    items = _item_rows(payload)
    history = _history_rows(payload)
    batches = payload["batches"]

    csv_path = exports_dir / "price-monitor-latest.csv"
    _write_csv(csv_path, items, list(items[0].keys()) if items else ["id", "title"])

    history_csv_path = exports_dir / "price-monitor-history.csv"
    _write_csv(
        history_csv_path,
        history,
        list(history[0].keys()) if history else ["item_id", "date"],
    )

    xlsx_path = exports_dir / "price-monitor-latest.xlsx"
    _write_xlsx(xlsx_path, items, history, batches)  # type: ignore[arg-type]

    return ExportResult(
        dashboard_path=dashboard_path,
        csv_path=csv_path,
        xlsx_path=xlsx_path,
        history_csv_path=history_csv_path,
        item_count=len(payload["items"]),  # type: ignore[arg-type]
        batch_count=len(batches),  # type: ignore[arg-type]
    )
