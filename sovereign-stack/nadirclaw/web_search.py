"""Server-side web search for the PeaBrain demo (keys stay in NADIR_ env, not the browser)."""

from __future__ import annotations

from typing import Any, Literal

import httpx

from nadirclaw.nadirclaw_config import NadirclawConfig

Provider = Literal["tavily", "brave"]


def search_provider_for(cfg: NadirclawConfig) -> Provider | None:
    if (cfg.tavily_api_key or "").strip():
        return "tavily"
    if (cfg.brave_search_api_key or "").strip():
        return "brave"
    return None


def format_results(query: str, items: list[dict[str, str]]) -> str:
    if not items:
        return f'[No web results returned for: "{query}"]'
    lines: list[str] = [
        f'[Web search for "{query}" — snippets may be wrong or dated; verify important facts.]',
        "",
    ]
    for i, it in enumerate(items, start=1):
        title = it.get("title") or "(no title)"
        url = it.get("url") or ""
        body = (it.get("content") or it.get("description") or "").strip()
        lines.append(f"{i}) {title}")
        if url:
            lines.append(f"   {url}")
        if body:
            for part in body.splitlines()[:8]:
                lines.append(f"   {part}")
        lines.append("")
    return "\n".join(lines).strip()


async def _tavily(cfg: NadirclawConfig, q: str) -> list[dict[str, str]]:
    key = (cfg.tavily_api_key or "").strip()
    n = min(max(cfg.web_search_max_results, 1), 10)
    payload: dict[str, Any] = {
        "api_key": key,
        "query": q,
        "max_results": n,
        "search_depth": "basic",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post("https://api.tavily.com/search", json=payload)
        r.raise_for_status()
        data = r.json()
    out: list[dict[str, str]] = []
    for it in (data.get("results") or [])[:n]:
        if not isinstance(it, dict):
            continue
        out.append(
            {
                "title": str(it.get("title") or ""),
                "url": str(it.get("url") or ""),
                "content": str(it.get("content") or ""),
            }
        )
    return out


async def _brave(cfg: NadirclawConfig, q: str) -> list[dict[str, str]]:
    key = (cfg.brave_search_api_key or "").strip()
    n = min(max(cfg.web_search_max_results, 1), 10)
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {"X-Subscription-Token": key, "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, params={"q": q, "count": n}, headers=headers)
        r.raise_for_status()
        data = r.json()
    out: list[dict[str, str]] = []
    web = data.get("web") or {}
    results = web.get("results") or []
    for it in results[:n]:
        if not isinstance(it, dict):
            continue
        title = str(it.get("title") or "")
        u = str(it.get("url") or "")
        es = it.get("extra_snippets")
        if isinstance(es, list) and es:
            desc = str(es[0])
        else:
            desc = str(it.get("description") or "")
        out.append({"title": title, "url": u, "content": desc})
    return out


async def run_web_search(cfg: NadirclawConfig, q: str) -> tuple[str, str]:
    """
    Returns (formatted_block, error_message). error_message is empty on success.
    """
    q = (q or "").strip()
    if not q:
        return "", "empty query"

    prov = search_provider_for(cfg)
    if not prov:
        return "", "web search is not configured (set NADIR_TAVILY_API_KEY or NADIR_BRAVE_SEARCH_API_KEY)"

    try:
        if prov == "tavily":
            items = await _tavily(cfg, q)
        else:
            items = await _brave(cfg, q)
    except httpx.HTTPStatusError as e:
        err = (e.response.text or "")[:500]
        return "", f"search HTTP {e.response.status_code}: {err}"
    except httpx.RequestError as e:
        return "", f"search request failed: {e}"

    text = format_results(q, items)
    return text, ""
