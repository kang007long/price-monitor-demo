import { describe, expect, it } from "vitest";

import {
  changeForWindow,
  computeMovers,
  filterItems,
  hasSimulatedHistory,
  paginate,
  realValues,
  sortItems,
  sparklinePaths,
} from "@/lib/filters";
import type { HistoryPoint, Item } from "@/lib/types";

function points(values: [string, number][]): HistoryPoint[] {
  return values.map(([date, price]) => ({
    date,
    price,
    sourcePrice: 10,
    simulated: true,
    inStock: true,
    sourceInStock: true,
  }));
}

function item(overrides: Partial<Item> = {}): Item {
  return {
    id: "book-1",
    title: "A Book",
    url: "https://books.toscrape.com/catalogue/book-1/index.html",
    category: null,
    rating: 4,
    currency: "GBP",
    price: 10,
    sourcePrice: 10,
    inStock: true,
    stockText: "In stock",
    sourceInStock: true,
    simulated: true,
    firstSeenAt: "2026-11-05T06:00:00+00:00",
    lastSeenAt: "2026-11-11T06:00:00+00:00",
    history: points([
      ["2026-11-05", 8],
      ["2026-11-06", 9],
      ["2026-11-07", 9.5],
      ["2026-11-08", 9.6],
      ["2026-11-09", 9.7],
      ["2026-11-10", 9.8],
      ["2026-11-11", 10],
    ]),
    ...overrides,
  };
}

describe("changeForWindow", () => {
  it("compares against the previous observation for 1 day", () => {
    const result = changeForWindow(item(), "1d");
    expect(result?.baseline.date).toBe("2026-11-10");
    expect(result?.change).toBeCloseTo(0.2, 5);
  });

  it("uses the first point inside a 7-day window", () => {
    const result = changeForWindow(item(), "7d");
    expect(result?.baseline.date).toBe("2026-11-05");
    expect(result?.change).toBeCloseTo(2, 5);
    expect(result?.pct).toBeCloseTo(25, 5);
  });

  it("falls back to the first point for 30 days and all history", () => {
    expect(changeForWindow(item(), "30d")?.baseline.date).toBe("2026-11-05");
    expect(changeForWindow(item(), "all")?.baseline.date).toBe("2026-11-05");
  });

  it("returns null when there is not enough history", () => {
    expect(changeForWindow(item({ history: [] }), "7d")).toBeNull();
    expect(
      changeForWindow(
        item({ history: points([["2026-11-11", 10]]) }),
        "1d",
      ),
    ).toBeNull();
  });
});

describe("filterItems", () => {
  const items = [
    item({ id: "1", title: "Alpha Guide", price: 5, rating: 5, inStock: true }),
    item({ id: "2", title: "Beta Novel", price: 15, rating: 3, inStock: false }),
    item({ id: "3", title: "Gamma Atlas", price: 25, rating: 4, inStock: true }),
  ];
  const base = {
    query: "",
    stock: "all" as const,
    minRating: null,
    sort: "title-asc" as const,
    window: "7d" as const,
  };

  it("matches title text case-insensitively", () => {
    expect(filterItems(items, { ...base, query: "beta" }).map((entry) => entry.id)).toEqual([
      "2",
    ]);
  });

  it("filters by stock and minimum rating", () => {
    expect(filterItems(items, { ...base, stock: "in" }).map((entry) => entry.id)).toEqual([
      "1",
      "3",
    ]);
    expect(filterItems(items, { ...base, stock: "out" }).map((entry) => entry.id)).toEqual([
      "2",
    ]);
    expect(
      filterItems(items, { ...base, minRating: 4 }).map((entry) => entry.id),
    ).toEqual(["1", "3"]);
  });
});

describe("sortItems", () => {
  it("sorts by price in both directions", () => {
    const items = [item({ id: "a", price: 20 }), item({ id: "b", price: 5 })];
    expect(sortItems(items, "price-asc", "7d").map((entry) => entry.id)).toEqual([
      "b",
      "a",
    ]);
    expect(sortItems(items, "price-desc", "7d").map((entry) => entry.id)).toEqual([
      "a",
      "b",
    ]);
  });

  it("puts items without history last when sorting by change", () => {
    const items = [
      item({ id: "none", history: [] }),
      item({ id: "up", history: points([["2026-11-10", 10], ["2026-11-11", 12]]) }),
      item({ id: "down", history: points([["2026-11-10", 10], ["2026-11-11", 8]]) }),
    ];
    expect(sortItems(items, "change-desc", "1d").map((entry) => entry.id)).toEqual([
      "up",
      "down",
      "none",
    ]);
  });
});

describe("computeMovers", () => {
  it("counts directions and returns sorted leaders", () => {
    const items = [
      item({
        id: "up",
        history: points([["2026-11-10", 10], ["2026-11-11", 12]]),
      }),
      item({
        id: "down",
        history: points([["2026-11-10", 10], ["2026-11-11", 9]]),
      }),
      item({
        id: "flat",
        history: points([["2026-11-10", 10], ["2026-11-11", 10]]),
      }),
      item({ id: "none", history: [] }),
    ];
    const movers = computeMovers(items, "1d");
    expect(movers.gainers.map((mover) => mover.item.id)).toEqual(["up"]);
    expect(movers.losers.map((mover) => mover.item.id)).toEqual(["down"]);
    expect(movers.upCount).toBe(1);
    expect(movers.downCount).toBe(1);
    expect(movers.flatCount).toBe(1);
    expect(movers.withHistory).toBe(3);
  });
});

describe("hasSimulatedHistory", () => {
  it("detects simulated observations anywhere in history", () => {
    expect(hasSimulatedHistory([item()])).toBe(true);
    expect(
      hasSimulatedHistory([
        item({
          history: points([["2026-11-11", 10]]).map((point) => ({
            ...point,
            simulated: false,
          })),
        }),
      ]),
    ).toBe(false);
    expect(hasSimulatedHistory([])).toBe(false);
  });
});

describe("realValues", () => {
  it("switches displayed values back to the scraped source", () => {
    const source = item({
      price: 12,
      sourcePrice: 10,
      inStock: false,
      sourceInStock: true,
      history: points([["2026-11-10", 9], ["2026-11-11", 12]]),
    });
    const real = realValues(source);
    expect(real.price).toBe(10);
    expect(real.inStock).toBe(true);
    expect(real.simulated).toBe(false);
    expect(real.history.map((point) => point.price)).toEqual([10, 10]);
    expect(real.history.every((point) => point.simulated === false)).toBe(true);
    // The original object is untouched.
    expect(source.price).toBe(12);
  });
});

describe("paginate", () => {
  it("clamps pages into range", () => {
    expect(paginate([1, 2, 3], 99, 2).page).toBe(2);
    expect(paginate([1, 2, 3], 0, 2).page).toBe(1);
    expect(paginate([1, 2, 3], 1, 2).rows).toEqual([1, 2]);
  });
});

describe("sparklinePaths", () => {
  it("builds a line and closed area for two or more prices", () => {
    const result = sparklinePaths(item().history);
    expect(result.line.startsWith("M")).toBe(true);
    expect(result.line).toContain("L");
    expect(result.area.endsWith("Z")).toBe(true);
  });

  it("returns empty paths for missing data", () => {
    expect(sparklinePaths([])).toEqual({ line: "", area: "" });
  });
});
