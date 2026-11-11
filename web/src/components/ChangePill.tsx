import { formatDate, formatPercent, formatSignedMoney } from "@/lib/format";
import type { ChangeResult } from "@/lib/filters";
import { ArrowDownIcon, ArrowUpIcon } from "./Icons";

export function ChangePill({
  change,
  currency = "GBP",
}: {
  change: ChangeResult | null;
  currency?: string;
}) {
  if (!change) {
    return <span className="change-pill flat">—</span>;
  }
  const direction = change.change > 0 ? "up" : change.change < 0 ? "down" : "flat";
  const Icon = change.change < 0 ? ArrowDownIcon : ArrowUpIcon;
  return (
    <span
      className={`change-pill ${direction}`}
      title={`${formatSignedMoney(change.change, currency)} since ${formatDate(
        change.baseline.date,
      )}`}
    >
      {direction !== "flat" && <Icon />}
      {formatPercent(change.pct)}
    </span>
  );
}
