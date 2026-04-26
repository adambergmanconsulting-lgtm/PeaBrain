#!/usr/bin/env node
/**
 * Wait for Nadir /health, then open the PeaBrain demo in the default browser.
 *
 * Env:
 *   NADIR_DEMO_URL     — page to open (default http://127.0.0.1:8765/demo/)
 *   NADIR_BASE         — if set, used to derive /health (overrides origin from NADIR_DEMO_URL)
 *   NADIR_DEMO_WAIT_MS — max wait for health (default 120000)
 *   NADIR_DEMO_SKIP_WAIT=1 — open immediately without waiting
 */
import { execFile } from "node:child_process";
import process from "node:process";

const pageUrl = process.env.NADIR_DEMO_URL || "http://127.0.0.1:8765/demo/";

let origin;
try {
  origin = new URL(pageUrl).origin;
} catch {
  console.error("NADIR_DEMO_URL is not a valid URL: " + pageUrl);
  process.exit(1);
}
if (process.env.NADIR_BASE) {
  try {
    origin = new URL(process.env.NADIR_BASE.replace(/\/$/, "")).origin;
  } catch {
    console.error("NADIR_BASE is not a valid URL");
    process.exit(1);
  }
}
const healthUrl = `${origin}/health`;

const skipWait = ["1", "true", "yes"].includes(
  String(process.env.NADIR_DEMO_SKIP_WAIT || "").toLowerCase()
);
const maxWait = Math.max(
  0,
  Number.parseInt(process.env.NADIR_DEMO_WAIT_MS || "120000", 10) || 120000
);
const intervalMs = 1000;

function openBrowser() {
  if (process.platform === "win32") {
    execFile("rundll32", ["url.dll,FileProtocolHandler", pageUrl], { stdio: "ignore" });
  } else if (process.platform === "darwin") {
    execFile("open", [pageUrl], { stdio: "ignore" });
  } else {
    execFile("xdg-open", [pageUrl], { stdio: "ignore" });
  }
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

if (skipWait) {
  openBrowser();
  console.log("Opened: " + pageUrl);
  process.exit(0);
}

const start = Date.now();
process.stdout.write(`Waiting for Nadir at ${healthUrl} …\n`);
for (;;) {
  try {
    const r = await fetch(healthUrl, { signal: AbortSignal.timeout(3000) });
    if (r.ok) {
      const elapsed = ((Date.now() - start) / 1000).toFixed(1);
      process.stdout.write(`Nadir is up (${elapsed}s). Opening browser.\n`);
      break;
    }
  } catch {
    /* not ready */
  }
  if (Date.now() - start >= maxWait) {
    process.stderr.write(
      `Nadir did not become ready in ${maxWait / 1000}s. Start the stack, then retry:\n` +
        `  npm run stack:up\n` +
        `  docker compose -f ./docker-compose.yml up -d\n` +
        `Or open the URL manually when Nadir is running: ${pageUrl}\n` +
        `To open without waiting: NADIR_DEMO_SKIP_WAIT=1 npm run demo:open\n`
    );
    process.exit(1);
  }
  process.stdout.write(`\r  still waiting… (${Math.floor((Date.now() - start) / 1000)}s) `);
  await sleep(intervalMs);
}

openBrowser();
console.log("Opened: " + pageUrl);
