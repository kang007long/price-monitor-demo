"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { downloadCsv } from "@/lib/csv";
import { withBasePath } from "@/lib/data";
import {
  changeForWindow,
  computeMovers,
  filterItems,
  hasSimulatedHistory,
  paginate,
  realValues,
  sortItems,
} from "@/lib/filters";
import {
  formatDate,
  formatMoney,
  formatNumber,
  formatWindow,
} from "@/lib/format";
import type {
  Filters,
  SortKey,
  StockFilter,
  WindowKey,
} from "@/lib/types";
import { useDashboard } from "@/lib/useDashboard";
import { BookCover } from "./BookCover";
import { ChangePill } from "./ChangePill";
import { DetailDrawer } from "./DetailDrawer";
import {
  AlertIcon,
  ArrowRightIcon,
  DownloadIcon,
  RefreshIcon,
  SearchIcon,
} from "./Icons";
import { KpiCards } from "./KpiCards";
import { MoversPanel } from "./MoversPanel";
import { Rating } from "./Rating";
import { RunSummary } from "./RunSummary";
import { Sparkline } from "./Sparkline";

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: "title-asc", label: "Title A–Z" },
  { value: "price-desc", label: "Price: high to low" },
  { value: "price-asc", label: "Price: low to high" },
  { value: "change-desc", label: "Biggest increase" },
  { value: "change-asc", label: "Biggest decrease" },
  { value: "rating-desc", label: "Highest rated" },
];

const WINDOWS: { value: WindowKey; label: string }[] = [
  { value: "1d", label: "1 day" },
  { value: "7d", label: "7 days" },
  { value: "30d", label: "30 days" },
  { value: "all", label: "All history" },
];

function pageList(current: number, total: number): (number | "ellipsis")[] {
  if (total <= 7) return Array.from({ length: total }, (_, index) => index + 1);
  const pages = new Set([1, total, current - 1, current, current + 1]);
  const sorted = [...pages].filter((page) => page >= 1 && page <= total).sort((a, b) => a - b);
  const result: (number | "ellipsis")[] = [];
  sorted.forEach((page, index) => {
    if (index > 0 && page - sorted[index - 1] > 1) result.push("ellipsis");
    result.push(page);
  });
  return result;
}

export function DashboardView() {
  const { data, error, loading, reload } = useDashboard();
  const [query, setQuery] = useState("");
  const [stock, setStock] = useState<StockFilter>("all");
  const [minRating, setMinRating] = useState<number | null>(null);
  const [sort, setSort] = useState<SortKey>("title-asc");
  const [range, setRange] = useState<WindowKey>("7d");
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [simulationChoice, setSimulationChoice] = useState<boolean | null>(null);

  useEffect(() => {
    setPage(1);
  }, [query, stock, minRating, sort, range]);

  const filters: Filters = useMemo(
    () => ({ query, stock, minRating, sort, window: range }),
    [query, stock, minRating, sort, range],
  );
  const simulationAvailable = useMemo(
    () => (data ? hasSimulatedHistory(data.items) : false),
    [data],
  );
  const viewingSimulated =
    (simulationChoice ?? data?.demo.simulationEnabled ?? false) &&
    simulationAvailable;
  const items = useMemo(() => {
    if (!data) return [];
    return viewingSimulated ? data.items : data.items.map(realValues);
  }, [data, viewingSimulated]);
  const filtered = useMemo(
    () => sortItems(filterItems(items, filters), sort, range),
    [items, filters, sort, range],
  );
  const movers = useMemo(() => computeMovers(items, range), [items, range]);
  const pagination = paginate(filtered, page);
  const selectedItem = useMemo(
    () => items.find((item) => item.id === selectedId) ?? null,
    [items, selectedId],
  );
  const closeDrawer = useCallback(() => setSelectedId(null), []);
  const filtersActive =
    query !== "" ||
    stock !== "all" ||
    minRating !== null ||
    sort !== "title-asc" ||
    range !== "7d";

  function resetFilters() {
    setQuery("");
    setStock("all");
    setMinRating(null);
    setSort("title-asc");
    setRange("7d");
  }

  if (loading && !data) {
    return (
      <div className="container">
        <div className="loading-page">
          <div className="spinner" aria-hidden="true" />
          <p>Loading dashboard data…</p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="container">
        <div className="error-page">
          <h2>Dashboard data could not be loaded</h2>
          <p>{error ?? "The data file is missing or malformed."}</p>
          <button type="button" className="btn btn-primary" onClick={reload}>
            <RefreshIcon /> Try again
          </button>
        </div>
      </div>
    );
  }

  const lastRun = data.lastBatch;

  return (
    <div className="container">
      <div className="page-head">
        <div>
          <div className="eyebrow">Books to Scrape · daily monitor</div>
          <h1 className="page-title">Catalogue price intelligence</h1>
          <p className="page-subtitle">
            Every one of the {formatNumber(data.summary.items)} practice books, tracked
            daily by a polite one-request-per-second crawler. Prices marked as simulated
            keep the trend chart useful; the scraped source price sits next to each one.
          </p>
        </div>
        <div className="page-actions">
          <button
            type="button"
            className="btn"
            onClick={() => downloadCsv(filtered, range)}
            disabled={filtered.length === 0}
            title="Download the rows matching the current search and filters"
          >
            <DownloadIcon /> This view ({formatNumber(filtered.length)})
          </button>
          <a
            className="btn"
            href={withBasePath(data.exports.csv)}
            download
          >
            <DownloadIcon /> CSV
          </a>
          <a
            className="btn btn-primary"
            href={withBasePath(data.exports.xlsx)}
            download
          >
            <DownloadIcon /> Excel
          </a>
        </div>
      </div>

      {viewingSimulated ? (
        <div className="banner">
          <span className="banner-icon" aria-hidden="true">
            <AlertIcon />
          </span>
          <div className="banner-body">
            <strong>Simulated price data.</strong> Books to Scrape never changes its
            prices, so each daily run applies a deterministic, bounded movement
            (within ±20%) and flags every affected row. The dashed line on a chart is
            the real scraped price.{" "}
            <Link href="/about#simulation">How the simulation works</Link>
          </div>
          <span className="pill pill-amber banner-action">Demo mode</span>
        </div>
      ) : (
        <div className="banner banner-real">
          <span className="banner-icon banner-icon-real" aria-hidden="true">
            <AlertIcon />
          </span>
          <div className="banner-body">
            <strong>Real scraped prices.</strong> Prices on this practice site are
            static, so charts are flat. Switch <em>Simulated prices</em> back on to see
            labelled demo movement.
          </div>
          <span className="pill pill-blue banner-action">Real view</span>
        </div>
      )}

      <KpiCards
        data={data}
        items={items}
        movers={movers}
        window={range}
        simulatedView={viewingSimulated}
      />

      <div className="toolbar" role="search">
        <div className="search-box">
          <SearchIcon />
          <input
            className="search-input"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={`Search ${formatNumber(data.items.length)} titles…`}
            aria-label="Search titles"
          />
        </div>

        <div className="control">
          <label className="control-label" htmlFor="stock-filter">
            Stock
          </label>
          <select
            id="stock-filter"
            className="select"
            value={stock}
            onChange={(event) => setStock(event.target.value as StockFilter)}
          >
            <option value="all">All</option>
            <option value="in">In stock</option>
            <option value="out">Out of stock</option>
          </select>
        </div>

        <div className="control">
          <label className="control-label" htmlFor="rating-filter">
            Rating
          </label>
          <select
            id="rating-filter"
            className="select"
            value={minRating ?? "all"}
            onChange={(event) =>
              setMinRating(event.target.value === "all" ? null : Number(event.target.value))
            }
          >
            <option value="all">Any</option>
            <option value="4">4+ stars</option>
            <option value="3">3+ stars</option>
          </select>
        </div>

        <div className="control">
          <label className="control-label" htmlFor="window-filter">
            Change
          </label>
          <select
            id="window-filter"
            className="select"
            value={range}
            onChange={(event) => setRange(event.target.value as WindowKey)}
          >
            {WINDOWS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div className="control">
          <label className="control-label" htmlFor="sort-filter">
            Sort
          </label>
          <select
            id="sort-filter"
            className="select"
            value={sort}
            onChange={(event) => setSort(event.target.value as SortKey)}
          >
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <label className="toggle" title="Switch between simulated and real scraped values">
          <input
            type="checkbox"
            checked={viewingSimulated}
            disabled={!simulationAvailable}
            onChange={(event) => setSimulationChoice(event.target.checked)}
            aria-label="Show simulated price movement"
          />
          <span className="toggle-track" aria-hidden="true">
            <span className="toggle-thumb" />
          </span>
          <span className="toggle-text">Simulated prices</span>
        </label>

        <div className="toolbar-spacer" />
        {filtersActive && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={resetFilters}>
            Reset
          </button>
        )}
      </div>

      <div className="dashboard-grid">
        <section className="panel" aria-labelledby="catalogue-title">
          <div className="panel-header">
            <div>
              <h2 className="panel-title" id="catalogue-title">
                Catalogue
              </h2>
              <p className="panel-sub">
                {formatNumber(filtered.length)} matched · {formatWindow(range)} change
                {lastRun?.finishedAt && ` · updated ${formatDate(lastRun.finishedAt)}`}
              </p>
            </div>
            <span className="pill pill-neutral">{formatNumber(data.items.length)} total</span>
          </div>

          {pagination.rows.length === 0 ? (
            <div className="empty">
              <span className="empty-icon">
                <SearchIcon />
              </span>
              <h3>No titles match these filters</h3>
              <p>Try a shorter search term, a wider rating, or reset the filters.</p>
              <button type="button" className="btn" onClick={resetFilters}>
                Reset filters
              </button>
            </div>
          ) : (
            <>
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th scope="col">Book</th>
                      <th scope="col">Price</th>
                      <th scope="col">Change</th>
                      <th scope="col">Trend</th>
                      <th scope="col">Stock</th>
                      <th scope="col" aria-label="Open details" />
                    </tr>
                  </thead>
                  <tbody>
                    {pagination.rows.map((item) => {
                      const change = changeForWindow(item, range);
                      return (
                        <tr
                          key={item.id}
                          className="clickable"
                          tabIndex={0}
                          onClick={() => setSelectedId(item.id)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              setSelectedId(item.id);
                            }
                          }}
                          aria-label={`Open details for ${item.title}`}
                        >
                          <td>
                            <div className="book-cell">
                              <BookCover title={item.title} />
                              <div>
                                <div className="book-title">{item.title}</div>
                                <div className="book-meta">
                                  <Rating value={item.rating} />
                                  <span>·</span>
                                  <span>{item.currency}</span>
                                  <span className={`stock mobile-stock${item.inStock ? "" : " out"}`}>
                                    <span className="stock-dot" />
                                    {item.inStock ? "In stock" : "Out"}
                                  </span>
                                  {lastRun && item.lastSeenAt < lastRun.startedAt && (
                                    <span
                                      className="stale-flag"
                                      title="This title was not seen in the latest run"
                                    >
                                      stale
                                    </span>
                                  )}
                                </div>
                              </div>
                            </div>
                          </td>
                          <td>
                            <div className="price-cell">
                              <div className="price-strong">
                                {formatMoney(item.price, item.currency)}
                              </div>
                              <div className="price-source">
                                source {formatMoney(item.sourcePrice, item.currency)}
                              </div>
                            </div>
                          </td>
                          <td>
                            <ChangePill change={change} currency={item.currency} />
                          </td>
                          <td>
                            <Sparkline history={item.history} />
                          </td>
                          <td>
                            <span className={`stock${item.inStock ? "" : " out"}`}>
                              <span className="stock-dot" />
                              {item.inStock ? "In stock" : "Out"}
                              {!item.inStock && item.simulated && (
                                <span className="sim">sim</span>
                              )}
                            </span>
                          </td>
                          <td>
                            <span className="row-arrow">
                              <ArrowRightIcon />
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className="pagination">
                <span className="page-info">
                  {pagination.start + 1}–
                  {Math.min(
                    pagination.start + pagination.rows.length,
                    filtered.length,
                  )}{" "}
                  of {formatNumber(filtered.length)}
                </span>
                <div className="page-buttons">
                  <button
                    type="button"
                    className="page-btn"
                    onClick={() => setPage(pagination.page - 1)}
                    disabled={pagination.page <= 1}
                    aria-label="Previous page"
                  >
                    ‹
                  </button>
                  {pageList(pagination.page, pagination.pageCount).map((entry, index) =>
                    entry === "ellipsis" ? (
                      <span className="page-btn" key={`gap-${index}`} aria-hidden="true">
                        …
                      </span>
                    ) : (
                      <button
                        type="button"
                        key={entry}
                        className={`page-btn${pagination.page === entry ? " active" : ""}`}
                        onClick={() => setPage(entry)}
                        aria-current={pagination.page === entry ? "page" : undefined}
                      >
                        {entry}
                      </button>
                    ),
                  )}
                  <button
                    type="button"
                    className="page-btn"
                    onClick={() => setPage(pagination.page + 1)}
                    disabled={pagination.page >= pagination.pageCount}
                    aria-label="Next page"
                  >
                    ›
                  </button>
                </div>
              </div>
            </>
          )}
        </section>

        <aside className="aside-stack">
          <MoversPanel
            movers={movers}
            window={range}
            onSelect={(item) => setSelectedId(item.id)}
          />
          <RunSummary batch={data.lastBatch} />
          <section className="panel">
            <div className="panel-header">
              <div>
                <h2 className="panel-title">Exports</h2>
                <p className="panel-sub">Generated with the last scrape</p>
              </div>
            </div>
            <div className="panel-body stack-8">
              <a
                className="btn"
                href={withBasePath(data.exports.csv)}
                download
                title="Full latest snapshot; simulated rows are flagged"
              >
                <DownloadIcon /> All rows · CSV
              </a>
              <a
                className="btn"
                href={withBasePath(data.exports.xlsx)}
                download
                title="Items, history, and recent batches; simulated rows are flagged"
              >
                <DownloadIcon /> All rows + history · Excel
              </a>
              <a
                className="btn"
                href={withBasePath(data.exports.historyCsv)}
                download
                title="Daily price history; simulated rows are flagged"
              >
                <DownloadIcon /> All price history · CSV
              </a>
              <button
                type="button"
                className="btn"
                onClick={() => downloadCsv(filtered, range)}
                disabled={filtered.length === 0}
              >
                <DownloadIcon /> This view · CSV ({formatNumber(filtered.length)})
              </button>
              <p className="exports-note">
                Full files include simulated rows, each flagged in the data. “This
                view” exports exactly what the switch and filters show. CSV files open
                cleanly in Excel and Numbers.
              </p>
            </div>
          </section>
        </aside>
      </div>

      {selectedItem && (
        <DetailDrawer
          item={selectedItem}
          range={range}
          onClose={closeDrawer}
        />
      )}
    </div>
  );
}
