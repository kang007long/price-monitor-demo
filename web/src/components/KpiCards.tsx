import type { Movers } from "@/lib/filters";
import { formatMoney, formatNumber, formatShortDate, formatWindow } from "@/lib/format";
import type { DashboardData, Item, WindowKey } from "@/lib/types";
import {
  ActivityIcon,
  ArrowDownIcon,
  ArrowUpIcon,
  BookIcon,
  BoxIcon,
  ClockIcon,
  CoinsIcon,
} from "./Icons";

export function KpiCards({
  data,
  items,
  movers,
  window,
  simulatedView,
}: {
  data: DashboardData;
  items: Item[];
  movers: Movers;
  window: WindowKey;
  simulatedView: boolean;
}) {
  const { summary, lastBatch } = data;
  const priced = items
    .map((item) => item.price)
    .filter((price): price is number => price !== null);
  const average = priced.length
    ? priced.reduce((total, price) => total + price, 0) / priced.length
    : null;
  const inStock = items.filter((item) => item.inStock).length;
  const lastTime = lastBatch?.finishedAt
    ? new Date(lastBatch.finishedAt).toISOString().slice(11, 16)
    : "—";

  return (
    <div className="kpi-grid">
      <div className="kpi-card">
        <div className="kpi-label">
          <BookIcon /> Tracked titles
        </div>
        <div className="kpi-value">{formatNumber(summary.items)}</div>
        <div className="kpi-sub">
          {lastBatch?.pages ?? 0} catalogue pages · {summary.historyDays} days of history
        </div>
      </div>

      <div className="kpi-card">
        <div className="kpi-label">
          <BoxIcon /> In stock
        </div>
        <div className="kpi-value">
          {formatNumber(inStock)}
          <small> / {formatNumber(items.length)}</small>
        </div>
        <div className="kpi-sub">
          {items.length - inStock} unavailable ·{" "}
          {simulatedView ? (
            <span className="simulated-count">
              {data.demo.simulatedItems} simulated
            </span>
          ) : (
            "real scraped values"
          )}
        </div>
      </div>

      <div className="kpi-card">
        <div className="kpi-label">
          <CoinsIcon /> Average price
        </div>
        <div className="kpi-value">{formatMoney(average, summary.currency)}</div>
        <div className="kpi-sub">Across {formatNumber(priced.length)} priced titles</div>
      </div>

      <div className="kpi-card">
        <div className="kpi-label">
          <ActivityIcon /> Movers · {formatWindow(window)}
        </div>
        <div className="kpi-value">
          <span className="up">
            <ArrowUpIcon className="kpi-arrow-icon" />{" "}
            {formatNumber(movers.upCount)}
          </span>
          <small> / </small>
          <span className="down">
            <ArrowDownIcon className="kpi-arrow-icon" />{" "}
            {formatNumber(movers.downCount)}
          </span>
        </div>
        <div className="kpi-sub">
          {movers.flatCount} unchanged · {movers.withHistory} with history
        </div>
      </div>

      <div className="kpi-card">
        <div className="kpi-label">
          <ClockIcon /> Last scrape
        </div>
        <div className="kpi-value">
          {lastBatch?.finishedAt
            ? formatShortDate(lastBatch.finishedAt.slice(0, 10))
            : "—"}
        </div>
        <div className="kpi-sub">
          {lastBatch?.finishedAt ? `${lastTime} UTC` : "No runs yet"} ·{" "}
          {formatNumber(lastBatch?.itemsSeen ?? 0)} items
        </div>
      </div>
    </div>
  );
}
