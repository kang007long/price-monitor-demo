import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import http from "node:http";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const port = 4400 + Math.floor(Math.random() * 500);

function request(pathname) {
  return new Promise((resolve, reject) => {
    const req = http.get(
      { host: "127.0.0.1", port, path: pathname },
      (response) => {
        response.resume();
        response.on("end", () => resolve(response.statusCode));
      },
    );
    req.on("error", reject);
  });
}

test("serve.mjs survives a malformed percent-encoded path", async (t) => {
  const child = spawn(
    process.execPath,
    [path.join(here, "serve.mjs"), "out", String(port)],
    { cwd: path.join(here, ".."), stdio: ["ignore", "pipe", "pipe"] },
  );
  t.after(() => child.kill());

  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("server did not start")), 5000);
    child.stdout.on("data", (chunk) => {
      if (chunk.toString().includes("static preview")) {
        clearTimeout(timer);
        resolve();
      }
    });
    child.on("exit", (code) => {
      clearTimeout(timer);
      reject(new Error(`server exited early with ${code}`));
    });
  });

  assert.equal(await request("/%E0"), 400);
  const after = await request("/");
  assert.ok(after === 200 || after === 404, `expected a live response, got ${after}`);
  assert.equal(child.exitCode, null);
});
