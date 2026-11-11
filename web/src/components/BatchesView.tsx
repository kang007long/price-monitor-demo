"use client";

import Link from "next/link";

import { batchDuration } from "@/lib/filters";
import { formatDateTime, formatNumber } from "@/lib/format";
import { useDashboard } from "@/lib/useDashboard";
import { AlertIcon, CheckIcon, DownloadIcon, RefreshIcon } from "@/components/Icons";

export function BatchesView() {
  const { data, error, loading, reload } = useDashboard();

  if (loading && !data) {
    return (
      <div className="container">
        <div className="loading-page">
          <div className="spinner" aria-hidden="true" />
          <p>Loading scrape history…</p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="container">
        <div className="error-page">
          <h2>Scrape history could not be loaded</h2>
          <p>{error ?? "The data file is missing or malformed."}</p>
          <button type="button" className="btn btn-primary" onClick={reload}>
            <RefreshIcon /> Try again
          </button>
        </div>
      </div>
    );
  }

  const successCount = data.batches.filter((batch) => batch.status === "success").length;
  const scrapeCount = data.summary.batches;
  const errors = data.errors;

  return (
    <div className="container">
      <div className="page-head">
        <div>
          <div className="eyebrow">Operations</div>
          <h1 className="page-title">Every batch, on the record</h1>
          <p className="page-subtitle">
            Each run is stored as a batch, including pages fetched, new and updated
            items, detected changes, and every error. A failed page never discards the
            pages that already succeeded, and the crawler skips to the next page when
            the pagination pattern allows (the batch is marked partial).
          </p>
        </div>
        <div className="page-actions">
          <Link className="btn" href="/">
            Back to dashboard
          </Link>
        </div>
      </div>

      <div className="batch-summary">
        <div className="kpi-card">
          <div className="kpi-label">Scrape batches</div>
          <div className="kpi-value">{formatNumber(scrapeCount)}</div>
          <div className="kpi-sub">{successCount} recent runs fully successful</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Last items seen</div>
          <div className="kpi-value">{formatNumber(data.lastBatch?.itemsSeen ?? 0)}</div>
          <div className="kpi-sub">Across {data.lastBatch?.pages ?? 0} catalogue pages</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Errors recorded</div>
          <div className="kpi-value">{formatNumber(data.summary.errors)}</div>
          <div className="kpi-sub">Fetch, parse, robots, and storage issues</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Synthetic days</div>
          <div className="kpi-value">{formatNumber(data.demo.backfilledBatches)}</div>
          <div className="kpi-sub">Labelled demo history, no HTTP requests</div>
        </div>
      </div>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Recent batches</h2>
            <p className="panel-sub">
              Newest first · times in UTC · {data.demo.backfilledBatches} backfill batches
              are synthetic
            </p>
          </div>
          <span className="pill pill-neutral">{data.batches.length} shown</span>
        </div>
        <div className="table-scroll">
          <table className="batch-table">
            <thead>
              <tr>
                <th scope="col">Batch</th>
                <th scope="col">Kind</th>
                <th scope="col">Mode</th>
                <th scope="col">Status</th>
                <th scope="col">Started</th>
                <th scope="col">Pages</th>
                <th scope="col">Items</th>
                <th scope="col">Price Δ</th>
                <th scope="col">Errors</th>
                <th scope="col">Note</th>
              </tr>
            </thead>
            <tbody>
              {data.batches.map((batch) => (
                <tr key={batch.id}>
                  <td>
                    <div className="batch-id">#{batch.id}</div>
                    <div className="price-source">{batchDuration(batch)}</div>
                  </td>
                  <td>{batch.kind === "backfill" ? "Backfill" : "Scrape"}</td>
                  <td>
                    <span className={`mode ${batch.mode}`}>{batch.mode}</span>
                  </td>
                  <td>
                    <span className={`status ${batch.status}`}>{batch.status}</span>
                  </td>
                  <td className="num batch-started">
                    {formatDateTime(batch.startedAt)}
                  </td>
                  <td className="num">{formatNumber(batch.pages)}</td>
                  <td className="num">
                    {formatNumber(batch.itemsSeen)}
                    {batch.itemsNew > 0 && (
                      <span className="price-source"> ({batch.itemsNew} new)</span>
                    )}
                  </td>
                  <td className="num">{formatNumber(batch.priceChanges)}</td>
                  <td className="num">
                    {batch.errorCount > 0 ? (
                      <span className="batch-errors">
                        {batch.errorCount}
                      </span>
                    ) : (
                      "0"
                    )}
                  </td>
                  <td className="batch-note">
                    {batch.notes ??
                      (batch.kind === "backfill"
                        ? "Synthetic history"
                        : "Daily scheduled scrape")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel panel-spaced">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Error log</h2>
            <p className="panel-sub">The last 50 recorded problems across recent batches</p>
          </div>
          {errors.length === 0 ? (
            <span className="pill pill-green">
              <CheckIcon className="icon-xs" /> Clean
            </span>
          ) : (
            <span className="pill pill-amber">
              <AlertIcon className="icon-xs" /> {errors.length}
            </span>
          )}
        </div>
        {errors.length === 0 ? (
          <div className="empty compact">
            <span className="empty-icon empty-icon-success">
              <CheckIcon />
            </span>
            <h3>No errors recorded</h3>
            <p>
              Every request in the stored batches completed and every page parsed. Errors
              would appear here with their batch, URL, and message.
            </p>
          </div>
        ) : (
          <div>
            {errors.map((item, index) => (
              <div className="error-item" key={`${item.batchId}-${index}`}>
                <div className="error-head">
                  <span className="pill pill-neutral">Batch #{item.batchId}</span>
                  <span className={`status ${item.kind === "fetch" ? "partial" : "failed"}`}>
                    {item.kind}
                  </span>
                  <span>{formatDateTime(item.occurredAt)}</span>
                </div>
                <div className="error-message">{item.message}</div>
                {item.url && <div className="error-url">{item.url}</div>}
              </div>
            ))}
          </div>
        )}
      </section>

      <p className="batch-footer-note">
        <DownloadIcon className="icon-xs icon-inline" />
        Batch-level details are also included in the Excel export on the dashboard.
      </p>
    </div>
  );
}
