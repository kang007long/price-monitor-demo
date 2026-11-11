"use client";

import { useEffect, useRef } from "react";

import { changeForWindow } from "@/lib/filters";
import {
  formatDate,
  formatMoney,
  formatPercent,
  formatSignedMoney,
  formatWindow,
} from "@/lib/format";
import type { Item, WindowKey } from "@/lib/types";
import { BookCover } from "./BookCover";
import { ChangePill } from "./ChangePill";
import { ExternalIcon, CloseIcon } from "./Icons";
import { PriceChart } from "./PriceChart";
import { Rating } from "./Rating";

interface Props {
  item: Item;
  range: WindowKey;
  onClose: () => void;
}

export function DetailDrawer({ item, range, onClose }: Props) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const change = changeForWindow(item, range);
  const history = [...item.history].reverse().slice(0, 12);

  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  return (
    <div
      className="drawer-overlay"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <aside
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="detail-title"
      >
        <header className="drawer-header">
          <div className="drawer-heading">
            <h2 className="drawer-title" id="detail-title">
              {item.title}
            </h2>
            <div className="drawer-sub">
              <Rating value={item.rating} />
              <span>·</span>
              <span>{item.history.length} daily observations</span>
              {item.simulated && <span className="pill pill-amber">Simulated</span>}
            </div>
          </div>
          <button
            type="button"
            className="drawer-close"
            onClick={onClose}
            aria-label="Close details"
            ref={closeRef}
          >
            <CloseIcon />
          </button>
        </header>

        <div className="drawer-body">
          <div className="drawer-hero">
            <BookCover title={item.title} size="large" />
            <div>
              <div className="drawer-price">{formatMoney(item.price, item.currency)}</div>
              <div className="drawer-price-row">
                <ChangePill change={change} currency={item.currency} />
                <span className="pill pill-neutral">{formatWindow(range)}</span>
              </div>
              <div className="drawer-source">
                Scraped source price: {formatMoney(item.sourcePrice, item.currency)}
              </div>
            </div>
          </div>

          <div className="detail-stats">
            <div className="detail-stat">
              <div className="detail-stat-label">Change</div>
              <div className="detail-stat-value">
                {change
                  ? `${formatSignedMoney(change.change, item.currency)} (${formatPercent(
                      change.pct,
                    )})`
                  : "—"}
              </div>
            </div>
            <div className="detail-stat">
              <div className="detail-stat-label">Stock</div>
              <div className="detail-stat-value">
                {item.inStock ? "In stock" : "Out of stock"}
                {item.simulated && item.inStock !== item.sourceInStock && (
                  <span className="sim-text"> · simulated</span>
                )}
              </div>
            </div>
            <div className="detail-stat">
              <div className="detail-stat-label">Last seen</div>
              <div className="detail-stat-value">{formatDate(item.lastSeenAt)}</div>
            </div>
          </div>

          <div className="chart-card">
            <div className="chart-head">
              <div className="chart-title">Price history</div>
              <div className="chart-legend">
                <span className="legend-item">
                  <span className="legend-swatch" /> Displayed price
                </span>
                <span className="legend-item">
                  <span className="legend-swatch dashed" /> Scraped price
                </span>
              </div>
            </div>
            <PriceChart points={item.history} currency={item.currency} />
          </div>

          <div className="history-head">
            <div className="history-title">Recent observations</div>
            <span className="pill pill-neutral">{formatWindow(range)} change</span>
          </div>
          <table className="history-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Price</th>
                <th>Source</th>
                <th>Stock</th>
              </tr>
            </thead>
            <tbody>
              {history.map((point) => (
                <tr key={point.date}>
                  <td>{formatDate(point.date)}</td>
                  <td>
                    {formatMoney(point.price, item.currency)}
                    {point.simulated && (
                      <span className="sim-text"> *</span>
                    )}
                  </td>
                  <td className="history-source">
                    {formatMoney(point.sourcePrice, item.currency)}
                  </td>
                  <td>{point.inStock ? "In" : "Out"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="drawer-footnote">
            * Synthetic price for the demo. The scraped source price never changes on
            this practice site.
          </p>

          <a
            className="drawer-link"
            href={item.url}
            target="_blank"
            rel="noreferrer noopener"
          >
            View the product on books.toscrape.com <ExternalIcon className="icon-sm" />
          </a>
        </div>
      </aside>
    </div>
  );
}
