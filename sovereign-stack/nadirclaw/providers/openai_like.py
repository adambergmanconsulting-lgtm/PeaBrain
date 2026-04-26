from __future__ import annotations

from typing import Any, AsyncIterator

import httpx
from fastapi import HTTPException

from nadirclaw.nadirclaw_config import NadirclawConfig


def _openrouter_headers(cfg: NadirclawConfig) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {cfg.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": cfg.openrouter_referer,
        "X-Title": cfg.openrouter_title,
    }


def _set_model(base_body: dict[str, Any], model: str) -> dict[str, Any]:
    return {**base_body, "model": model}


def _local_headers() -> dict[str, str]:
    return {"Content-Type": "application/json"}


async def post_chat(
    cfg: NadirclawConfig,
    *,
    to_local: bool,
    body: dict[str, Any],
) -> dict[str, Any]:
    url = cfg.local_chat_url if to_local else cfg.openrouter_chat_url
    model = cfg.local_model if to_local else cfg.cloud_model
    out = _set_model(body, model)
    t = cfg.local_timeout_s if to_local else cfg.cloud_timeout_s
    headers = _local_headers() if to_local else _openrouter_headers(cfg)
    try:
        async with httpx.AsyncClient(timeout=t) as client:
            r = await client.post(url, json=out, headers=headers)
            r.raise_for_status()
            return r.json()
    except httpx.HTTPStatusError as e:
        u = "ollama" if to_local else "openrouter"
        text = (e.response.text or "")[:4000]
        status = e.response.status_code
        if not to_local and status in (401, 403):
            raise HTTPException(
                502,
                detail=f"OpenRouter rejected the request (HTTP {status}). Check NADIR_OPENROUTER_API_KEY. {text}",
            ) from e
        tail = text if text else str(e)
        raise HTTPException(502, detail=f"Upstream {u} error HTTP {status}: {tail}") from e
    except httpx.RequestError as e:
        u = "ollama" if to_local else "openrouter"
        raise HTTPException(503, detail=f"Could not reach {u}: {e}") from e


async def post_chat_stream(
    cfg: NadirclawConfig,
    *,
    to_local: bool,
    body: dict[str, Any],
) -> AsyncIterator[bytes]:
    url = cfg.local_chat_url if to_local else cfg.openrouter_chat_url
    model = cfg.local_model if to_local else cfg.cloud_model
    out = {**_set_model(body, model), "stream": True}
    t = cfg.local_timeout_s if to_local else cfg.cloud_timeout_s
    if to_local:
        h = {**_local_headers(), "Accept": "text/event-stream"}
    else:
        h = {**_openrouter_headers(cfg), "Accept": "text/event-stream"}
    try:
        async with httpx.AsyncClient(timeout=t) as client:
            async with client.stream("POST", url, json=out, headers=h) as r:
                r.raise_for_status()
                async for chunk in r.aiter_bytes():
                    if chunk:
                        yield chunk
    except httpx.HTTPStatusError as e:
        u = "ollama" if to_local else "openrouter"
        text = (e.response.text or "")[:4000]
        tail = text if text else str(e)
        raise HTTPException(
            502,
            detail=f"Upstream {u} stream error HTTP {e.response.status_code}: {tail}",
        ) from e
    except httpx.RequestError as e:
        u = "ollama" if to_local else "openrouter"
        raise HTTPException(503, detail=f"Could not reach {u}: {e}") from e
