from __future__ import annotations

from typing import Protocol

from xianyu_tools.models import HotItem


class HotlistAdapter(Protocol):
    def list_hot_items(self, *, platform: str | None = None, limit: int = 20) -> list[HotItem]:
        """Return hot-selling items in the common HotItem shape."""
