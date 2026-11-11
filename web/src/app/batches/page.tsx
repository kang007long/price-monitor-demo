import type { Metadata } from "next";

import { BatchesView } from "@/components/BatchesView";

export const metadata: Metadata = {
  title: "Scrape runs",
  description: "Batch history, counts, and error log for the price monitor demo.",
};

export default function BatchesPage() {
  return <BatchesView />;
}
