#!/usr/bin/env bash
# Download, build, and start NadirClaw + Ollama. Requires Docker Engine and Compose v2.
# If Node is present, uses CVReady-style scripts/ensure-docker.js + scripts/compose-up.js.
# Usage: ./setup.sh   |   ./setup.sh --skip-model-pull
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

SKIP_PULL=0
if [[ "${1:-}" == "--skip-model-pull" ]]; then
  SKIP_PULL=1
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example. Set NADIR_OPENROUTER_API_KEY for cloud routing."
else
  echo "Using existing .env"
fi

echo "Building and starting services (Ollama + Nadir)..."
if command -v node >/dev/null 2>&1 && [[ -f "$ROOT/scripts/compose-up.js" ]]; then
  node "$ROOT/scripts/compose-up.js"
else
  if ! command -v docker >/dev/null 2>&1; then
    echo "Install Docker: https://docs.docker.com/get-docker/" >&2
    exit 1
  fi
  if ! docker info >/dev/null 2>&1; then
    echo "Docker is installed, but the daemon is not running. Start Docker and run again." >&2
    echo "Or install Node.js and re-run: Node will run scripts/ensure-docker.js (can start Docker Desktop on Windows/macOS)." >&2
    exit 1
  fi
  if ! docker compose version >/dev/null 2>&1; then
    echo "Install Docker Compose v2 (plugin) and run again." >&2
    exit 1
  fi
  docker compose -f "$ROOT/docker-compose.yml" up -d --build
fi

MODEL="qwen2.5-coder:14b"
if [[ -f .env ]]; then
  M="$(grep -E '^\s*NADIR_LOCAL_MODEL=' .env | head -1 | cut -d= -f2- | tr -d " '\"")"
  if [[ -n "$M" ]]; then
    MODEL="$M"
  fi
fi

if [[ "$SKIP_PULL" -eq 1 ]]; then
  echo "Skipped Ollama model pull. Run: docker compose exec ollama ollama pull $MODEL"
else
  echo "Pulling Ollama model: $MODEL (can take a while)..."
  docker compose -f "$ROOT/docker-compose.yml" exec -T ollama ollama pull "$MODEL"
fi

sleep 1
if curl -fsS "http://127.0.0.1:8765/health" >/dev/null; then
  echo "Nadir is up."
  curl -fsS "http://127.0.0.1:8765/health" || true
else
  echo "Nadir not responding on :8765 yet. Check: docker compose logs nadir" >&2
fi

echo ""
echo "Base URL: http://127.0.0.1:8765/v1"
echo "Routing: add body key \"nadir\": { \"lines\": <n>, \"multi_file\": false } or headers X-Nadir-Lines, etc."
echo "Tailscale: run on the host, then: tailscale serve --bg 8765   (or use tailnet IP)"
