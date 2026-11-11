export type WindowKey = "1d" | "7d" | "30d" | "all";

export interface HistoryPoint {
  date: string;
  price: number | null;
  sourcePrice: number | null;
  simulated: boolean;
  inStock: boolean;
  sourceInStock: boolean;
}

export interface Item {
  id: string;
  title: string;
  url: string;
  category: string | null;
  rating: number | null;
  currency: string;
  price: number | null;
  sourcePrice: number | null;
  inStock: boolean;
  stockText: string;
  sourceInStock: boolean;
  simulated: boolean;
  firstSeenAt: string;
  lastSeenAt: string;
  history: HistoryPoint[];
}

export interface Batch {
  id: number;
  kind: "scrape" | "backfill";
  mode: "real" | "simulated";
  status: "success" | "partial" | "failed";
  startedAt: string;
  finishedAt: string | null;
  pages: number;
  itemsSeen: number;
  itemsNew: number;
  itemsUpdated: number;
  priceChanges: number;
  stockChanges: number;
  errorCount: number;
  notes: string | null;
}

export interface ScrapeError {
  batchId: number;
  url: string;
  kind: string;
  message: string;
  occurredAt: string;
}

export interface DashboardData {
  schemaVersion: number;
  generatedAt: string;
  source: { key: string; name: string; url: string; note: string };
  demo: {
    simulationEnabled: boolean;
    simulatedItems: number;
    backfilledBatches: number;
    note: string;
  };
  summary: {
    items: number;
    inStock: number;
    outOfStock: number;
    averagePrice: number | null;
    currency: string;
    batches: number;
    backfillBatches: number;
    errors: number;
    historyDays: number;
  };
  lastBatch: Batch | null;
  batches: Batch[];
  errors: ScrapeError[];
  items: Item[];
  exports: { csv: string; xlsx: string; historyCsv: string };
}

export type StockFilter = "all" | "in" | "out";

export type SortKey =
  | "title-asc"
  | "price-asc"
  | "price-desc"
  | "change-desc"
  | "change-asc"
  | "rating-desc";

export interface Filters {
  query: string;
  stock: StockFilter;
  minRating: number | null;
  sort: SortKey;
  window: WindowKey;
}
