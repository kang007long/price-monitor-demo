import type { NextConfig } from "next";

// The dashboard is fully static: GitHub Actions builds it after scraping and
// deploys the `out/` directory to GitHub Pages. A base path is only needed for
// project pages (https://user.github.io/price-monitor-demo/).
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  basePath: basePath || undefined,
  images: { unoptimized: true },
  reactStrictMode: true,
};

export default nextConfig;
