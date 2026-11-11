import type { DashboardData } from "./types";

export const BASE_PATH = (process.env.NEXT_PUBLIC_BASE_PATH ?? "").replace(
  /\/+$/,
  "",
);

export function withBasePath(path: string): string {
  const clean = path.replace(/^\/+/, "");
  return `${BASE_PATH}/${clean}`;
}

export async function fetchDashboard(
  signal?: AbortSignal,
): Promise<DashboardData> {
  const response = await fetch(withBasePath("data/dashboard.json"), {
    signal,
    cache: "no-cache",
  });
  if (!response.ok) {
    throw new Error(`Could not load dashboard data (HTTP ${response.status}).`);
  }
  const data = (await response.json()) as DashboardData;
  if (
    typeof data !== "object" ||
    data === null ||
    data.schemaVersion !== 1 ||
    !Array.isArray(data.items)
  ) {
    throw new Error("Dashboard data has an unexpected shape.");
  }
  return data;
}
