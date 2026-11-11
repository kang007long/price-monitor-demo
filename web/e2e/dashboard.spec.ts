import { expect, test } from "@playwright/test";
import { stat } from "node:fs/promises";
import path from "node:path";

const screenshots = path.resolve(process.cwd(), "..", "docs", "screenshots");

function shot(name: string, mobile: boolean): string {
  return path.join(screenshots, `${name}${mobile ? "-mobile" : ""}.png`);
}

test("dashboard renders the catalogue and charts", async ({ page }, testInfo) => {
  const mobile = testInfo.project.name === "mobile";
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Catalogue price intelligence",
  );
  await expect(page.locator("table.data-table tbody tr")).toHaveCount(20);
  await expect(page.locator(".kpi-value").first()).toContainText("1,000");
  await expect(page.locator(".banner")).toContainText("Simulated price data");
  await expect(page.locator(".mover-row").first()).toBeVisible();

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);

  await page.screenshot({ path: shot("dashboard", mobile), fullPage: true });

  await page.locator("table.data-table tbody tr").first().click();
  await expect(page.locator(".drawer")).toBeVisible();
  await page.waitForTimeout(350);
  await expect(page.locator(".chart-svg")).toBeVisible();
  await expect(page.locator(".history-table tbody tr").first()).toBeVisible();
  await page.locator(".chart-svg").hover({ position: { x: 300, y: 100 } });
  await expect(page.locator(".chart-tooltip")).toBeVisible();
  await page.waitForTimeout(150);
  await page.screenshot({ path: shot("detail", mobile) });
  await page.keyboard.press("Escape");
  await expect(page.locator(".drawer")).toHaveCount(0);
});

test("search and stock filters narrow the catalogue", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name === "mobile", "Covered by the desktop project.");
  await page.goto("/");
  await expect(page.locator("table.data-table tbody tr")).toHaveCount(20);

  const search = page.getByPlaceholder(/Search 1,000 titles/);
  await search.fill("salem");
  await expect(page.locator("table.data-table tbody tr")).toHaveCount(1);
  await expect(page.locator("table.data-table tbody tr").first()).toContainText(/salem/i);

  await search.fill("");
  await page.getByLabel("Stock").selectOption("out");
  const outRows = page.locator("table.data-table tbody tr");
  expect(await outRows.count()).toBeGreaterThan(0);
  for (const row of await outRows.all()) {
    await expect(row.locator(".stock:not(.mobile-stock)")).toContainText("Out");
  }

  await page.getByRole("button", { name: "Reset" }).click();
  await expect(page.locator("table.data-table tbody tr")).toHaveCount(20);
});

test("the simulation toggle switches to real scraped values", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name === "mobile", "Toggle is verified on desktop.");
  await page.goto("/");
  await expect(page.locator(".banner")).toContainText("Simulated price data");
  await expect(page.locator(".toggle-text")).toContainText("Simulated prices");

  await page.locator(".toggle").click();
  await expect(page.locator(".banner")).toContainText("Real scraped prices");
  await expect(page.locator(".banner")).toContainText("Real view");
  await expect(page.locator(".mover-empty")).toBeVisible();
  await expect(
    page.locator("table.data-table tbody tr").first().locator(".change-pill"),
  ).toContainText("0.00%");

  await page.locator(".toggle").click();
  await expect(page.locator(".banner")).toContainText("Simulated price data");
});

test("exports download real files", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name === "mobile", "Downloads are checked on desktop.");
  await page.goto("/");
  await expect(page.locator("table.data-table tbody tr")).toHaveCount(20);

  for (const [extension, minimum] of [
    ["csv", 5_000],
    ["xlsx", 50_000],
  ] as const) {
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.locator(`a[href$="price-monitor-latest.${extension}"]`).first().click(),
    ]);
    expect(download.suggestedFilename()).toBe(`price-monitor-latest.${extension}`);
    const file = await download.path();
    expect(file).toBeTruthy();
    const info = await stat(file as string);
    expect(info.size).toBeGreaterThan(minimum);
  }
});

test("scrape runs and about pages render", async ({ page }, testInfo) => {
  const mobile = testInfo.project.name === "mobile";
  test.skip(mobile, "Long-form pages are captured on desktop.");

  await page.goto("/batches/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Every batch, on the record",
  );
  const batchRows = page.locator(".batch-table tbody tr");
  expect(await batchRows.count()).toBeGreaterThan(1);
  await expect(page.locator(".batch-table")).toContainText("Scrape");
  await expect(page.locator(".panel-sub").first()).toContainText("backfill");
  await page.screenshot({ path: shot("batches", false), fullPage: true });

  await page.goto("/about/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "A small, honest scraping demo",
  );
  await expect(page.locator("#simulation")).toBeVisible();
  await page.screenshot({ path: shot("about", false), fullPage: true });
});
