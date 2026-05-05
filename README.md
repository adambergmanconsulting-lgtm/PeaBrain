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

## Phased plan

Work is **incremental**: later phases add services or packages **next to** the core stack, not by replacing it.

| Phase | Focus | Outcome |
|--------|--------|--------|
| **0 — Current** | One machine, **Nadir + Ollama**, OpenAI-compatible **`/v1`**, IDE mode, PeaBrain **web demo**, optional **OpenRouter**, **cloudflared/ngrok** helpers, **[CURSOR.md](sovereign-stack/CURSOR.md)** for editors | Local-first coding assistant API + demo; Cursor/Cline can point at Nadir when the editor supports it |
| **1 — Useful in real repos** | **MCP** (or equivalent) for **read / search / optional commands** scoped to a workspace; **editor rules** (e.g. AGENTS.md / project docs) that point at canonical READMEs and **`npm run …`** checks | Model stays on **Nadir/Ollama**; **tools** supply repo truth so monorepos like large TS apps are workable without pasting whole trees |
| **2 — Safety & quality hooks** | **Privacy / de-identification** before any **non-local** send; optional **stricter verification** (e.g. typecheck-style hooks) aligned with project scripts; light **orchestration** (multi-step / verifier patterns) where it pays off | Safer sharing story + fewer broken edits from one-shot replies |
| **3 — Swarm & economics (later)** | Trusted **P2P** (e.g. Tailscale), **compute credits**, idle worker, optional **global / DeAI** paths | Requires trust, security review, and protocol design — **separate subsystems** under the PeaBrain umbrella, not a rewrite of Nadir |

**Principle:** keep **Nadir** as the stable **OpenAI-shaped engine**; hang **MCP**, shredders, and swarm logic **around** it.

## License

Use the license of the parent project, or add a `LICENSE` at this root if you publish this folder on its own.
