#!/usr/bin/env node
/**
 * Start the stack (if needed) and the Cloudflare quick-tunnel sidecar (public HTTPS -> Nadir).
 * The public base URL (…trycloudflare.com) is printed in the cloudflared container logs.
 */
const path = require("path");
const { spawnSync } = require("child_process");
const { ensureDockerReady } = require("./ensure-docker");

const rootDir = path.join(__dirname, "..");
const composeFile = path.join(rootDir, "docker-compose.yml");

if (!ensureDockerReady({ cwd: rootDir, quiet: false })) {
  process.exit(1);
}

const upBase = spawnSync(
  "docker",
  ["compose", "-f", composeFile, "up", "-d", "--build"],
  { cwd: rootDir, stdio: "inherit" }
);
if (upBase.status !== 0) {
  process.exit(typeof upBase.status === "number" ? upBase.status : 1);
}

const upTunnel = spawnSync(
  "docker",
  [
    "compose",
    "-f",
    composeFile,
    "--profile",
    "public",
    "up",
    "-d",
    "cloudflared",
  ],
  { cwd: rootDir, stdio: "inherit" }
);
if (upTunnel.status !== 0) {
  process.exit(typeof upTunnel.status === "number" ? upTunnel.status : 1);
}

console.log("");
console.log(
  "[public-tunnel] Cloudflared is running. Your HTTPS base URL is in the logs (ends with trycloudflare.com)."
);
console.log("  Set Cursor Override OpenAI Base URL to:  https://<host>/v1");
console.log(
  "  If NADIR_INBOUND_BEARER_TOKEN is set in .env, use the same string as the OpenAI API key in Cursor."
);
console.log("");
console.log("  View URL:  npm run public:url:logs");
console.log("  Or:        docker compose --profile public logs -f cloudflared");
console.log("");
