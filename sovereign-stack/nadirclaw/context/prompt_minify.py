"""
Strip block comments and collapse extra blank lines in *string* user/assistant
content to reduce input tokens. Only applied to the local path when enabled.

Does not run inside code fences heuristics—keeps implementation predictable.
For production codebases with sensitive string literals, disable via NADIR_MINIFY_LOCAL_MESSAGES=0.
"""

from __future__ import annotations

import re
from typing import Any

_BLANK = re.compile(r"\n[ \t]*\n[ \t]*\n+")
# Block comments: /* ... */ and // full lines (lossy; optional)
_C_BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)
_PY_HASH = re.compile(r"^\s*#.*$", re.MULTILINE)


def _minify_text(s: str) -> str:
    t = _C_BLOCK.sub(" ", s)
    t = _PY_HASH.sub("", t)
    t = _BLANK.sub("\n\n", t)
    return t.strip()


def minify_messages_for_local(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        role = m.get("role")
        c = m.get("content")
        if isinstance(c, str) and role in ("user", "assistant", "system"):
            out.append({**m, "content": _minify_text(c)})
        else:
            out.append(m)
    return out
