from __future__ import annotations

from typing import Any, Callable

from xianyu_tools.models import HotItem, XianyuSearchItem
from xianyu_tools.reporting import simplify_xianyu_item
from xianyu_tools.xianyu_adapter.base import XianyuAdapter

XianyuItemFilter = Callable[[XianyuSearchItem], bool]


def scan_xianyu_market(
    category_keyword: str,
    *,
    xianyu_adapter: XianyuAdapter,
    top_n: int = 10,
    max_pages: int = 5,
    require_chaozan_fish_shop: bool = True,
    item_filter: XianyuItemFilter | None = None,
) -> dict[str, Any]:
    all_items = fetch_all_xianyu_search_results(
        category_keyword,
        xianyu_adapter=xianyu_adapter,
        max_pages=max_pages,
        require_chaozan_fish_shop=require_chaozan_fish_shop,
    )
    filter_fn = item_filter or looks_like_chaozan_fish_shop_item
    filtered_items = (
        all_items if _adapter_supports_browser_filter(xianyu_adapter) else
        [item for item in all_items if filter_fn(item)] if require_chaozan_fish_shop else
        all_items
    )
    sorted_items = sort_xianyu_items_by_want_count(filtered_items)
    eligible_items = [item for item in sorted_items if item.image_url]
    hot_items = [build_hot_item_from_xianyu(item) for item in eligible_items[:top_n]]
    top_prices = [item.price for item in hot_items if item.price]
    return {
        "hot_items": [_serialize_hot_item(item) for item in hot_items],
        "xianyu_market": {
            "category_keyword": category_keyword,
            "result_count": len(filtered_items),
            "filtered_by": ["超赞鱼小铺"] if require_chaozan_fish_shop else [],
            "sorted_by": "want_count desc",
            "top_n": len(hot_items),
            "top10_price_stats": {
                "min": min(top_prices) if top_prices else 0.0,
                "max": max(top_prices) if top_prices else 0.0,
                "median": _median(top_prices),
            },
            "sample_items": [simplify_xianyu_item(item) for item in eligible_items[:top_n]],
        },
    }


def fetch_all_xianyu_search_results(
    category_keyword: str,
    *,
    xianyu_adapter: XianyuAdapter,
    max_pages: int = 5,
    require_chaozan_fish_shop: bool = False,
) -> list[XianyuSearchItem]:
    search_all = getattr(xianyu_adapter, "search_all", None)
    if callable(search_all):
        return search_all(
            category_keyword,
            max_pages=max_pages,
            require_chaozan_fish_shop=require_chaozan_fish_shop,
        )
    collected: list[XianyuSearchItem] = []
    seen_item_ids: set[str] = set()
    for page in range(1, max(max_pages, 1) + 1):
        page_items = xianyu_adapter.search(category_keyword, page=page)
        if not page_items:
            break
        new_count = 0
        for item in page_items:
            if item.item_id in seen_item_ids:
                continue
            seen_item_ids.add(item.item_id)
            collected.append(item)
            new_count += 1
        if new_count == 0:
            break
    return collected


def _adapter_supports_browser_filter(xianyu_adapter: XianyuAdapter) -> bool:
    return callable(getattr(xianyu_adapter, "search_all", None))


def sort_xianyu_items_by_want_count(items: list[XianyuSearchItem]) -> list[XianyuSearchItem]:
    return sorted(
        items,
        key=lambda item: (
            item.want_count or 0,
            item.price or 0.0,
            item.item_id,
        ),
        reverse=True,
    )


def build_hot_item_from_xianyu(item: XianyuSearchItem) -> HotItem:
    return HotItem(
        hot_item_id=item.item_id,
        platform="xianyu",
        title=item.title,
        price=item.price,
        want_count=item.want_count or 0,
        seller_name=item.seller_name,
        area=item.area,
        sales_volume=item.want_count,
        hot_score=float(item.want_count or 0),
        item_url=item.item_url,
        image_url=item.image_url,
        metadata={
            "publish_time": item.publish_time,
            "tags": list(item.tags),
        },
    )


def _serialize_hot_item(item: HotItem) -> dict[str, Any]:
    return {
        "hot_item_id": item.hot_item_id,
        "platform": item.platform,
        "title": item.title,
        "price": item.price,
        "want_count": item.want_count,
        "seller_name": item.seller_name,
        "area": item.area,
        "image_url": item.image_url,
        "item_url": item.item_url,
        "publish_time": (item.metadata or {}).get("publish_time"),
        "tags": (item.metadata or {}).get("tags") or [],
    }


def looks_like_chaozan_fish_shop_item(item: XianyuSearchItem) -> bool:
    payload = (item.metadata or {}).get("search_payload") or {}
    main = (((payload.get("data") or {}).get("item") or {}).get("main") or {})
    ex_content = main.get("exContent") or {}
    click_args = ((main.get("clickParam") or {}).get("args") or {})
    if ex_content.get("userFishShopLabel"):
        return True
    if str(click_args.get("userIsUseFishShopCard") or "").lower() == "true":
        return True
    return False


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[mid]
    return round((ordered[mid - 1] + ordered[mid]) / 2, 2)
