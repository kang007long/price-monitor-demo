"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { BASE_PATH, REPO_URL } from "@/lib/data";
import { ExternalIcon } from "@/components/Icons";

const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/batches", label: "Scrape runs" },
  { href: "/about", label: "About" },
];

export function SiteHeader() {
  const pathname = usePathname() ?? "/";
  const path = BASE_PATH && pathname.startsWith(BASE_PATH)
    ? pathname.slice(BASE_PATH.length) || "/"
    : pathname;

  return (
    <header className="site-header">
      <div className="container header-inner">
        <Link className="brand" href="/" aria-label="Price Monitor home">
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
              <path d="M4 19V5" />
              <path d="M4 19h16" />
              <path d="M7 15l4-5 3 3 5-7" />
            </svg>
          </span>
          <span className="brand-text">
            <span className="brand-name">Price Monitor</span>
            <span className="brand-tag">Portfolio demo</span>
          </span>
        </Link>

        <nav className="nav" aria-label="Main navigation">
          {NAV.map((item) => {
            const active =
              item.href === "/"
                ? path === "/" || path === ""
                : path.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`nav-link${active ? " active" : ""}`}
                aria-current={active ? "page" : undefined}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="header-meta">
          <span className="pill pill-amber">
            <span className="dot" /> Practice sandbox
          </span>
          <a className="btn" href={REPO_URL} target="_blank" rel="noreferrer noopener">
            Source on GitHub <ExternalIcon />
          </a>
        </div>
      </div>
    </header>
  );
}
