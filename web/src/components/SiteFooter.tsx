import Link from "next/link";

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="container footer-inner">
        <p className="footer-note">
          Built on{" "}
          <a href="https://books.toscrape.com/" rel="noreferrer noopener" target="_blank">
            Books to Scrape
          </a>
          , a public sandbox made for scraping practice. Not affiliated with any shop.
        </p>
        <div className="footer-links">
          <Link href="/about">How it works</Link>
          <a
            href="https://quotes.toscrape.com/"
            rel="noreferrer noopener"
            target="_blank"
          >
            Second sandbox
          </a>
          <span>Educational use</span>
        </div>
      </div>
    </footer>
  );
}
