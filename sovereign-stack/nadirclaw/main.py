from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Request
from starlette.middleware.cors import CORSMiddleware
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    StreamingResponse,
)

from nadirclaw.context.prompt_minify import minify_messages_for_local
from nadirclaw.nadirclaw_config import NadirclawConfig, load_config
from nadirclaw.providers.openai_like import post_chat, post_chat_stream
from nadirclaw.quality.verify import verify_response_text
from nadirclaw.router import decide_route, pop_nadir_metadata
from nadirclaw.url_fetch import fetch_url_to_text
from nadirclaw.web_search import run_web_search, search_provider_for

app = FastAPI(title="NadirClaw", version="0.1.0")
_cfg: NadirclawConfig | None = None

# Comma-separated origins, e.g. "http://127.0.0.1,http://localhost" or "*" (dev only)
_cors = (os.environ.get("NADIR_CORS_ORIGINS") or "").strip()
if _cors:
    _origs = [o.strip() for o in _cors.split(",") if o.strip()]
    if _origs:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=_origs,
            allow_methods=["*"],
            allow_headers=["*"],
        )


def get_cfg() -> NadirclawConfig:
    global _cfg
    if _cfg is None:
        _cfg = load_config()
    return _cfg


def _host_header_hostname(host_header: str) -> str:
    h = (host_header or "").strip().lower()
    if not h:
        return ""
    if h.startswith("["):
        end = h.find("]")
        return h[1:end] if end > 0 else h
    if h.count(":") == 1:  # hostname:port (incl. 127.0.0.1:8765)
        return h.split(":", 1)[0]
    return h  # no port, or unbracketed v6 in Host (rare)


def _bearer_bypass_by_host(request: Request) -> bool:
    """
    If the browser is opened at http://127.0.0.1/... or http://localhost/... the Host
    header targets loopback, so we can skip bearer; public hostnames (trycloudflare, etc.) still require the token.
    """
    h = _host_header_hostname(request.headers.get("host") or "")
    return h in ("127.0.0.1", "localhost", "::1", "0:0:0:0:0:0:0:1")


@app.middleware("http")
async def _inbound_bearer_middleware(request: Request, call_next):
    """Optional NADIR_INBOUND_BEARER_TOKEN: protect /v1 when exposed via a public tunnel."""
    cfg = get_cfg()
    tok = (cfg.inbound_bearer_token or "").strip()
    if not tok or request.method == "OPTIONS":
        return await call_next(request)
    p = request.url.path
    need = p.startswith("/v1") or (
        request.method == "POST"
        and p in ("/api/demo/web-search", "/api/demo/fetch-url")
    )
    if not need:
        return await call_next(request)
    if cfg.inbound_bearer_localhost_bypass and _bearer_bypass_by_host(request):
        return await call_next(request)
    auth = (request.headers.get("authorization") or "").strip()
    if auth == f"Bearer {tok}":
        return await call_next(request)
    return JSONResponse(
        {
            "error": {
                "message": "Invalid or missing bearer token. Set Nadir OpenAI API key to the same value as NADIR_INBOUND_BEARER_TOKEN when using a public base URL.",
                "type": "invalid_request_error",
            }
        },
        status_code=401,
    )


def _merge_nadir_from_headers(request: Request, d: dict[str, Any]) -> None:
    ln = request.headers.get("X-Nadir-Lines")
    if ln and "lines" not in d:
        try:
            d["lines"] = int(ln)
        except ValueError:
            pass
    v = (request.headers.get("X-Nadir-Multi-File") or "").lower()
    if v in ("1", "true", "yes"):
        d["multi_file"] = True
    v2 = (request.headers.get("X-Nadir-Complex") or "").lower()
    if v2 in ("1", "true", "yes"):
        d["complex"] = True


def _assistant_text(resp: dict[str, Any]) -> str:
    ch = (resp.get("choices") or [{}])[0] or {}
    msg = ch.get("message") or {}
    c = msg.get("content")
    if isinstance(c, str):
        return c
    if c is not None and isinstance(c, list):
        parts: list[str] = []
        for p in c:
            if isinstance(p, dict) and p.get("type") == "text" and p.get("text"):
                parts.append(str(p["text"]))
        if parts:
            return "\n".join(parts)
    return str(c) if c is not None else ""


def _lint_enabled(cfg: NadirclawConfig) -> bool:
    return cfg.verify_with_eslint or cfg.verify_with_prettier


def _self_correct_messages(
    messages: list[dict[str, Any]],
    first_assistant: str,
    err: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    out.extend(messages)
    out.append({"role": "assistant", "content": first_assistant})
    out.append(
        {
            "role": "user",
            "content": (
                "The previous code failed automated checks. Fix the issues; "
                "return only the corrected code in a fenced code block if applicable.\n\n"
                f"Diagnostics:\n{err}"
            ),
        }
    )
    return out


async def _synthesize_stream_from_response(
    resp: dict[str, Any]
) -> AsyncIterator[bytes]:
    text = _assistant_text(resp)
    ch0 = (resp.get("choices") or [{}])[0] or {}
    c0 = {
        **{k: v for k, v in ch0.items() if k != "message"},
        "index": 0,
        "delta": {"content": text, "role": "assistant"},
    }
    line = {
        "id": resp.get("id", "nadirclaw-synth"),
        "object": "chat.completion.chunk",
        "model": resp.get("model", ""),
        "created": resp.get("created", 0),
        "choices": [c0],
    }
    yield f"data: {json.dumps(line, ensure_ascii=False)}\n\n".encode("utf-8")
    yield b"data: [DONE]\n\n"


def _minify_msg_list(cfg: NadirclawConfig, b: dict[str, Any]) -> None:
    if not cfg.minify_local_messages or not isinstance(b.get("messages"), list):
        return
    b["messages"] = minify_messages_for_local(
        b["messages"]  # type: ignore[arg-type]
    )


async def _handle_local(
    cfg: NadirclawConfig,
    b0: dict[str, Any],
    nadir: dict[str, Any],
    wants_stream: bool,
) -> JSONResponse | StreamingResponse:
    if not _lint_enabled(cfg) and wants_stream:
        bs = {**b0, "stream": True}
        _minify_msg_list(cfg, bs)
        return StreamingResponse(
            post_chat_stream(cfg, to_local=True, body=bs), media_type="text/event-stream"
        )
    b = {**b0, "stream": False}
    _minify_msg_list(cfg, b)
    if not _lint_enabled(cfg):
        r = await post_chat(cfg, to_local=True, body=b)
        return JSONResponse(r)

    r1 = await post_chat(cfg, to_local=True, body=b)
    t1 = _assistant_text(r1)
    v1 = verify_response_text(cfg, t1, nadir)
    if v1.ok or not cfg.self_correct_local_once:
        if wants_stream:
            return StreamingResponse(
                _synthesize_stream_from_response(r1), media_type="text/event-stream"
            )
        return JSONResponse(r1)

    msgs = b.get("messages")
    if not isinstance(msgs, list):
        raise HTTPException(500, "messages is not a list")
    b2: dict[str, Any] = {
        **b,
        "messages": _self_correct_messages(msgs, t1, v1.detail),
    }
    _minify_msg_list(cfg, b2)
    r2 = await post_chat(cfg, to_local=True, body=b2)
    t2 = _assistant_text(r2)
    v2 = verify_response_text(cfg, t2, nadir)
    if v2.ok or not (cfg.openrouter_api_key or "").strip():
        if wants_stream:
            return StreamingResponse(
                _synthesize_stream_from_response(r2), media_type="text/event-stream"
            )
        return JSONResponse(r2)

    b3c = {**b0, "stream": False}
    if wants_stream:
        return StreamingResponse(
            post_chat_stream(cfg, to_local=False, body=b3c), media_type="text/event-stream"
        )
    r3 = await post_chat(cfg, to_local=False, body=b3c)
    return JSONResponse(r3)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/demo/web-search/config")
def demo_web_search_config() -> JSONResponse:
    """Tells the PeaBrain HTML demo whether server-side search is available (no secrets)."""
    c = get_cfg()
    p = search_provider_for(c)
    return JSONResponse(
        {
            "configured": p is not None,
            "provider": p,
            "max_results": c.web_search_max_results,
        }
    )


@app.post("/api/demo/web-search")
async def demo_web_search(body: dict[str, Any] = Body(...)) -> JSONResponse:
    """
    PeaBrain demo: run a web search using Tavily (preferred) or Brave API key from env.
    """
    c = get_cfg()
    q = (body.get("q") or "").strip()
    text, err = await run_web_search(c, q)
    if err:
        if "not configured" in err:
            return JSONResponse({"ok": False, "error": err}, status_code=503)
        if err == "empty query":
            return JSONResponse({"ok": False, "error": err}, status_code=400)
        return JSONResponse({"ok": False, "error": err}, status_code=502)
    return JSONResponse({"ok": True, "text": text})


@app.post("/api/demo/fetch-url")
async def demo_fetch_url(body: dict[str, Any] = Body(...)) -> JSONResponse:
    """PeaBrain demo: fetch a public URL and return plain text (SSRF-filtered)."""
    c = get_cfg()
    u = (body.get("url") or "").strip()
    text, err = await fetch_url_to_text(
        u,
        max_bytes=c.demo_url_fetch_max_bytes,
        max_text_chars=c.demo_url_fetch_max_text,
    )
    if err:
        return JSONResponse({"ok": False, "error": err, "url": u}, status_code=400)
    return JSONResponse({"ok": True, "text": text, "url": u})


@app.get("/v1/models")
def list_models() -> JSONResponse:
    c = get_cfg()
    return JSONResponse(
        {
            "object": "list",
            "data": [
                {
                    "id": c.local_model,
                    "object": "model",
                    "owned_by": "nadirclaw-local",
                },
                {
                    "id": c.cloud_model,
                    "object": "model",
                    "owned_by": "openrouter",
                },
            ],
        }
    )


@app.post("/v1/chat/completions", response_model=None)
async def chat_completions(
    request: Request,
    body: dict[str, Any] = Body(...),
) -> JSONResponse | StreamingResponse:
    cfg = get_cfg()
    clean, n0 = pop_nadir_metadata(body)
    n: dict[str, Any] = dict(n0) if n0 else {}
    _merge_nadir_from_headers(request, n)
    route, _reason = decide_route(cfg, n)
    if route == "cloud" and not (cfg.openrouter_api_key or "").strip():
        raise HTTPException(503, "Set NADIR_OPENROUTER_API_KEY for cloud routing")

    wants_stream = bool(clean.get("stream"))
    b0 = {**clean}
    b0["stream"] = False
    b0.pop("nadir", None)

    if route == "cloud" and wants_stream:
        return StreamingResponse(
            post_chat_stream(cfg, to_local=False, body=b0), media_type="text/event-stream"
        )
    if route == "cloud":
        r = await post_chat(cfg, to_local=False, body=b0)
        return JSONResponse(r)

    return await _handle_local(cfg, b0, n, wants_stream)


def _resolve_peabrain_index_html() -> Path | None:
    """
    1) NADIR_DEMO_INDEX in env
    2) demo/index.html next to the nadirclaw package (Docker: /app/demo; bind mount if present)
    3) ./demo under cwd
    4) nadirclaw/bundled_peabrain.html — always copied into the image; survives an empty
       or wrong host bind mount on ./demo:./app/demo
    """
    candidates: list[Path] = []
    envp = (os.environ.get("NADIR_DEMO_INDEX") or "").strip()
    if envp:
        candidates.append(Path(envp))
    candidates.append(Path(__file__).resolve().parent.parent / "demo" / "index.html")
    candidates.append(Path.cwd() / "demo" / "index.html")
    candidates.append(Path(__file__).resolve().parent / "bundled_peabrain.html")
    seen: set[Path] = set()
    for p in candidates:
        key = p.resolve()
        if key in seen:
            continue
        seen.add(key)
        if p.is_file():
            return p
    return None


_PEABRAIN_MISSING = """<!DOCTYPE html>
<html><head><meta charset="utf-8"/><title>PeaBrain demo — missing</title></head>
<body style="font-family:system-ui;padding:1.5rem;max-width:40rem">
<h1>PeaBrain demo: index.html not found</h1>
<p>The server could not read <code>demo/index.html</code>. In Docker, ensure
<code>docker-compose.yml</code> bind-mounts <code>./demo</code> to
<code>/app/demo</code> and restart: <code>docker compose up -d</code>.
Or rebuild: <code>docker compose up -d --build</code> from <code>sovereign-stack/</code>.
</p>
<p>API still works: <a href="/docs">/docs</a>, <a href="/v1/models">/v1/models</a>, <a href="/health">/health</a>.</p>
</body></html>"""


@app.get("/")
def peabrain_root() -> RedirectResponse:
    return RedirectResponse(url="/demo/", status_code=302)


@app.get("/demo", include_in_schema=False)
def peabrain_demo_no_slash() -> RedirectResponse:
    return RedirectResponse(url="/demo/", status_code=308)


@app.get("/demo/", include_in_schema=False, response_model=None)
def peabrain_demo() -> FileResponse | HTMLResponse:
    path = _resolve_peabrain_index_html()
    if path is not None and path.is_file():
        return FileResponse(path, media_type="text/html; charset=utf-8")
    return HTMLResponse(
        _PEABRAIN_MISSING,
        status_code=503,
        media_type="text/html; charset=utf-8",
    )
