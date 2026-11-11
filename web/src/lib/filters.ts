import type { Batch, Filters, HistoryPoint, Item, WindowKey } from "./types";

export const PAGE_SIZE = 20;

export interface ChangeResult {
  change: number;
  pct: number;
  latest: HistoryPoint;
  baseline: HistoryPoint;
}

function addDays(isoDate: string, days: number): string {
  const date = new Date(`${isoDate}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

/** Latest price compared with an earlier observation in the chosen window. */
export function changeForWindow(
  item: Item,
  window: WindowKey,
): ChangeResult | null {
  const history = item.history;
  if (history.length < 2) return null;
  const latest = history[history.length - 1];
  if (latest.price === null) return null;

  let baseline: HistoryPoint | undefined;
  if (window === "1d") {
    baseline = history[history.length - 2];
  } else if (window === "all") {
    baseline = history[0];
  } else {
    const days = window === "7d" ? 7 : 30;
    const cutoff = addDays(latest.date, -(days - 1));
    baseline = history.find((point) => point.date >= cutoff);
    if (!baseline) baseline = history[0];
  }

  if (!baseline || baseline.price === null || baseline.date === latest.date) {
    return null;
  }
  const change = latest.price - baseline.price;
  const pct = baseline.price > 0 ? (change / baseline.price) * 100 : 0;
  return { change, pct, latest, baseline };
}

export function filterItems(items: Item[], filters: Filters): Item[] {
  const query = filters.query.trim().toLowerCase();
  return items.filter((item) => {
    if (query && !item.title.toLowerCase().includes(query)) return false;
    if (filters.stock === "in" && !item.inStock) return false;
    if (filters.stock === "out" && item.inStock) return false;
    if (filters.minRating !== null && (item.rating ?? 0) < filters.minRating) {
      return false;
    }
    return true;
  });
}

export function sortItems(
  items: Item[],
  sort: Filters["sort"],
  window: WindowKey,
): Item[] {
  const sorted = [...items];
  const changeOf = (item: Item) => changeForWindow(item, window)?.pct ?? null;
  switch (sort) {
    case "title-asc":
      sorted.sort((a, b) => a.title.localeCompare(b.title));
      break;
    case "price-asc":
      sorted.sort((a, b) => (a.price ?? Infinity) - (b.price ?? Infinity));
      break;
    case "price-desc":
      sorted.sort((a, b) => (b.price ?? -Infinity) - (a.price ?? -Infinity));
      break;
    case "rating-desc":
      sorted.sort(
        (a, b) => (b.rating ?? 0) - (a.rating ?? 0) || a.title.localeCompare(b.title),
      );
      break;
    case "change-desc":
    case "change-asc": {
      const direction = sort === "change-desc" ? -1 : 1;
      sorted.sort((a, b) => {
        const av = changeOf(a);
        const bv = changeOf(b);
        if (av === null && bv === null) return a.title.localeCompare(b.title);
        if (av === null) return 1;
        if (bv === null) return -1;
        return (av - bv) * direction;
      });
      break;
    }
  }
  return sorted;
}

export interface Mover {
  item: Item;
  change: number;
  pct: number;
}

export interface Movers {
  gainers: Mover[];
  losers: Mover[];
  upCount: number;
  downCount: number;
  flatCount: number;
  withHistory: number;
}

export function computeMovers(
  items: Item[],
  window: WindowKey,
  limit = 5,
): Movers {
  const movers: Mover[] = [];
  let flatCount = 0;
  for (const item of items) {
    const result = changeForWindow(item, window);
    if (!result) continue;
    if (Math.abs(result.change) < 0.005) {
      flatCount += 1;
      continue;
    }
    movers.push({ item, change: result.change, pct: result.pct });
  }
  const gainers = movers
    .filter((mover) => mover.change > 0)
    .sort((a, b) => b.pct - a.pct)
    .slice(0, limit);
  const losers = movers
    .filter((mover) => mover.change < 0)
    .sort((a, b) => a.pct - b.pct)
    .slice(0, limit);
  return {
    gainers,
    losers,
    upCount: movers.filter((mover) => mover.change > 0).length,
    downCount: movers.filter((mover) => mover.change < 0).length,
    flatCount,
    withHistory: movers.length + flatCount,
  };
}

export function paginate<T>(items: T[], page: number, pageSize = PAGE_SIZE) {
  const pageCount = Math.max(1, Math.ceil(items.length / pageSize));
  const safePage = Math.min(Math.max(1, page), pageCount);
  const start = (safePage - 1) * pageSize;
  return {
    page: safePage,
    pageCount,
    start,
    rows: items.slice(start, start + pageSize),
  };
}

export interface SparkPaths {
  line: string;
  area: string;
}

/** Compact SVG path for a 30-day sparkline (no external chart dependency). */
export function sparklinePaths(
  history: HistoryPoint[],
  width = 96,
  height = 30,
  points = 14,
): SparkPaths {
  const values = history
    .slice(-points)
    .map((point) => point.price)
    .filter((price): price is number => price !== null);
  if (values.length < 2) return { line: "", area: "" };
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const step = width / (values.length - 1);
  const coords = values.map((value, index) => {
    const x = index * step;
    const y = height - 2 - ((value - min) / span) * (height - 4);
    return [x, y] as const;
  });
  const line = coords
    .map(([x, y], index) => `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`)
    .join(" ");
  const area = `${line} L${width},${height} L0,${height} Z`;
  return { line, area };
}

/** Map an item to its real scraped values (used by the UI simulation switch). */
export function realValues(item: Item): Item {
  return {
    ...item,
    price: item.sourcePrice,
    inStock: item.sourceInStock,
    stockText: item.sourceInStock ? "In stock" : "Out of stock",
    simulated: false,
    history: item.history.map((point) => ({
      ...point,
      price: point.sourcePrice,
      inStock: point.sourceInStock,
      simulated: false,
    })),
  };
}

export function hasSimulatedHistory(items: Item[]): boolean {
  return items.some((item) => item.history.some((point) => point.simulated));
}

export function batchDuration(batch: Batch): string {
  if (!batch.finishedAt) return "running";
  const start = new Date(batch.startedAt).getTime();
  const end = new Date(batch.finishedAt).getTime();
  if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return "—";
  const seconds = Math.round((end - start) / 1000);
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}
