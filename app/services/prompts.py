from __future__ import annotations

from functools import lru_cache

from app.core.config import PROMPTS_DIR


@lru_cache
def load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""
