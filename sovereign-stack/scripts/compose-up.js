#!/usr/bin/env node
/**
 * `docker compose` for this folder, after ensuring the daemon (CVReady-style).
 * Pass-through: `node scripts/compose-up.js ps` -> `docker compose -f ... ps`
 * Default: `up -d --build`
 */
const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");
const { ensureDockerReady } = require("./ensure-docker");

const rootDir = path.join(__dirname, "..");
const composeFile = path.join(rootDir, "docker-compose.yml");
const userArgs = process.argv.slice(2);

function fail(msg) {
  console.error(`[nadir:compose] ${msg}`);
  process.exit(1);
}

if (!fs.existsSync(composeFile)) {
  fail(`Missing ${composeFile}`);
}

if (!ensureDockerReady({ cwd: rootDir, quiet: false })) {
  process.exit(1);
}

const dockerArgs =
  userArgs.length > 0
    ? ["compose", "-f", composeFile, ...userArgs]
    : ["compose", "-f", composeFile, "up", "-d", "--build"];

const r = spawnSync("docker", dockerArgs, {
  cwd: rootDir,
  stdio: "inherit",
  shell: false,
  env: process.env,
});

if (r.error) {
  fail(r.error.message || "docker failed");
}
process.exit(typeof r.status === "number" ? r.status : 1);
