from __future__ import annotations

from xianyu_tools.models import XianyuSearchItem
from xianyu_tools.xianyu_market_scan import (
    build_hot_item_from_xianyu,
    fetch_all_xianyu_search_results,
    looks_like_chaozan_fish_shop_item,
    scan_xianyu_market,
    sort_xianyu_items_by_want_count,
)


class FakeXianyuAdapter:
    def __init__(self, pages: dict[int, list[XianyuSearchItem]]) -> None:
        self.pages = pages

    def search(self, keyword: str, *, page: int = 1) -> list[XianyuSearchItem]:
        return self.pages.get(page, [])


class FakeXianyuBrowserAdapter(FakeXianyuAdapter):
    def __init__(self, items: list[XianyuSearchItem]) -> None:
        super().__init__({})
        self.items = items
        self.calls: list[dict[str, object]] = []

    def search_all(
        self,
        keyword: str,
        *,
        max_pages: int = 5,
        require_chaozan_fish_shop: bool = False,
    ) -> list[XianyuSearchItem]:
        self.calls.append(
            {
                "keyword": keyword,
                "max_pages": max_pages,
                "require_chaozan_fish_shop": require_chaozan_fish_shop,
            }
        )
        return self.items


def test_fetch_all_xianyu_search_results_combines_pages_and_dedupes() -> None:
    adapter = FakeXianyuAdapter(
        {
            1: [
                XianyuSearchItem(item_id="1", title="A", price=10, want_count=5),
                XianyuSearchItem(item_id="2", title="B", price=20, want_count=4),
            ],
            2: [
                XianyuSearchItem(item_id="2", title="B", price=20, want_count=4),
                XianyuSearchItem(item_id="3", title="C", price=30, want_count=3),
            ],
        }
    )
    items = fetch_all_xianyu_search_results("耳机", xianyu_adapter=adapter, max_pages=3)
    assert [item.item_id for item in items] == ["1", "2", "3"]


def test_fetch_all_xianyu_search_results_prefers_search_all_when_available() -> None:
    adapter = FakeXianyuBrowserAdapter(
        [XianyuSearchItem(item_id="1", title="A", price=10, want_count=3)]
    )
    items = fetch_all_xianyu_search_results(
        "耳机",
        xianyu_adapter=adapter,
        max_pages=3,
        require_chaozan_fish_shop=True,
    )
    assert [item.item_id for item in items] == ["1"]
    assert adapter.calls == [
        {
            "keyword": "耳机",
            "max_pages": 3,
            "require_chaozan_fish_shop": True,
        }
    ]


def test_sort_xianyu_items_by_want_count_desc() -> None:
    items = [
        XianyuSearchItem(item_id="1", title="A", price=10, want_count=3),
        XianyuSearchItem(item_id="2", title="B", price=10, want_count=8),
        XianyuSearchItem(item_id="3", title="C", price=10, want_count=5),
    ]
    sorted_items = sort_xianyu_items_by_want_count(items)
    assert [item.item_id for item in sorted_items] == ["2", "3", "1"]


def test_build_hot_item_from_xianyu_maps_required_fields() -> None:
    item = XianyuSearchItem(
        item_id="xy-001",
        title="升降桌",
        price=299.0,
        want_count=66,
        seller_name="超值家居",
        area="浙江",
        item_url="https://www.goofish.com/item?id=xy-001",
        image_url="https://img.goofish.com/xy-001.jpg",
        tags=["包邮"],
        metadata={"search_payload": {"foo": "bar"}},
    )
    hot_item = build_hot_item_from_xianyu(item)
    assert hot_item.hot_item_id == "xy-001"
    assert hot_item.platform == "xianyu"
    assert hot_item.want_count == 66
    assert hot_item.sales_volume == 66
    assert hot_item.image_url == "https://img.goofish.com/xy-001.jpg"
    assert hot_item.metadata == {"publish_time": None, "tags": ["包邮"]}


def test_looks_like_chaozan_fish_shop_item_uses_payload_markers() -> None:
    item = XianyuSearchItem(
        item_id="xy-002",
        title="升降桌",
        price=299.0,
        metadata={
            "search_payload": {
                "data": {
                    "item": {
                        "main": {
                            "clickParam": {"args": {"userIsUseFishShopCard": "true"}},
                            "exContent": {},
                        }
                    }
                }
            }
        },
    )
    assert looks_like_chaozan_fish_shop_item(item) is True


def test_scan_xianyu_market_returns_top_items_and_market_summary() -> None:
    adapter = FakeXianyuAdapter(
        {
            1: [
                    XianyuSearchItem(
                        item_id="1",
                        title="A",
                        price=10,
                        want_count=1,
                        image_url="https://img/a.jpg",
                        metadata={"search_payload": {"data": {"item": {"main": {"exContent": {"userFishShopLabel": {"tagList": []}}}}}}},
                    ),
                    XianyuSearchItem(
                        item_id="2",
                        title="B",
                        price=20,
                        want_count=9,
                        image_url="https://img/b.jpg",
                        metadata={"search_payload": {"data": {"item": {"main": {"exContent": {"userFishShopLabel": {"tagList": []}}}}}}},
                    ),
                ],
                2: [
                    XianyuSearchItem(
                        item_id="3",
                        title="C",
                        price=30,
                        want_count=5,
                        image_url="https://img/c.jpg",
                        metadata={"search_payload": {"data": {"item": {"main": {"exContent": {"userFishShopLabel": {"tagList": []}}}}}}},
                    )
                ],
            }
        )
    bundle = scan_xianyu_market("升降桌", xianyu_adapter=adapter, top_n=2, max_pages=3)
    assert bundle["xianyu_market"]["category_keyword"] == "升降桌"
    assert bundle["xianyu_market"]["filtered_by"] == ["超赞鱼小铺"]
    assert bundle["xianyu_market"]["result_count"] == 3
    assert [item["hot_item_id"] for item in bundle["hot_items"]] == ["2", "3"]
    assert bundle["xianyu_market"]["top10_price_stats"] == {"min": 20, "max": 30, "median": 25.0}
