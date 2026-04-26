from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from nadirclaw.nadirclaw_config import NadirclawConfig
from nadirclaw.quality.eslint_runner import run_eslint_on_file
from nadirclaw.quality.prettier_runner import run_prettier_check

_FENCE = re.compile(
    r"^```(?P<lang>[\w#+\-.]*)\s*\n(?P<code>.*?)^```\s*",
    re.DOTALL | re.MULTILINE,
)

_DEFAULT_ESLINT = Path("/app/linters/.eslintrc.cjs")


@dataclass
class VerificationResult:
    ok: bool
    detail: str
    workdir: Path
    file_path: Path | None


def _pick_extension(nadir_lang: str | None, fence_lang: str) -> str:
    if nadir_lang:
        l = nadir_lang.lower().strip()
    else:
        l = (fence_lang or "typescript").lower().strip()
    if "tsx" in l or l == "typescriptreact":
        return "tsx"
    if "jsx" in l or l == "javascriptreact" or l == "jsx":
        return "jsx"
    if l in ("ts", "typescript"):
        return "ts"
    if l in ("js", "javascript", "mjs", "cjs"):
        return "js"
    if "ts" in l:
        return "ts"
    if "js" in l:
        return "js"
    return "ts"


def _is_jsish(ext: str) -> bool:
    return ext in ("ts", "tsx", "js", "jsx", "mjs", "cjs")


def _extract_fenced_code(text: str) -> tuple[str, str] | None:
    best: tuple[str, int, str] | None = None
    for m in _FENCE.finditer(text):
        code = m.group("code") or ""
        lang = (m.group("lang") or "").strip() or "text"
        L = len(code)
        if not code.strip() or not _is_jsish(_pick_extension(None, lang)):
            continue
        if best is None or L > best[1]:
            best = (code, L, lang)
    if best:
        return best[0], best[2]
    # Do not treat plain prose (e.g. "hi!") as TypeScript; that spuriously fails Prettier/ESLint
    # and can trigger self-correct or cloud paths. Only verify explicit ``` js/ts/... blocks.
    return None


def verify_response_text(
    cfg: NadirclawConfig,
    assistant_text: str,
    nadir: dict,
) -> VerificationResult:
    d = nadir or {}
    if len(assistant_text) > cfg.max_verify_chars:
        return VerificationResult(
            True, "verify skipped: response too long", Path("."), None
        )

    hit = _extract_fenced_code(assistant_text)
    if hit is None:
        return VerificationResult(
            True,
            "no JS/TS fenced code block to verify; pass",
            Path("."),
            None,
        )
    code, fence_lang = hit
    ext = _pick_extension(d.get("language"), fence_lang)
    if not _is_jsish(ext):
        return VerificationResult(
            True, f"skipping verify for .{ext}", Path("."), None
        )

    tmpd = Path(tempfile.mkdtemp(prefix="nadir_"))
    fp = tmpd / f"verify.{ext}"
    fp.write_text(code, encoding="utf-8")

    (tmpd / "package.json").write_text('{"type":"commonjs"}\n', encoding="utf-8")

    parts: list[str] = []
    if cfg.verify_with_prettier:
        ok_p, msg_p = run_prettier_check(fp)
        if not ok_p:
            parts.append("Prettier:\n" + (msg_p or "failed"))
    if cfg.verify_with_eslint and _DEFAULT_ESLINT.is_file():
        ok_e, msg_e = run_eslint_on_file(fp, _DEFAULT_ESLINT)
        if not ok_e:
            parts.append("ESLint:\n" + (msg_e or "failed"))
    elif cfg.verify_with_eslint and not _DEFAULT_ESLINT.is_file():
        parts.append("ESLint: skipped (no /app/linters/.eslintrc.cjs)")

    ok = len(parts) == 0
    return VerificationResult(ok, "\n".join(parts) if parts else "ok", tmpd, fp)
