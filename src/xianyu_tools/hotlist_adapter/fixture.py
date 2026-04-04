from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from xianyu_tools.models import HotItem


class FixtureHotlistAdapter:
    def __init__(self, hot_items: list[dict[str, Any]]) -> None:
        self._hot_items = [self._parse_hot_item(item) for item in hot_items]

    @classmethod
    def from_file(cls, path: str | Path) -> "FixtureHotlistAdapter":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            rows = payload.get("hot_items") or []
        else:
            rows = payload
        if not isinstance(rows, list):
            raise ValueError("fixture hotlist must be a list or contain a 'hot_items' list")
        return cls(rows)

    def list_hot_items(self, *, platform: str | None = None, limit: int = 20) -> list[HotItem]:
        filtered = self._hot_items
        if platform:
            filtered = [item for item in filtered if item.platform == platform]
        return filtered[:limit]

    @staticmethod
    def _parse_hot_item(row: dict[str, Any]) -> HotItem:
        return HotItem(
            hot_item_id=str(row.get("hot_item_id") or row.get("item_id") or ""),
            platform=str(row.get("platform") or ""),
            title=str(row.get("title") or ""),
            price=_to_float(row.get("price")),
            want_count=_to_int_or_none(row.get("want_count")),
            seller_name=_to_str_or_none(row.get("seller_name")),
            area=_to_str_or_none(row.get("area")),
            sales_volume=_to_int_or_none(row.get("sales_volume")),
            hot_score=_to_float_or_none(row.get("hot_score")),
            item_url=str(row.get("item_url") or ""),
            image_url=_to_str_or_none(row.get("image_url")),
            metadata=dict(row.get("metadata") or row.get("source_snapshot") or {}),
        )


def _to_float(value: Any) -> float:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return 0.0


def _to_float_or_none(value: Any) -> float | None:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _to_int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
