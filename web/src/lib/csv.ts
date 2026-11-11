import { changeForWindow } from "./filters";
import type { Item, WindowKey } from "./types";

const FORMULA_PREFIX = /^[=+\-@\t\r]/;

/** Neutralise text that spreadsheet apps would otherwise execute as a formula. */
export function excelSafe(value: unknown): string {
  if (value === null || value === undefined) return "";
  const text = String(value);
  return FORMULA_PREFIX.test(text) ? `'${text}` : text;
}

export function csvEscape(value: unknown): string {
  const text = excelSafe(value);
  if (/[",\n\r]/.test(text)) {
    return `"${text.replaceAll('"', '""')}"`;
  }
  return text;
}

/** Filtered-table CSV export, generated in the browser. */
export function toCsv(items: Item[], window: WindowKey): string {
  const headers = [
    "title",
    "rating",
    "price",
    "source_price",
    "currency",
    "change",
    "change_pct",
    "window",
    "in_stock",
    "simulated",
    "url",
  ];
  const lines = [headers.join(",")];
  for (const item of items) {
    const change = changeForWindow(item, window);
    lines.push(
      [
        csvEscape(item.title),
        item.rating ?? "",
        item.price?.toFixed(2) ?? "",
        item.sourcePrice?.toFixed(2) ?? "",
        csvEscape(item.currency),
        change?.change.toFixed(2) ?? "",
        change?.pct.toFixed(2) ?? "",
        csvEscape(window),
        item.inStock ? "yes" : "no",
        item.simulated ? "yes" : "no",
        csvEscape(item.url),
      ].join(","),
    );
  }
  return `${lines.join("\n")}\n`;
}

export function downloadCsv(items: Item[], window: WindowKey): void {
  const csv = `\ufeff${toCsv(items, window)}`;
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `price-monitor-filtered-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
