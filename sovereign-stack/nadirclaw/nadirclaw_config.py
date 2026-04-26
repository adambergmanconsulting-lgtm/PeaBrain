"""Runtime configuration (env: NADIR_*). See .env.example."""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class NadirclawConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="NADIR_",
    )

    # URLs
    local_base: str = Field(
        default="http://ollama:11434/v1",
        description="OpenAI-compatible base for local engine (Ollama /v1).",
    )
    openrouter_base: str = "https://openrouter.ai/api/v1"

    # Models
    local_model: str = "qwen2.5-coder:14b"
    cloud_model: str = "anthropic/claude-3.5-sonnet"

    # Routing
    max_lines_for_local: int = 650
    on_missing_metadata: Literal["local", "cloud"] = "cloud"
    # "complex" in the `nadir` object forces OpenRouter
    use_complexity_flag: bool = True
    # When true, force local (Ollama) for all requests except optional nadir.use_cloud / nadir.complex
    # with a valid OpenRouter key—intended for IDEs (Cursor) that cannot send custom `nadir` fields.
    ide_mode: bool = False

    # Keys (cloud)
    openrouter_api_key: str = ""

    # If set, require `Authorization: Bearer <token>` on /v1/* (for public tunnels). /health and /demo stay open.
    inbound_bearer_token: str = ""
    # If true (default), skip that check when the HTTP Host is 127.0.0.1, localhost, or ::1 (local browser).
    # Set to false to require the token even on localhost (e.g. full prod-like tests).
    inbound_bearer_localhost_bypass: bool = True

    # Demo: server-side web search (see /api/demo/web-search)
    tavily_api_key: str = ""
    brave_search_api_key: str = ""
    web_search_max_results: int = 5
    # Demo: fetch pasted URLs (see /api/demo/fetch-url)
    demo_url_fetch_max_bytes: int = 1_000_000
    demo_url_fetch_max_text: int = 32_000

    # OpenRouter optional headers
    openrouter_referer: str = "https://github.com/local/nadirclaw"
    openrouter_title: str = "NadirClaw"

    # Local prompt budget
    minify_local_messages: bool = True

    # Verification (local only)
    verify_with_eslint: bool = True
    verify_with_prettier: bool = True
    self_correct_local_once: bool = True
    max_verify_chars: int = 120_000

    # Timeouts
    local_timeout_s: float = 600.0
    cloud_timeout_s: float = 600.0

    @property
    def local_chat_url(self) -> str:
        base = self.local_base.rstrip("/")
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"

    @property
    def openrouter_chat_url(self) -> str:
        b = self.openrouter_base.rstrip("/")
        return f"{b}/chat/completions"


def load_config() -> NadirclawConfig:
    return NadirclawConfig()
