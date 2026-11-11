"""SQLite storage: current state, price/stock history, scrape batches, errors.

The dashboard is a *derived* static artifact; SQLite is the operational source
of truth. Keeping history in separate tables makes change queries cheap and
keeps the current-state table small enough to export in one pass.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from price_monitor.models import ObservationOutcome, ParsedItem
from price_monitor.sources.base import SourceSpec

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
    key TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    base_url TEXT NOT NULL,
    robots_url TEXT NOT NULL,
    license_note TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key TEXT NOT NULL REFERENCES sources(key),
    kind TEXT NOT NULL CHECK (kind IN ('scrape', 'backfill')),
    mode TEXT NOT NULL CHECK (mode IN ('real', 'simulated')),
    status TEXT NOT NULL CHECK (status IN ('running', 'success', 'partial', 'failed')),
    started_at TEXT NOT NULL,
    finished_at TEXT,
    pages_fetched INTEGER NOT NULL DEFAULT 0,
    items_seen INTEGER NOT NULL DEFAULT 0,
    items_new INTEGER NOT NULL DEFAULT 0,
    items_updated INTEGER NOT NULL DEFAULT 0,
    price_changes INTEGER NOT NULL DEFAULT 0,
    stock_changes INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key TEXT NOT NULL REFERENCES sources(key),
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    image_url TEXT,
    category TEXT,
    rating INTEGER,
    currency TEXT NOT NULL DEFAULT '',
    source_price REAL,
    price REAL,
    in_stock INTEGER NOT NULL DEFAULT 1,
    stock_text TEXT NOT NULL DEFAULT '',
    source_in_stock INTEGER NOT NULL DEFAULT 1,
    source_stock_text TEXT NOT NULL DEFAULT '',
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    UNIQUE (source_key, external_id)
);

CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    batch_id INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    price REAL NOT NULL,
    source_price REAL NOT NULL,
    currency TEXT NOT NULL,
    simulated INTEGER NOT NULL DEFAULT 0,
    recorded_at TEXT NOT NULL,
    UNIQUE (item_id, batch_id)
);

CREATE TABLE IF NOT EXISTS stock_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    batch_id INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    in_stock INTEGER NOT NULL,
    stock_text TEXT NOT NULL DEFAULT '',
    source_in_stock INTEGER NOT NULL DEFAULT 1,
    source_stock_text TEXT NOT NULL DEFAULT '',
    simulated INTEGER NOT NULL DEFAULT 0,
    recorded_at TEXT NOT NULL,
    UNIQUE (item_id, batch_id)
);

CREATE TABLE IF NOT EXISTS scrape_errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    url TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL,
    message TEXT NOT NULL,
    occurred_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_items_source ON items(source_key);
CREATE INDEX IF NOT EXISTS idx_price_history_item ON price_history(item_id, recorded_at);
CREATE INDEX IF NOT EXISTS idx_price_history_batch ON price_history(batch_id);
CREATE INDEX IF NOT EXISTS idx_stock_history_item ON stock_history(item_id, recorded_at);
CREATE INDEX IF NOT EXISTS idx_batches_source ON batches(source_key, started_at);
CREATE INDEX IF NOT EXISTS idx_errors_batch ON scrape_errors(batch_id);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def initialize(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT INTO meta(key, value) VALUES('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()


def upsert_source(conn: sqlite3.Connection, spec: SourceSpec) -> None:
    conn.execute(
        """
        INSERT INTO sources(key, name, base_url, robots_url, license_note)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            name = excluded.name,
            base_url = excluded.base_url,
            robots_url = excluded.robots_url,
            license_note = excluded.license_note
        """,
        (spec.key, spec.name, spec.base_url, spec.robots_url, spec.license_note),
    )


def start_batch(
    conn: sqlite3.Connection,
    *,
    source_key: str,
    kind: str,
    mode: str,
    started_at: str,
    notes: str | None = None,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO batches(source_key, kind, mode, status, started_at, notes)
        VALUES (?, ?, ?, 'running', ?, ?)
        """,
        (source_key, kind, mode, started_at, notes),
    )
    conn.commit()
    return int(cursor.lastrowid)


def finish_batch(
    conn: sqlite3.Connection,
    batch_id: int,
    *,
    status: str,
    finished_at: str,
    pages_fetched: int,
    items_seen: int,
    items_new: int,
    items_updated: int,
    price_changes: int,
    stock_changes: int,
    error_count: int,
    notes: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE batches SET
            status = ?, finished_at = ?, pages_fetched = ?, items_seen = ?,
            items_new = ?, items_updated = ?, price_changes = ?,
            stock_changes = ?, error_count = ?, notes = COALESCE(?, notes)
        WHERE id = ?
        """,
        (
            status,
            finished_at,
            pages_fetched,
            items_seen,
            items_new,
            items_updated,
            price_changes,
            stock_changes,
            error_count,
            notes,
            batch_id,
        ),
    )
    conn.commit()


def record_error(
    conn: sqlite3.Connection,
    *,
    batch_id: int,
    url: str,
    kind: str,
    message: str,
    occurred_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO scrape_errors(batch_id, url, kind, message, occurred_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (batch_id, url, kind, message[:1000], occurred_at),
    )


def save_observation(
    conn: sqlite3.Connection,
    *,
    item: ParsedItem,
    source_key: str,
    batch_id: int,
    price: float | None,
    source_price: float | None,
    currency: str,
    in_stock: bool,
    stock_text: str,
    source_in_stock: bool,
    source_stock_text: str,
    simulated: bool,
    recorded_at: str,
) -> ObservationOutcome:
    """Upsert current state and append this batch's history rows."""

    previous = conn.execute(
        "SELECT id, price, in_stock FROM items WHERE source_key = ? AND external_id = ?",
        (source_key, item.external_id),
    ).fetchone()

    if previous is None:
        cursor = conn.execute(
            """
            INSERT INTO items(
                source_key, external_id, title, url, image_url, category, rating,
                currency, source_price, price, in_stock, stock_text,
                source_in_stock, source_stock_text, first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_key,
                item.external_id,
                item.title,
                item.url,
                item.image_url,
                item.category,
                item.rating,
                currency,
                source_price,
                price,
                1 if in_stock else 0,
                stock_text,
                1 if source_in_stock else 0,
                source_stock_text,
                recorded_at,
                recorded_at,
            ),
        )
        item_id = int(cursor.lastrowid)
        is_new = True
        previous_price = None
        previous_in_stock = None
        price_changed = False
        stock_changed = False
    else:
        item_id = int(previous["id"])
        previous_price = previous["price"]
        previous_in_stock = bool(previous["in_stock"])
        is_new = False
        conn.execute(
            """
            UPDATE items SET
                title = ?, url = ?, image_url = ?, category = ?, rating = ?,
                currency = ?, source_price = ?, price = ?, in_stock = ?,
                stock_text = ?, source_in_stock = ?, source_stock_text = ?,
                last_seen_at = ?
            WHERE id = ?
            """,
            (
                item.title,
                item.url,
                item.image_url,
                item.category,
                item.rating,
                currency,
                source_price,
                price,
                1 if in_stock else 0,
                stock_text,
                1 if source_in_stock else 0,
                source_stock_text,
                recorded_at,
                item_id,
            ),
        )
        price_changed = (
            previous_price is not None
            and price is not None
            and abs(previous_price - price) >= 0.005
        )
        stock_changed = previous_in_stock != in_stock

    if price is not None and source_price is not None:
        conn.execute(
            """
            INSERT INTO price_history(
                item_id, batch_id, price, source_price, currency, simulated, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(item_id, batch_id) DO UPDATE SET
                price = excluded.price,
                source_price = excluded.source_price,
                currency = excluded.currency,
                simulated = excluded.simulated,
                recorded_at = excluded.recorded_at
            """,
            (
                item_id,
                batch_id,
                price,
                source_price,
                currency,
                1 if simulated else 0,
                recorded_at,
            ),
        )
        conn.execute(
            """
            INSERT INTO stock_history(
                item_id, batch_id, in_stock, stock_text, source_in_stock,
                source_stock_text, simulated, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(item_id, batch_id) DO UPDATE SET
                in_stock = excluded.in_stock,
                stock_text = excluded.stock_text,
                source_in_stock = excluded.source_in_stock,
                source_stock_text = excluded.source_stock_text,
                simulated = excluded.simulated,
                recorded_at = excluded.recorded_at
            """,
            (
                item_id,
                batch_id,
                1 if in_stock else 0,
                stock_text,
                1 if source_in_stock else 0,
                source_stock_text,
                1 if simulated else 0,
                recorded_at,
            ),
        )

    return ObservationOutcome(
        item_id=item_id,
        is_new=is_new,
        price_changed=price_changed,
        stock_changed=stock_changed,
        previous_price=previous_price,
        previous_in_stock=previous_in_stock,
    )


def insert_history(
    conn: sqlite3.Connection,
    *,
    item_id: int,
    batch_id: int,
    price: float,
    source_price: float,
    currency: str,
    simulated: bool,
    recorded_at: str,
    in_stock: bool,
    stock_text: str,
    source_in_stock: bool,
    source_stock_text: str,
) -> None:
    """Append history without touching current state (used by demo backfill)."""

    conn.execute(
        """
        INSERT INTO price_history(
            item_id, batch_id, price, source_price, currency, simulated, recorded_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(item_id, batch_id) DO UPDATE SET
            price = excluded.price,
            source_price = excluded.source_price,
            currency = excluded.currency,
            simulated = excluded.simulated,
            recorded_at = excluded.recorded_at
        """,
        (item_id, batch_id, price, source_price, currency, 1 if simulated else 0, recorded_at),
    )
    conn.execute(
        """
        INSERT INTO stock_history(
            item_id, batch_id, in_stock, stock_text, source_in_stock,
            source_stock_text, simulated, recorded_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(item_id, batch_id) DO UPDATE SET
            in_stock = excluded.in_stock,
            stock_text = excluded.stock_text,
            source_in_stock = excluded.source_in_stock,
            source_stock_text = excluded.source_stock_text,
            simulated = excluded.simulated,
            recorded_at = excluded.recorded_at
        """,
        (
            item_id,
            batch_id,
            1 if in_stock else 0,
            stock_text,
            1 if source_in_stock else 0,
            source_stock_text,
            1 if simulated else 0,
            recorded_at,
        ),
    )


def history_days(conn: sqlite3.Connection, source_key: str) -> set[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT substr(ph.recorded_at, 1, 10) AS day
        FROM price_history ph
        JOIN batches b ON b.id = ph.batch_id
        JOIN items i ON i.id = ph.item_id
        WHERE i.source_key = ? AND b.status IN ('success', 'partial')
        """,
        (source_key,),
    ).fetchall()
    return {row["day"] for row in rows}


def list_items(conn: sqlite3.Connection, source_key: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT id, external_id, title, url, currency, source_price, price,
               in_stock, stock_text, source_in_stock, source_stock_text
        FROM items WHERE source_key = ? ORDER BY id
        """,
        (source_key,),
    ).fetchall()


def fetch_items(conn: sqlite3.Connection, source_key: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT id, external_id, title, url, image_url, category, rating,
               currency, source_price, price, in_stock, stock_text,
               source_in_stock, source_stock_text,
               first_seen_at, last_seen_at
        FROM items WHERE source_key = ? ORDER BY title COLLATE NOCASE, id
        """,
        (source_key,),
    ).fetchall()


def fetch_price_history(conn: sqlite3.Connection, source_key: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT ph.item_id, ph.price, ph.source_price, ph.currency, ph.simulated,
               ph.recorded_at, COALESCE(sh.in_stock, 1) AS in_stock,
               COALESCE(sh.source_in_stock, 1) AS source_in_stock
        FROM price_history ph
        JOIN items i ON i.id = ph.item_id
        JOIN batches b ON b.id = ph.batch_id
        LEFT JOIN stock_history sh
               ON sh.item_id = ph.item_id AND sh.batch_id = ph.batch_id
        WHERE i.source_key = ? AND b.status IN ('success', 'partial')
        ORDER BY ph.recorded_at ASC, ph.id ASC
        """,
        (source_key,),
    ).fetchall()


def fetch_batches(
    conn: sqlite3.Connection, source_key: str, *, limit: int = 30
) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT id, kind, mode, status, started_at, finished_at, pages_fetched,
               items_seen, items_new, items_updated, price_changes,
               stock_changes, error_count, notes
        FROM batches
        WHERE source_key = ? AND status != 'running'
        ORDER BY started_at DESC, id DESC
        LIMIT ?
        """,
        (source_key, limit),
    ).fetchall()


def fetch_errors(
    conn: sqlite3.Connection, batch_ids: list[int], *, limit: int = 100
) -> list[sqlite3.Row]:
    if not batch_ids:
        return []
    placeholders = ",".join("?" for _ in batch_ids)
    return conn.execute(
        f"""
        SELECT batch_id, url, kind, message, occurred_at
        FROM scrape_errors
        WHERE batch_id IN ({placeholders})
        ORDER BY occurred_at DESC, id DESC
        LIMIT ?
        """,
        (*batch_ids, limit),
    ).fetchall()


def fetch_latest_scrape(conn: sqlite3.Connection, source_key: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT * FROM batches
        WHERE source_key = ? AND kind = 'scrape' AND status != 'running'
        ORDER BY id DESC LIMIT 1
        """,
        (source_key,),
    ).fetchone()


def count_batches(conn: sqlite3.Connection, source_key: str, *, kind: str | None = None) -> int:
    if kind:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM batches WHERE source_key = ? AND kind = ? AND status != 'running'",
            (source_key, kind),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM batches WHERE source_key = ? AND status != 'running'",
            (source_key,),
        ).fetchone()
    return int(row["n"])


def count_errors(conn: sqlite3.Connection, source_key: str) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS n FROM scrape_errors e
        JOIN batches b ON b.id = e.batch_id
        WHERE b.source_key = ?
        """,
        (source_key,),
    ).fetchone()
    return int(row["n"])


def count_items(conn: sqlite3.Connection, source_key: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM items WHERE source_key = ?", (source_key,)
    ).fetchone()
    return int(row["n"])


def get_item_state(
    conn: sqlite3.Connection, source_key: str, external_id: str
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT i.price, i.in_stock, i.stock_text, i.last_seen_at,
               (
                   SELECT ph.simulated
                   FROM price_history ph
                   WHERE ph.item_id = i.id
                   ORDER BY ph.recorded_at DESC, ph.id DESC
                   LIMIT 1
               ) AS last_simulated
        FROM items i
        WHERE i.source_key = ? AND i.external_id = ?
        """,
        (source_key, external_id),
    ).fetchone()


def mark_stale_running(
    conn: sqlite3.Connection, *, before_iso: str, now_iso: str
) -> int:
    """Mark interrupted batches as failed so they never look permanently active."""

    cursor = conn.execute(
        """
        UPDATE batches SET
            status = 'failed',
            finished_at = ?,
            notes = CASE
                WHEN notes IS NULL OR notes = '' THEN 'Marked failed: interrupted run'
                ELSE notes || ' | Marked failed: interrupted run'
            END
        WHERE status = 'running' AND started_at < ?
        """,
        (now_iso, before_iso),
    )
    conn.commit()
    return int(cursor.rowcount)
