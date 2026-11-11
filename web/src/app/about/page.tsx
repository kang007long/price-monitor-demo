import type { Metadata } from "next";
import Link from "next/link";

import {
  ActivityIcon,
  CheckIcon,
  ClockIcon,
  DatabaseIcon,
  ExternalIcon,
  InfoIcon,
} from "@/components/Icons";

export const metadata: Metadata = {
  title: "About",
  description:
    "Architecture, data model, scraping ethics, and deployment notes for the Price Monitor demo.",
};

export default function AboutPage() {
  return (
    <div className="container">
      <div className="page-head">
        <div>
          <div className="eyebrow">How it works</div>
          <h1 className="page-title">A small, honest scraping demo</h1>
          <p className="page-subtitle">
            Scrape a public practice site politely, keep every observation in SQLite,
            and publish a static dashboard that costs nothing to host. No real shops,
            accounts, credentials, or anti-bot tricks.
          </p>
        </div>
        <div className="page-actions">
          <Link className="btn" href="/">
            View dashboard
          </Link>
          <Link className="btn" href="/batches">
            Scrape runs
          </Link>
        </div>
      </div>

      <div className="about-layout">
        <article className="prose">
          <h2>Architecture</h2>
          <pre className="arch" aria-label="Architecture diagram">
{`GitHub Actions · cron 05:17 UTC
        │
        ▼
Python crawler  ──  robots.txt · 1 req/s · retries · clear UA
        │
        ▼
SQLite  data/price_monitor.db
        ├── items                current state
        ├── price_history        one row per item per batch
        ├── stock_history        availability timeline
        ├── batches              one row per run
        └── scrape_errors        fetch / parse / robots failures
        │
        │  export step (no network)
        ▼
web/public/data/dashboard.json  +  CSV / XLSX
        │
        ▼
Next.js static export  ──▶  GitHub Pages`}
          </pre>

          <div className="step-grid">
            <div className="step">
              <span className="step-num">1</span>
              <h3>Crawl politely</h3>
              <p>
                One shared HTTP client enforces at least 1.1 seconds between requests,
                checks robots.txt once per host, and retries timeouts, 429s, and 5xx
                responses with backoff.
              </p>
            </div>
            <div className="step">
              <span className="step-num">2</span>
              <h3>Store every observation</h3>
              <p>
                Items are de-duplicated by their stable product path. Price and stock
                history are append-only; rerunning a batch updates rows instead of
                duplicating them.
              </p>
            </div>
            <div className="step">
              <span className="step-num">3</span>
              <h3>Export, don&apos;t serve</h3>
              <p>
                SQLite stays the operational store. The export step writes a static JSON
                snapshot plus CSV/Excel reports, so the dashboard needs no server or
                database at runtime.
              </p>
            </div>
            <div className="step">
              <span className="step-num">4</span>
              <h3>Deploy for free</h3>
              <p>
                The daily workflow commits the updated database and reports, rebuilds
                the static site, and deploys it to GitHub Pages. No paid host, no
                secrets.
              </p>
            </div>
          </div>

          <h2 id="simulation">What is real and what is simulated</h2>
          <p>
            <strong>The source prices are real scraper output.</strong> Books to Scrape
            is a practice sandbox whose prices never change, so a genuine 14-day price
            chart would be a flat line.
          </p>
          <p>
            To demonstrate change detection, the demo can apply clearly-labelled
            synthetic movement: a deterministic random walk bounded to ±20% of the
            scraped price. Every stored row carries a <code>simulated</code> flag, the
            source price is preserved beside the displayed price, and the UI shows an
            amber banner and a dashed source-price line. Backfilled days are separate
            batches with <code>kind = backfill</code> and never touch current state.
          </p>
          <p>
            Run without <code>--simulate</code> and the dashboard switches to real
            values, with a note that the practice site prices are static.
          </p>

          <h2>Politeness &amp; scope</h2>
          <ul>
            <li>
              Only two hosts are allowed by code: <code>books.toscrape.com</code> and{" "}
              <code>quotes.toscrape.com</code>. Other hosts are refused before any
              request is made.
            </li>
            <li>
              robots.txt is fetched once per host and obeyed. Both sandboxes currently
              return 404 for robots.txt, which RFC 9309 treats as &ldquo;no
              restrictions&rdquo;; a disallow or a 5xx response blocks the crawl.
            </li>
            <li>
              The client spaces requests by at least 1.1 seconds, sends a descriptive
              User-Agent, retries with backoff, and never bypasses a challenge or
              anti-bot measure.
            </li>
            <li>
              No login, account, API key, or private data is used anywhere in the
              project.
            </li>
          </ul>

          <h2>Data model</h2>
          <ul>
            <li>
              <code>items</code> holds current title, URL, rating, scraped price,
              displayed price, stock, and first/last seen timestamps.
            </li>
            <li>
              <code>price_history</code> and <code>stock_history</code> are keyed by
              item and batch, so each day is one observation. The dashboard derives 1
              day / 7 day / 30 day changes from them.
            </li>
            <li>
              <code>batches</code> records pages fetched, items seen/new/updated, price
              and stock changes, errors, mode, and status. <code>scrape_errors</code>{" "}
              keeps the URL, kind, message, and time for each failure.
            </li>
          </ul>

          <h2>Run it locally</h2>
          <pre className="arch" aria-label="Local commands">
{`# one command: scrape, export, build, open the dashboard
make demo

# or run the steps yourself
uv sync
uv run price-monitor scrape --simulate --ensure-history 14
uv run price-monitor export
cd web && pnpm install && pnpm build && pnpm preview`}
          </pre>
          <p>
            Tests never touch the network: parsers run against saved HTML fixtures,
            HTTP behaviour is tested with a mock transport, and the full scrape pipeline
            is exercised offline.
          </p>

          <h2>Add another site</h2>
          <p>
            A source is one adapter: a <code>SourceSpec</code> (start URL, robots URL,
            page cap, currency) plus a <code>parse_page()</code> that returns items and
            the next URL. Register it in <code>price_monitor/sources/__init__.py</code>,
            add its host to <code>ALLOWED_HOSTS</code>, save a fixture, and write parser
            tests. The crawler, storage, export, and dashboard do not change.
          </p>
          <p>
            The optional Quotes to Scrape adapter is included as a reference for a
            second, unpriced source. The dashboard reads the books dataset.
          </p>

          <h2>Stack</h2>
          <p>
            Python 3.11+ with httpx and BeautifulSoup (static HTML needs no browser),
            SQLite for storage, openpyxl for Excel, Next.js static export with hand-built
            SVG charts for the dashboard, and GitHub Actions for the daily run and
            Pages deployment.
          </p>
        </article>

        <aside className="about-aside">
          <section className="panel">
            <div className="panel-header">
              <div>
                <h2 className="panel-title">At a glance</h2>
                <p className="panel-sub">Demo boundaries</p>
              </div>
            </div>
            <div className="panel-body">
              <div className="fact-list">
                <div className="fact">
                  <ActivityIcon />
                  <span>
                    <strong>1 request / second</strong>
                    Global throttle, robots-aware, retries with backoff.
                  </span>
                </div>
                <div className="fact">
                  <ClockIcon />
                  <span>
                    <strong>Daily at 05:17 UTC</strong>
                    GitHub Actions cron; manual runs supported.
                  </span>
                </div>
                <div className="fact">
                  <DatabaseIcon />
                  <span>
                    <strong>SQLite source of truth</strong>
                    Current state plus append-only price and stock history.
                  </span>
                </div>
                <div className="fact">
                  <CheckIcon />
                  <span>
                    <strong>No accounts or keys</strong>
                    Public sandbox only; nothing private is touched.
                  </span>
                </div>
                <div className="fact">
                  <InfoIcon />
                  <span>
                    <strong>Simulated values are labelled</strong>
                    Database flags, UI banner, and dashed source line.
                  </span>
                </div>
              </div>
            </div>
          </section>

          <section className="panel">
            <div className="panel-header">
              <div>
                <h2 className="panel-title">Practice sites</h2>
                <p className="panel-sub">Explicitly built for scraping</p>
              </div>
            </div>
            <div className="panel-body stack-10">
              <a
                className="btn"
                href="https://books.toscrape.com/"
                target="_blank"
                rel="noreferrer noopener"
              >
                Books to Scrape <ExternalIcon />
              </a>
              <a
                className="btn"
                href="https://quotes.toscrape.com/"
                target="_blank"
                rel="noreferrer noopener"
              >
                Quotes to Scrape <ExternalIcon />
              </a>
              <p className="aside-note">
                These sandboxes exist for scraping practice. They are not shops and
                contain no personal data.
              </p>
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}
