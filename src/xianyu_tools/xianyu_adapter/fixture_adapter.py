from __future__ import annotations

import json
from pathlib import Path

from xianyu_tools.models import XianyuDetailItem, XianyuSearchItem, XianyuSellerProfile
from xianyu_tools.xianyu_adapter.parsers import (
    parse_xianyu_detail,
    parse_xianyu_search_results,
    parse_xianyu_seller_profile,
)
from xianyu_tools.xianyu_adapter.playwright_adapter import XianyuAdapterError


class FixtureXianyuAdapter:
    """
    Replay adapter for captured Xianyu JSON payloads.

    Expected layout:

    fixtures/
      search/
        <keyword_slug>/page_1.json
      detail/
        <item_id>.json
      seller/
        <user_id>/head.json
        <user_id>/ratings.json
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def search(self, keyword: str, *, page: int = 1) -> list[XianyuSearchItem]:
        payload = self._load_json(self.root / "search" / _slugify(keyword) / f"page_{page}.json")
        return parse_xianyu_search_results(payload)

    def detail(self, item_url_or_id: str) -> XianyuDetailItem:
        item_id = item_url_or_id.split("id=")[-1].split("&")[0].strip()
        payload = self._load_json(self.root / "detail" / f"{item_id}.json")
        return parse_xianyu_detail(payload, item_url=item_url_or_id)

    def seller(self, user_id: str) -> XianyuSellerProfile:
        base_dir = self.root / "seller" / user_id
        head_payload = self._load_json(base_dir / "head.json")
        ratings_path = base_dir / "ratings.json"
        ratings_payload = self._load_json(ratings_path) if ratings_path.exists() else None
        return parse_xianyu_seller_profile(head_payload, ratings_payload)

    def _load_json(self, path: Path) -> dict | list:
        if not path.exists():
            raise XianyuAdapterError(f"fixture file not found: {path}")
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)


def _slugify(keyword: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in keyword.strip())
    parts = [part for part in cleaned.split("-") if part]
    return "-".join(parts) or "default"
