from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException


def parse_filter(filter_param: str | None) -> dict[str, Any]:
    if not filter_param:
        return {}
    try:
        parsed = json.loads(filter_param)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid filter") from exc
    if isinstance(parsed, dict):
        return parsed
    return {}


def list_response(items: list[Any], total: int) -> dict[str, Any]:
    return {"data": items, "total": total}
