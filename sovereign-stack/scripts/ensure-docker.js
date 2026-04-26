#!/usr/bin/env node
/**
 * Ensure the Docker daemon is reachable: try to start Docker Desktop (Windows/macOS)
 * or the docker service (Linux), then wait until `docker info` succeeds.
 *
 * Adapted from CVReady (scripts/ensure-docker.js) with Nadir-specific env names.
 * Original pattern: `docker info` with shell: true; Windows: spawn Docker Desktop.exe; poll until ready.
 *
 * CLI:  node scripts/ensure-docker.js
 * npm:  npm run docker:ensure
 *
 * Skip auto-start: NADIR_DOCKER_ENSURE_SKIP=1 (only checks `docker info`)
 * Wait timeout:   NADIR_DOCKER_ENSURE_TIMEOUT_MS (default 120000)
 */

const { execSync, spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

const rootDir = path.join(__dirname, "..");

function sleepSync(ms) {
  const sab = new SharedArrayBuffer(4);
  Atomics.wait(new Int32Array(sab), 0, 0, ms);
}

function log(msg) {
  console.log(`[nadir:docker:ensure] ${msg}`);
}

function probeDockerInfo(cwd) {
  try {
    execSync("docker info", {
      cwd,
      stdio: ["ignore", "pipe", "pipe"],
      encoding: "utf8",
      shell: true,
    });
    return { ok: true, err: "" };
  } catch (e) {
    const err =
      (e.stderr && e.stderr.toString()) ||
      (e.stdout && e.stdout.toString()) ||
      e.message ||
      "";
    return { ok: false, err };
  }
}

function isDockerDaemonReachable(cwd = rootDir) {
  return probeDockerInfo(cwd).ok;
}

function resolveDockerDesktopExe() {
  const candidates = [
    process.env.ProgramFiles &&
      path.join(process.env.ProgramFiles, "Docker", "Docker", "Docker Desktop.exe"),
    "C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe",
    process.env["ProgramFiles(x86)"] &&
      path.join(process.env["ProgramFiles(x86)"], "Docker", "Docker", "Docker Desktop.exe"),
  ].filter(Boolean);

  for (const p of candidates) {
    if (p && fs.existsSync(p)) return p;
  }
  return null;
}

/**
 * @param {object} [options]
 * @param {string} [options.cwd]
 * @param {boolean} [options.quiet]
 * @returns {boolean}
 */
function ensureDockerReady(options = {}) {
  const cwd = options.cwd || rootDir;
  const quiet = Boolean(options.quiet);

  if (process.env.NADIR_DOCKER_ENSURE_SKIP === "1") {
    const ok = isDockerDaemonReachable(cwd);
    if (!quiet && ok) log("daemon reachable (NADIR_DOCKER_ENSURE_SKIP=1, no auto-start).");
    return ok;
  }

  const initial = probeDockerInfo(cwd);
  if (initial.ok) {
    if (!quiet) log("Docker daemon already reachable.");
    return true;
  }

  if (
    initial.err.includes("WSL") ||
    initial.err.includes("Windows Subsystem for Linux")
  ) {
    log("Docker Desktop needs WSL 2. Install with: wsl --install (Admin PowerShell), reboot, then retry.");
    return false;
  }

  const platform = process.platform;
  const timeoutMs = Math.max(
    15000,
    Number.parseInt(process.env.NADIR_DOCKER_ENSURE_TIMEOUT_MS || "120000", 10) || 120000
  );
  const checkInterval = 2000;

  let startLabel = null;

  if (platform === "win32") {
    try {
      execSync("wsl", ["--status"], {
        encoding: "utf8",
        stdio: ["ignore", "pipe", "pipe"],
      });
    } catch (wslError) {
      const wslOut =
        (wslError.stderr && wslError.stderr.toString()) ||
        (wslError.stdout && wslError.stdout.toString()) ||
        "";
      if (wslOut.includes("not installed") || wslOut.includes("WSL")) {
        log("Docker Desktop requires WSL 2. Run: wsl --install (Admin), reboot, then start Docker Desktop.");
        return false;
      }
    }

    const exe = resolveDockerDesktopExe();
    if (!exe) {
      log("Docker Desktop does not appear to be installed (no Docker Desktop.exe under Program Files).");
      log("Install (Admin PowerShell; accepts winget license):");
      log("  winget install -e --id Docker.DockerDesktop");
      log("https://docs.docker.com/desktop/install/windows-install/");
      log("After install, start Docker Desktop once, then re-run this script or npm run docker:ensure");
      return false;
    }
    if (!quiet) log("Starting Docker Desktop…");
    try {
      const child = spawn(exe, [], {
        detached: true,
        stdio: "ignore",
        windowsHide: true,
      });
      child.unref();
      startLabel = "Docker Desktop";
    } catch {
      try {
        execSync(`Start-Process "${exe}"`, {
          shell: "powershell.exe",
          stdio: "ignore",
        });
        startLabel = "Docker Desktop";
      } catch {
        try {
          execSync("Start-Service com.docker.service", {
            shell: "powershell.exe",
            stdio: "ignore",
          });
          startLabel = "Docker service";
        } catch {
          /* ignore */
        }
      }
    }
  } else if (platform === "darwin") {
    if (!quiet) log("Starting Docker Desktop (macOS)…");
    try {
      execSync("open", ["-a", "Docker"], { stdio: "ignore" });
      startLabel = "Docker Desktop";
    } catch {
      /* ignore */
    }
  } else if (platform === "linux") {
    if (!quiet) log("Trying to start Docker service (Linux)…");
    const attempts = [
      () => execSync("sudo", ["-n", "systemctl", "start", "docker"], { stdio: "ignore" }),
      () => execSync("sudo", ["-n", "service", "docker", "start"], { stdio: "ignore" }),
    ];
    for (const run of attempts) {
      try {
        run();
        startLabel = "Docker service";
        break;
      } catch {
        /* next */
      }
    }
  }

  if (!startLabel) {
    log("Could not start Docker automatically. Open Docker Desktop (or: sudo systemctl start docker on Linux).");
    return false;
  }

  if (!quiet) log(`Waiting for Docker (up to ${Math.round(timeoutMs / 1000)}s)…`);
  const startTime = Date.now();
  while (Date.now() - startTime < timeoutMs) {
    if (isDockerDaemonReachable(cwd)) {
      if (!quiet) log("Docker is ready.");
      return true;
    }
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    process.stdout.write(`\r[nadir:docker:ensure] Waiting… (${elapsed}s)`);
    sleepSync(checkInterval);
  }
  process.stdout.write("\n");
  log("Timed out waiting for Docker. Start Docker Desktop manually and run this command again.");
  return false;
}

function main() {
  const ok = ensureDockerReady({ quiet: false });
  process.exit(ok ? 0 : 1);
}

module.exports = {
  ensureDockerReady,
  isDockerDaemonReachable,
};

if (require.main === module) {
  main();
}
