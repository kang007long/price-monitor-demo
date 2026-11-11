import { sparklinePaths } from "@/lib/filters";
import type { HistoryPoint } from "@/lib/types";

export function Sparkline({ history }: { history: HistoryPoint[] }) {
  const prices = history
    .slice(-14)
    .map((point) => point.price)
    .filter((price): price is number => price !== null);
  if (prices.length < 2) {
    return <span className="price-source">—</span>;
  }
  const { line, area } = sparklinePaths(history);
  const rising = prices[prices.length - 1] >= prices[0];
  return (
    <svg
      className={`sparkline ${rising ? "up" : "down"}`}
      viewBox="0 0 96 30"
      role="img"
      aria-label={`Price trend over ${prices.length} days`}
    >
      <path d={area} className="area" />
      <path d={line} className="line" />
    </svg>
  );
}
