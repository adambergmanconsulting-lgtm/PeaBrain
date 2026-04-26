from __future__ import annotations

import os
import subprocess
from pathlib import Path

_NODE_CWD = Path(os.environ.get("NADIR_NODE_CWD", "/app"))


def run_eslint_on_file(
    path: Path, eslint_config: Path, cwd: Path | None = None
) -> tuple[bool, str]:
    if not path.exists() or path.stat().st_size == 0:
        return True, ""
    work = cwd or _NODE_CWD
    env = {**os.environ, "NODE_NO_WARNINGS": "1"}
    p = subprocess.run(
        [
            "npx",
            "--no-install",
            "eslint",
            "-c",
            str(eslint_config),
            str(path),
            "--max-warnings",
            "0",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(work),
        env=env,
    )
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode == 0, out.strip()
