"""Route requests to local Ollama vs OpenRouter from body metadata."""

from __future__ import annotations

from typing import Any, Literal

from nadirclaw.nadirclaw_config import NadirclawConfig

Route = Literal["local", "cloud"]


def pop_nadir_metadata(body: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    b = {k: v for k, v in body.items() if k != "nadir"}
    n = body.get("nadir") or {}
    if not isinstance(n, dict):
        n = {}
    return b, n


def decide_route(cfg: NadirclawConfig, nadir: dict) -> tuple[Route, str]:
    use_cloud = bool(nadir.get("use_cloud", False))
    if cfg.ide_mode:
        if use_cloud and (cfg.openrouter_api_key or "").strip():
            return "cloud", "nadir.use_cloud in ide_mode"
        if use_cloud and not (cfg.openrouter_api_key or "").strip():
            return "local", "ide_mode: use_cloud requested but no OpenRouter key"
        if cfg.use_complexity_flag and nadir.get("complex") and (cfg.openrouter_api_key or "").strip():
            return "cloud", "nadir.complex in ide_mode"
        return "local", "ide_mode: local only"

    lines = nadir.get("lines")
    multi = bool(nadir.get("multi_file", False))
    complex_ = bool(nadir.get("complex", False))

    if cfg.use_complexity_flag and complex_:
        return "cloud", "nadir.complex=true"

    if lines is None:
        if cfg.on_missing_metadata == "local":
            return "local", f"missing lines; on_missing=local"
        return "cloud", f"missing lines; on_missing=cloud"

    try:
        li = int(lines)
    except (TypeError, ValueError):
        if cfg.on_missing_metadata == "local":
            return "local", "lines not int; on_missing=local"
        return "cloud", "lines not int; on_missing=cloud"

    if multi:
        return "cloud", "multi_file=True"
    if li > cfg.max_lines_for_local:
        return "cloud", f"lines {li} > {cfg.max_lines_for_local}"
    return "local", f"lines {li} <= {cfg.max_lines_for_local}, single file"
