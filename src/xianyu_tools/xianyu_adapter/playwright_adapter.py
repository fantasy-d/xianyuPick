from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from xianyu_tools.models import XianyuDetailItem, XianyuSearchItem, XianyuSellerProfile
from xianyu_tools.xianyu_adapter.parsers import (
    parse_xianyu_detail,
    parse_xianyu_search_results,
    parse_xianyu_seller_profile,
)

if TYPE_CHECKING:
    from xianyu_tools.xianyu_adapter.browser_transport import PlaywrightBrowserConfig


class XianyuAdapterError(RuntimeError):
    pass


SearchTransport = Callable[[str, int], dict[str, Any]]
DetailTransport = Callable[[str], dict[str, Any]]
SellerTransport = Callable[[str], tuple[dict[str, Any], list[dict[str, Any]] | None]]


class PlaywrightXianyuAdapter:
    """
    Adapter boundary for a Playwright-based Xianyu scraper.

    The real browser automation is intentionally kept behind injectable
    transports so the parser and pipeline can be tested without a browser.
    A future implementation should wire these transports to:
    1. load login state into a Playwright context
    2. navigate search/detail/profile pages
    3. intercept JSON responses and feed them back here
    """

    def __init__(
        self,
        *,
        search_transport: SearchTransport | None = None,
        detail_transport: DetailTransport | None = None,
        seller_transport: SellerTransport | None = None,
    ) -> None:
        self.search_transport = search_transport
        self.detail_transport = detail_transport
        self.seller_transport = seller_transport

    @classmethod
    def from_browser(
        cls,
        *,
        config: "PlaywrightBrowserConfig | None" = None,
        async_playwright_factory: Any | None = None,
    ) -> "PlaywrightXianyuAdapter":
        from xianyu_tools.xianyu_adapter.browser_transport import PlaywrightBrowserTransport

        transport = PlaywrightBrowserTransport(
            config=config,
            async_playwright_factory=async_playwright_factory,
        )
        return cls(
            search_transport=transport.search_payload,
            detail_transport=transport.detail_payload,
            seller_transport=transport.seller_payload,
        )

    def search(self, keyword: str, *, page: int = 1) -> list[XianyuSearchItem]:
        if self.search_transport is None:
            raise XianyuAdapterError("search transport is not configured")
        payload = self.search_transport(keyword, page)
        return parse_xianyu_search_results(payload)

    def search_all(
        self,
        keyword: str,
        *,
        max_pages: int = 5,
        require_chaozan_fish_shop: bool = False,
    ) -> list[XianyuSearchItem]:
        transport = getattr(self.search_transport, "__self__", None)
        if transport is None or not hasattr(transport, "search_all_payloads"):
            items: list[XianyuSearchItem] = []
            for page in range(1, max(max_pages, 1) + 1):
                page_items = self.search(keyword, page=page)
                if not page_items:
                    break
                items.extend(page_items)
            return items
        payloads = transport.search_all_payloads(
            keyword,
            max_pages=max_pages,
            require_chaozan_fish_shop=require_chaozan_fish_shop,
        )
        items: list[XianyuSearchItem] = []
        seen_item_ids: set[str] = set()
        for payload in payloads:
            for item in parse_xianyu_search_results(payload):
                if item.item_id in seen_item_ids:
                    continue
                seen_item_ids.add(item.item_id)
                items.append(item)
        return items

    def detail(self, item_url_or_id: str) -> XianyuDetailItem:
        if self.detail_transport is None:
            raise XianyuAdapterError("detail transport is not configured")
        payload = self.detail_transport(item_url_or_id)
        return parse_xianyu_detail(payload, item_url=item_url_or_id)

    def seller(self, user_id: str) -> XianyuSellerProfile:
        if self.seller_transport is None:
            raise XianyuAdapterError("seller transport is not configured")
        head_payload, ratings_payload = self.seller_transport(user_id)
        return parse_xianyu_seller_profile(head_payload, ratings_payload)
