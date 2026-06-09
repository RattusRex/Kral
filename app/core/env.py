"""Minimal `.env` loading without external dependencies.

This mirrors the behaviour of ``scripts/load-env.mjs`` so that the FastAPI
backend reads ``DATABASE_URL`` from a project-level ``.env`` file when it is
started directly (for example via ``npm run dev:backend`` or ``uvicorn``)
instead of through ``scripts/dev.mjs``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict


def parse_env(content: str) -> Dict[str, str]:
    """Parse the contents of a ``.env`` file into key/value pairs."""

    result: Dict[str, str] = {}
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("export "):
            line = line[len("export "):].lstrip()

        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not key:
            continue

        value = value.strip()
        if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
            value = value[1:-1]
        else:
            comment_index = value.find(" #")
            if comment_index != -1:
                value = value[:comment_index].strip()

        result[key] = value

    return result


def load_env(start: Path | None = None) -> Dict[str, str]:
    """Load a ``.env`` file (searching upward from ``start``) into ``os.environ``.

    Existing environment variables take precedence, so values that are already
    set (including those exported by ``scripts/dev.mjs`` or by tests) are never
    overwritten.
    """

    if start is None:
        start = Path(__file__).resolve().parent

    env_path: Path | None = None
    for directory in [start, *start.parents]:
        candidate = directory / ".env"
        if candidate.is_file():
            env_path = candidate
            break

    if env_path is None:
        return {}

    applied: Dict[str, str] = {}
    for key, value in parse_env(env_path.read_text(encoding="utf-8")).items():
        if key not in os.environ:
            os.environ[key] = value
            applied[key] = value

    return applied
