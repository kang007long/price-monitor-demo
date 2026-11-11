import { describe, expect, it } from "vitest";

import { csvEscape, excelSafe, toCsv } from "@/lib/csv";
import {
  formatDate,
  formatDateTime,
  formatMoney,
  formatPercent,
  formatSignedMoney,
} from "@/lib/format";
import { coverPalette, initials } from "@/lib/cover";
import type { Item } from "@/lib/types";

function item(overrides: Partial<Item> = {}): Item {
  return {
    id: "book-1",
    title: "A Book",
    url: "https://example.com",
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
    history: [
      {
        date: "2026-11-10",
        price: 9,
        sourcePrice: 10,
        simulated: true,
        inStock: true,
        sourceInStock: true,
      },
      {
        date: "2026-11-11",
        price: 10,
        sourcePrice: 10,
        simulated: true,
        inStock: true,
        sourceInStock: true,
      },
    ],
    ...overrides,
  };
}

describe("csv", () => {
  it("escapes commas, quotes, and newlines", () => {
    expect(csvEscape("plain")).toBe("plain");
    expect(csvEscape("a,b")).toBe('"a,b"');
    expect(csvEscape('say "hi"')).toBe('"say ""hi"""');
    expect(csvEscape("two\nlines")).toBe('"two\nlines"');
    expect(csvEscape(null)).toBe("");
  });

  it("neutralises values that spreadsheet apps treat as formulas", () => {
    expect(excelSafe("=SUM(A1:A2)")).toBe("'=SUM(A1:A2)");
    expect(excelSafe("+1")).toBe("'+1");
    expect(excelSafe("-1")).toBe("'-1");
    expect(excelSafe("@cmd")).toBe("'@cmd");
    expect(csvEscape("=1+1")).toBe("'=1+1");
    expect(csvEscape("plain")).toBe("plain");
  });

  it("neutralises formula titles in the filtered export", () => {
    const csv = toCsv([item({ title: "=1+1", url: "=HYPERLINK(\"http://x\")" })], "1d");
    expect(csv).toContain("'=1+1");
    expect(csv).toContain("'=HYPERLINK");
  });

  it("builds a header and one row per item with window change", () => {
    const csv = toCsv([item({ title: 'Comma, "Quote"' })], "1d");
    const lines = csv.trimEnd().split("\n");
    expect(lines[0]).toBe(
      "title,rating,price,source_price,currency,change,change_pct,window,in_stock,simulated,url",
    );
    expect(lines[1]).toContain('"Comma, ""Quote"""');
    expect(lines[1]).toContain("GBP,1.00,11.11");
    expect(lines[1]).toContain("1d,yes,yes");
    expect(lines).toHaveLength(2);
  });
});

describe("format", () => {
  it("formats money and signed values", () => {
    expect(formatMoney(1234.5)).toContain("1,234.50");
    expect(formatMoney(null)).toBe("—");
    expect(formatSignedMoney(1.2)).toContain("+");
    expect(formatSignedMoney(-1.2)).toContain("−");
    expect(formatPercent(-1.234)).toBe("−1.23%");
    expect(formatPercent(0)).toBe("0.00%");
  });

  it("formats dates in UTC and handles invalid input", () => {
    expect(formatDate("2026-11-11")).toBe("11 Nov 2026");
    expect(formatDateTime("2026-11-11T13:26:43+00:00")).toBe(
      "11 Nov 2026, 13:26 UTC",
    );
    expect(formatDateTime(null)).toBe("—");
    expect(formatDate("not-a-date")).toBe("not-a-date");
  });
});

describe("cover", () => {
  it("is deterministic and readable", () => {
    expect(coverPalette("A Book")).toEqual(coverPalette("A Book"));
    expect(coverPalette("A Book").background).toContain("linear-gradient");
    expect(initials("The Great Gatsby")).toBe("TG");
    expect(initials("'Salem's Lot")).toBe("SL");
    expect(initials("One")).toBe("ON");
    expect(initials("###")).toBe("?");
  });
});
