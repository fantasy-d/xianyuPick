from __future__ import annotations

from dataclasses import asdict
from statistics import median
from typing import Any

from xianyu_tools.models import HotItem, XianyuMarket, XianyuSearchItem
from xianyu_tools.reporting import simplify_xianyu_item
from xianyu_tools.xianyu_adapter.base import XianyuAdapter


def build_xianyu_market_records(
    hot_items: list[HotItem],
    *,
    xianyu_adapter: XianyuAdapter,
    page: int = 1,
    sample_size: int = 5,
) -> list[dict[str, Any]]:
    markets: list[dict[str, Any]] = []
    for hot_item in hot_items:
        keyword = build_xianyu_keyword_from_hot_item(hot_item)
        items = xianyu_adapter.search(keyword, page=page)
        markets.append(asdict(summarize_xianyu_market(hot_item, keyword, items, sample_size=sample_size)))
    return markets


def build_xianyu_keyword_from_hot_item(hot_item: HotItem) -> str:
    model_hint = hot_item.metadata.get("model_hint") if isinstance(hot_item.metadata, dict) else None
    if model_hint:
        return str(model_hint)
    return hot_item.title


def summarize_xianyu_market(
    hot_item: HotItem,
    keyword: str,
    items: list[XianyuSearchItem],
    *,
    sample_size: int = 5,
) -> XianyuMarket:
    prices = sorted(item.price for item in items if item.price is not None)
    min_price = prices[0] if prices else None
    median_price = float(median(prices)) if prices else None
    merchant_count = sum(1 for item in items if _is_merchant_like(item))
    merchant_ratio = round(merchant_count / len(items), 4) if items else 0.0
    return XianyuMarket(
        hot_item_id=hot_item.hot_item_id,
        keyword=keyword,
        listing_count=len(items),
        min_price=min_price,
        median_price=median_price,
        price_band={
            "min": min_price,
            "median": median_price,
            "max": prices[-1] if prices else None,
        },
        merchant_ratio=merchant_ratio,
        competition_level=_competition_level(len(items), merchant_ratio),
        sample_items=[simplify_xianyu_item(item) for item in items[:sample_size]],
        metadata={"hot_item_platform": hot_item.platform},
    )


def _is_merchant_like(item: XianyuSearchItem) -> bool:
    seller_name = (item.seller_name or "").lower()
    return any(marker in seller_name for marker in ("店", "企业", "严选", "优品", "数码"))


def _competition_level(listing_count: int, merchant_ratio: float) -> str:
    if listing_count >= 50 or merchant_ratio >= 0.5:
        return "high"
    if listing_count >= 15 or merchant_ratio >= 0.2:
        return "medium"
    if listing_count > 0:
        return "low"
    return "none"
