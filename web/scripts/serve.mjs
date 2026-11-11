#!/usr/bin/env node
// Tiny static file server for the exported site (no extra dependencies).
// Usage: node scripts/serve.mjs [root] [port]

import { createServer } from "node:http";
import { readFile, stat } from "node:fs/promises";
import { extname, join, resolve, sep } from "node:path";

const root = resolve(process.argv[2] ?? "out");
const port = Number(process.argv[3] ?? process.env.PORT ?? 3000);

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".ico": "image/x-icon",
  ".txt": "text/plain; charset=utf-8",
  ".csv": "text/csv; charset=utf-8",
  ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  ".woff2": "font/woff2",
};

async function findFile(pathname) {
  if (pathname.endsWith("/")) pathname += "index.html";
  const target = resolve(join(root, pathname));
  if (target !== root && !target.startsWith(root + sep)) return null;

  try {
    const info = await stat(target);
    if (info.isDirectory()) return findFile(`${pathname}/index.html`);
    return target;
  } catch {
    if (!extname(pathname)) {
      try {
        const html = await stat(`${target}.html`);
        if (html.isFile()) return `${target}.html`;
      } catch {
        /* fall through */
      }
    }
    return null;
  }
}

const server = createServer(async (request, response) => {
  try {
    let pathname;
    try {
      const url = new URL(request.url ?? "/", "http://localhost");
      pathname = decodeURIComponent(url.pathname);
    } catch {
      response.writeHead(400, { "Content-Type": "text/plain; charset=utf-8" });
      response.end("400 Bad Request");
      return;
    }

    const file = await findFile(pathname);
    if (!file) {
      response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
      response.end("404 Not Found");
      return;
    }

    const body = await readFile(file);
    response.writeHead(200, {
      "Content-Type": MIME[extname(file)] ?? "application/octet-stream",
      "Cache-Control": "no-cache",
    });
    response.end(body);
  } catch {
    if (!response.headersSent && !response.writableEnded) {
      response.writeHead(500, { "Content-Type": "text/plain; charset=utf-8" });
    }
    if (!response.writableEnded) response.end("500 Internal Server Error");
  }
});

server.on("clientError", (_error, socket) => {
  if (socket.writable) {
    socket.end("HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n");
  }
});

// Loopback only: the demo dashboard should not be reachable from the LAN.
server.listen(port, "127.0.0.1", () => {
  console.log(`Price Monitor static preview: http://127.0.0.1:${port}`);
});
