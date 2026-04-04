from __future__ import annotations

from typing import Protocol

from xianyu_tools.models import XianyuDetailItem, XianyuSearchItem, XianyuSellerProfile


class XianyuAdapter(Protocol):
    def search(self, keyword: str, *, page: int = 1) -> list[XianyuSearchItem]:
        """Search Xianyu items for a keyword."""

    def detail(self, item_url_or_id: str) -> XianyuDetailItem:
        """Fetch a single item detail from Xianyu."""

    def seller(self, user_id: str) -> XianyuSellerProfile:
        """Fetch a seller profile from Xianyu."""
