from __future__ import annotations

from typing import Protocol

from xianyu_tools.models import RawSourceItem


class SourceAdapter(Protocol):
    def search(
        self,
        keyword: str,
        *,
        limit: int = 20,
        source: int = 0,
        page: int = 1,
    ) -> list[RawSourceItem]:
        """Return lightweight upstream candidates in the common RawSourceItem shape."""

    def detail(self, item_id_or_url: str, *, source: int = 1) -> RawSourceItem:
        """Return one enriched upstream item in the common RawSourceItem shape."""
