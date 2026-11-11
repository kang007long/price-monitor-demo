from __future__ import annotations

import csv
import json
from datetime import datetime, timezone

import httpx
from openpyxl import load_workbook

from price_monitor import export, pipeline
from price_monitor.http import PoliteClient
from price_monitor.sources.books import BooksAdapter

from tests.helpers import read_fixture

NOW = datetime(2026, 11, 11, 6, 0, tzinfo=timezone.utc)
PAGE_1 = read_fixture("books-page-1.html")
PAGE_2 = read_fixture("books-page-2.html")


def make_client() -> PoliteClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404, request=request)
        if request.url.path == "/catalogue/page-1.html":
            return httpx.Response(200, text=PAGE_1, request=request)
        return httpx.Response(200, text=PAGE_2, request=request)

    return PoliteClient(
        transport=httpx.MockTransport(handler),
        min_interval=0,
        max_retries=0,
        sleep=lambda _seconds: None,
        clock=lambda: 0.0,
    )


def seed(conn, *, simulate: bool = True, ensure_history: int = 3):
    return pipeline.run_scrape(
        conn,
        BooksAdapter(),
        make_client(),
        max_pages=2,
        simulate=simulate,
        ensure_history=ensure_history,
        now=NOW,
    )


def test_export_writes_dashboard_csv_and_xlsx(conn, tmp_path) -> None:
    seed(conn)
    web = tmp_path / "web"
    result = export.export_dashboard(conn, web_dir=web, generated_at=NOW)

    assert result.item_count == 40
    assert result.batch_count == 3
    assert result.dashboard_path.exists()
    assert result.csv_path.exists()
    assert result.xlsx_path.exists()
    assert result.history_csv_path.exists()

    payload = json.loads(result.dashboard_path.read_text(encoding="utf-8"))
    assert payload["schemaVersion"] == export.DASHBOARD_SCHEMA_VERSION
    assert payload["summary"]["items"] == 40
    assert payload["summary"]["inStock"] + payload["summary"]["outOfStock"] == 40
    assert payload["summary"]["batches"] == 1
    assert payload["summary"]["historyDays"] == 3
    assert payload["lastBatch"]["itemsSeen"] == 40
    assert len(payload["batches"]) == 3
    assert payload["demo"]["simulationEnabled"] is True
    assert payload["demo"]["backfilledBatches"] == 2
    assert payload["source"]["key"] == "books"
    assert len(payload["items"][0]["history"]) == 3
    assert payload["items"][0]["history"][0]["date"] < payload["items"][0]["history"][-1]["date"]
    assert payload["exports"]["csv"] == "exports/price-monitor-latest.csv"
    assert not list(result.dashboard_path.parent.glob("*.tmp"))

    with result.csv_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 40
    assert rows[0]["title"]
    assert "price" in rows[0]
    assert "is_simulated" in rows[0]

    with result.history_csv_path.open(encoding="utf-8-sig", newline="") as handle:
        history_rows = list(csv.DictReader(handle))
    assert len(history_rows) == 40 * 3

    workbook = load_workbook(result.xlsx_path)
    assert workbook.sheetnames == ["Items", "Price history", "Scrape batches"]
    assert workbook["Items"].max_row == 41
    assert workbook["Price history"].max_row == 121
    assert workbook["Scrape batches"].max_row == 4
    assert workbook["Items"]["A1"].value == "id"
    assert workbook["Items"].freeze_panes == "A2"


def test_real_mode_export_has_no_simulated_flags(conn, tmp_path) -> None:
    seed(conn, simulate=False, ensure_history=0)
    result = export.export_dashboard(conn, web_dir=tmp_path / "web", generated_at=NOW)
    payload = json.loads(result.dashboard_path.read_text(encoding="utf-8"))
    assert payload["demo"]["simulationEnabled"] is False
    assert payload["demo"]["simulatedItems"] == 0
    assert payload["demo"]["backfilledBatches"] == 0
    assert all(point["simulated"] is False for item in payload["items"] for point in item["history"])


def test_empty_database_exports_valid_empty_files(conn, tmp_path) -> None:
    result = export.export_dashboard(conn, web_dir=tmp_path / "web", generated_at=NOW)
    payload = json.loads(result.dashboard_path.read_text(encoding="utf-8"))
    assert payload["items"] == []
    assert payload["lastBatch"] is None
    assert payload["summary"]["averagePrice"] is None

    with result.csv_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows == [["id", "title"]]

    workbook = load_workbook(result.xlsx_path)
    assert workbook["Items"].max_row == 1


def test_simulated_history_survives_a_later_real_run(conn, tmp_path) -> None:
    seed(conn, simulate=True, ensure_history=3)
    pipeline.run_scrape(
        conn,
        BooksAdapter(),
        make_client(),
        max_pages=2,
        simulate=False,
        ensure_history=0,
        now=NOW,
    )
    result = export.export_dashboard(conn, web_dir=tmp_path / "web", generated_at=NOW)
    payload = json.loads(result.dashboard_path.read_text(encoding="utf-8"))

    assert payload["demo"]["simulationEnabled"] is False
    assert payload["demo"]["simulatedItems"] == 40
    assert all(item["simulated"] is False for item in payload["items"])
    assert any(
        point["simulated"] for item in payload["items"] for point in item["history"]
    )


def test_exports_neutralise_spreadsheet_formulas(conn, tmp_path) -> None:
    seed(conn)
    conn.execute(
        "UPDATE items SET title = '=1+1' WHERE id = (SELECT MIN(id) FROM items)"
    )
    conn.commit()
    result = export.export_dashboard(conn, web_dir=tmp_path / "web", generated_at=NOW)

    with result.csv_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert any(row["title"] == "'=1+1" for row in rows)
    assert all(not row["title"].startswith("=") for row in rows)

    workbook = load_workbook(result.xlsx_path)
    titles = [cell for cell in workbook["Items"]["B"][1:] if cell.value == "'=1+1"]
    assert titles
    assert titles[0].data_type == "s"
    assert all(
        cell.data_type != "f"
        for sheet in workbook.sheetnames
        for row_cells in workbook[sheet].iter_rows()
        for cell in row_cells
    )
