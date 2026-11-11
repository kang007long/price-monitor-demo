"use client";

import { useState } from "react";

import type { Mover, Movers } from "@/lib/filters";
import {
  formatMoney,
  formatNumber,
  formatPercent,
  formatWindow,
} from "@/lib/format";
import type { Item, WindowKey } from "@/lib/types";
import { BookCover } from "./BookCover";

export function MoversPanel({
  movers,
  window,
  onSelect,
}: {
  movers: Movers;
  window: WindowKey;
  onSelect: (item: Item) => void;
}) {
  const [tab, setTab] = useState<"gainers" | "losers">("gainers");
  const rows: Mover[] = tab === "gainers" ? movers.gainers : movers.losers;
  const maxAbs = Math.max(0.01, ...rows.map((row) => Math.abs(row.pct)));

  return (
    <section className="panel" aria-labelledby="movers-title">
      <div className="movers-head">
        <div>
          <h2 className="panel-title" id="movers-title">
            Biggest movers
          </h2>
          <p className="panel-sub">{formatWindow(window)} change</p>
        </div>
        <div className="segmented" role="tablist" aria-label="Mover direction">
          <button
            type="button"
            role="tab"
            aria-selected={tab === "gainers"}
            className={tab === "gainers" ? "active" : ""}
            onClick={() => setTab("gainers")}
          >
            Up {movers.upCount}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "losers"}
            className={tab === "losers" ? "active" : ""}
            onClick={() => setTab("losers")}
          >
            Down {movers.downCount}
          </button>
        </div>
      </div>

      {rows.length === 0 ? (
        <div className="mover-empty">
          No {tab === "gainers" ? "increases" : "decreases"} in this window.
        </div>
      ) : (
        <div className="mover-list">
          {rows.map((row, index) => (
            <button
              type="button"
              className="mover-row"
              key={row.item.id}
              onClick={() => onSelect(row.item)}
              title={`${row.item.title} · ${formatPercent(row.pct)}`}
            >
              <span className="mover-rank">{index + 1}</span>
              <BookCover title={row.item.title} />
              <span className="mover-info">
                <span className="mover-title">{row.item.title}</span>
                <span className="mover-meta">
                  {formatMoney(row.item.price, row.item.currency)}
                  <span className="mover-bar-track" aria-hidden="true">
                    <span
                      className={`mover-bar-fill ${row.pct >= 0 ? "up" : "down"}`}
                      style={{
                        width: `${Math.max(
                          8,
                          (Math.abs(row.pct) / maxAbs) * 100,
                        )}%`,
                      }}
                    />
                  </span>
                </span>
              </span>
              <span className={`mover-pct ${row.pct >= 0 ? "up" : "down"}`}>
                {formatPercent(row.pct)}
              </span>
            </button>
          ))}
        </div>
      )}

      <div className="movers-footer">
        <span>
          {formatNumber(movers.upCount)} up · {formatNumber(movers.downCount)} down
        </span>
        <span>{formatNumber(movers.flatCount)} flat</span>
      </div>
    </section>
  );
}
