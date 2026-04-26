#Requires -Version 5.1
# Download, build, and start NadirClaw + Ollama. Requires Docker Desktop (Windows) or a working `docker` CLI.
# If Node is present, uses the same ensure-docker + compose flow as CVReady (scripts/ensure-docker.js, scripts/compose-up.js).
# Usage: .\setup.ps1   |   .\setup.ps1 -SkipModelPull
param(
  [switch] $SkipModelPull
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

function Test-Docker {
  if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker CLI not found. Install Docker Desktop: https://docs.docker.com/desktop/setup/install/windows-install/" -ForegroundColor Red
    exit 1
  }
  # `docker version` can partially succeed; `docker info` always talks to the engine (daemon).
  $null = & docker info 2>&1
  if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Docker is installed, but the engine is not running or is not reachable." -ForegroundColor Red
    Write-Host "  (Typical: Docker Desktop is closed, still starting, or a wrong 'docker context'.)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  1. Open Docker Desktop from the Start menu and wait until the engine is running (tray icon idle)." -ForegroundColor Yellow
    Write-Host "  2. WSL2: In Docker Desktop, Settings, Resources, WSL integration, enable your distro if you use Docker from WSL." -ForegroundColor Yellow
    Write-Host "  3. In this terminal, run:  docker context ls" -ForegroundColor Yellow
    Write-Host "     If the current context (marked *) is wrong, try:  docker context use default" -ForegroundColor Yellow
    Write-Host ""
    exit 1
  }
  $null = & docker compose version 2>&1
  if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker is running, but 'docker compose' is missing. Update Docker Desktop or install the Compose v2 plugin." -ForegroundColor Red
    exit 1
  }
}

function Get-ModelName {
  if (Test-Path (Join-Path $Root ".env")) {
    $line = Get-Content (Join-Path $Root ".env") | Where-Object { $_ -match "^\s*NADIR_LOCAL_MODEL\s*=" } | Select-Object -First 1
    if ($line) {
      $m = $line -replace "^\s*NADIR_LOCAL_MODEL\s*=\s*", "" -replace "\s+$", "" -replace "^['\`"]|['\`"]$", ""
      if ($m) { return $m }
    }
  }
  return "qwen2.5-coder:14b"
}

if (-not (Test-Path (Join-Path $Root ".env"))) {
  Copy-Item (Join-Path $Root ".env.example") (Join-Path $Root ".env")
  Write-Host "Created .env from .env.example. Set NADIR_OPENROUTER_API_KEY before using cloud routing." -ForegroundColor Yellow
} else {
  Write-Host "Using existing .env" -ForegroundColor Cyan
}

$composeUpJs = Join-Path $Root "scripts\compose-up.js"
$useNode = (Get-Command node -ErrorAction SilentlyContinue) -and (Test-Path $composeUpJs)

Write-Host "Building and starting services (Ollama + Nadir)..." -ForegroundColor Cyan
if ($useNode) {
  & node $composeUpJs
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
  Test-Docker
  docker compose -f (Join-Path $Root "docker-compose.yml") up -d --build
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$model = Get-ModelName
if ($SkipModelPull) {
  Write-Host "Skipped Ollama model pull. Run when ready: docker compose exec ollama ollama pull $model" -ForegroundColor Yellow
} else {
  Write-Host "Pulling Ollama model: $model (this can take a while)..." -ForegroundColor Cyan
  docker compose -f (Join-Path $Root "docker-compose.yml") exec -T ollama ollama pull $model
}

Start-Sleep -Seconds 1
$health = "http://127.0.0.1:8765/health"
try {
  $r = Invoke-RestMethod -Uri $health -Method Get
  Write-Host "Nadir health: $($r | ConvertTo-Json -Compress)" -ForegroundColor Green
} catch {
  Write-Host "Nadir not responding at $health yet. Check: docker compose logs nadir" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Base URL (OpenAI-compatible): http://127.0.0.1:8765/v1" -ForegroundColor Green
Write-Host 'Set your client (Cursor) base to that, and add routing: JSON "nadir": { "lines": <int>, "multi_file": false, "complex": false }' -ForegroundColor Cyan
Write-Host "Or send headers: X-Nadir-Lines, X-Nadir-Multi-File, X-Nadir-Complex" -ForegroundColor Cyan
Write-Host 'Tailscale: on the host run: tailscale serve --bg 8765  (or use your tailnet IP).' -ForegroundColor Cyan
