# PeaBrain

**PeaBrain** is a small **sovereign AI coding stack** for the desktop: a local **OpenAI-compatible** API (**NadirClaw**) in front of **Ollama**, with optional **OpenRouter** for cloud escalation, a **PeaBrain** browser demo, and helpers for **Cursor** and public tunnels.

All implementation and full documentation live under **`sovereign-stack/`**.

## Quick start

1. `cd sovereign-stack`
2. Copy **`.env.example` → `.env`** and set at least what you need (local-only works without cloud keys; see the stack README).
3. `.\setup.ps1` (Windows) or **`./setup.sh`**, or **`npm run stack:up`**.

Then open **`http://127.0.0.1:8765/demo/`** and read **[sovereign-stack/README.md](sovereign-stack/README.md)** for routing, **CURSOR.md**, public URL, and tuning.

## Repository layout

| Path | What |
|------|------|
| **[sovereign-stack/](sovereign-stack/)** | Docker, NadirClaw (FastAPI), Ollama, `demo/`, scripts |

## License

Use the license of the parent project, or add a `LICENSE` at this root if you publish this folder on its own.
