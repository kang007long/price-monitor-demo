import type { Metadata } from "next";

import "./globals.css";
import { SiteFooter } from "@/components/SiteFooter";
import { SiteHeader } from "@/components/SiteHeader";

export const metadata: Metadata = {
  title: {
    default: "Price Monitor — a scraping + dashboard demo",
    template: "%s · Price Monitor",
  },
  description:
    "A polite Python scraper, SQLite history, and static Next.js dashboard, built on the public Books to Scrape sandbox.",
  applicationName: "Price Monitor Demo",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div className="site-shell">
          <SiteHeader />
          <main className="site-main">{children}</main>
          <SiteFooter />
        </div>
      </body>
    </html>
  );
}
