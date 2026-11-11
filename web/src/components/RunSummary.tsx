import Link from "next/link";

import { batchDuration } from "@/lib/filters";
import { formatDateTime, formatNumber } from "@/lib/format";
import type { Batch } from "@/lib/types";
import { ArrowRightIcon } from "./Icons";

export function RunSummary({ batch }: { batch: Batch | null }) {
  return (
    <section className="panel run-card" aria-labelledby="run-title">
      <div className="panel-header">
        <div>
          <h2 className="panel-title" id="run-title">
            Latest run
          </h2>
          <p className="panel-sub">One batch = one polite crawl</p>
        </div>
        {batch && (
          <span className={`status ${batch.status}`}>{batch.status}</span>
        )}
      </div>
      <div className="panel-body">
        {batch ? (
          <>
            <div className="run-row">
              <span className="run-label">Finished</span>
              <span className="run-value">{formatDateTime(batch.finishedAt)}</span>
            </div>
            <div className="run-row">
              <span className="run-label">Duration</span>
              <span className="run-value">{batchDuration(batch)}</span>
            </div>
            <div className="run-row">
              <span className="run-label">Pages fetched</span>
              <span className="run-value">{formatNumber(batch.pages)}</span>
            </div>
            <div className="run-row">
              <span className="run-label">Items seen</span>
              <span className="run-value">{formatNumber(batch.itemsSeen)}</span>
            </div>
            <div className="run-row">
              <span className="run-label">New / updated</span>
              <span className="run-value">
                {formatNumber(batch.itemsNew)} / {formatNumber(batch.itemsUpdated)}
              </span>
            </div>
            <div className="run-row">
              <span className="run-label">Price changes</span>
              <span className="run-value">{formatNumber(batch.priceChanges)}</span>
            </div>
            <div className="run-row">
              <span className="run-label">Errors</span>
              <span className="run-value">{formatNumber(batch.errorCount)}</span>
            </div>
            {batch.mode === "simulated" && (
              <div className="run-note">
                This run applied synthetic price movement. The scraped source prices
                are stored alongside every displayed value.
              </div>
            )}
            <Link className="drawer-link" href="/batches">
              All scrape runs <ArrowRightIcon className="icon-sm" />
            </Link>
          </>
        ) : (
          <p className="mover-empty">No completed scrape batches yet.</p>
        )}
      </div>
    </section>
  );
}
