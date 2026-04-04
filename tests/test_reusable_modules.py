from __future__ import annotations

from xianyu_tools.listing_decision import build_listing_candidates
from xianyu_tools.models import HotItem, RawSourceItem, XianyuSearchItem
from xianyu_tools.profit_analysis import build_profit_analysis
from xianyu_tools.reporting import build_xianyu_sourcing_summary, simplify_xianyu_item
from xianyu_tools.source_resolution import (
    build_source_query_from_hot_item,
    filter_ali1688_source_items_by_relevance,
    resolve_hot_items_to_ali1688_urls,
    resolve_hot_items_to_sources,
)
from xianyu_tools.xianyu_market import summarize_xianyu_market
from xianyu_tools.source_adapter.ali1688 import Ali1688CaptchaError, Ali1688PayloadError


class FakeSourceAdapter:
    def __init__(self, items: list[RawSourceItem] | None = None) -> None:
        self.items = items or []
        self.search_calls: list[str] = []

    def search(self, keyword: str, *, limit: int = 20, source: int = 0, page: int = 1) -> list[RawSourceItem]:
        self.search_calls.append(keyword)
        return self.items[:limit]

    def detail(self, item_id_or_url: str, *, source: int = 1) -> RawSourceItem:
        for item in self.items:
            if item.source_item_id == item_id_or_url:
                return item
        raise KeyError(item_id_or_url)


def test_build_source_query_from_hot_item_removes_noise() -> None:
    hot_item = HotItem(
        hot_item_id="hot-001",
        platform="1688",
        title="iPhone 15 Pro Max 爆款 官方 同款",
        price=4999.0,
    )
    query = build_source_query_from_hot_item(hot_item)
    assert "爆款" not in query
    assert "官方" not in query
    assert "iphone" in query.lower()


def test_build_source_query_from_hot_item_keeps_high_signal_phrase() -> None:
    hot_item = HotItem(
        hot_item_id="hot-010",
        platform="xianyu",
        title="低价处理原价3千多乐歌同款电动升降桌 深圳跨境公司出口货",
        price=298.0,
    )
    query = build_source_query_from_hot_item(hot_item)
    assert "升降桌" in query
    assert "低价" not in query
    assert "原价" not in query
    assert "出口" not in query


def test_build_source_query_from_hot_item_drops_size_and_measure_noise() -> None:
    hot_item = HotItem(
        hot_item_id="hot-011",
        platform="xianyu",
        title="e1环保级别 80x60 手摇升降桌 120cm 学习桌 88元",
        price=88.0,
    )
    query = build_source_query_from_hot_item(hot_item)
    assert "手摇升降桌" in query or "升降桌" in query
    assert "80x60" not in query.lower()
    assert "120cm" not in query.lower()
    assert "88" not in query


def test_resolve_hot_items_to_sources_preserves_resolution() -> None:
    adapter = FakeSourceAdapter(
        items=[
            RawSourceItem(
                source_platform="1688",
                source_item_id="src-001",
                title="iPhone 15 Pro Max",
                price=4200.0,
                item_url="https://example.com/src-001",
            )
        ]
    )
    hot_item = HotItem(
        hot_item_id="hot-001",
        platform="pinduoduo",
        title="iPhone 15 Pro Max",
        price=4999.0,
    )

    bundle = resolve_hot_items_to_sources([hot_item], adapter=adapter, limit_per_item=5, enrich_top_n=0)

    assert bundle["source_resolution"][0]["hot_item_id"] == "hot-001"
    assert bundle["source_resolution"][0]["resolved"] is True
    assert bundle["source_resolution"][0]["source_item_ids"] == ["src-001"]
    assert bundle["source_items"][0]["hot_item_id"] == "hot-001"
    assert adapter.search_calls


def test_resolve_hot_items_to_sources_records_no_source_case() -> None:
    hot_item = HotItem(
        hot_item_id="hot-002",
        platform="jd",
        title="蓝牙耳机",
        price=99.0,
    )
    bundle = resolve_hot_items_to_sources([hot_item], adapter=FakeSourceAdapter(), enrich_top_n=0)
    assert bundle["source_items"] == []
    assert bundle["source_resolution"][0]["resolved"] is False
    assert bundle["source_resolution"][0]["resolution_reason"] == "no_source_items_found"


def test_resolve_hot_items_to_ali1688_urls_records_missing_url() -> None:
    hot_item = HotItem(
        hot_item_id="hot-404",
        platform="xianyu",
        title="升降桌",
        price=99.0,
    )
    bundle = resolve_hot_items_to_ali1688_urls([hot_item], result_urls_by_hot_item_id={})
    assert bundle["source_items"] == []
    assert bundle["source_resolution"][0]["hot_item_id"] == "hot-404"
    assert bundle["source_resolution"][0]["resolved"] is False
    assert bundle["source_resolution"][0]["resolution_reason"] == "missing_result_url"


def test_resolve_hot_items_to_ali1688_urls_records_parse_error() -> None:
    class FailingAli1688Adapter:
        def search_from_result_url(self, url: str, *, limit: int = 20):
            raise Ali1688PayloadError("unparseable page")

    hot_item = HotItem(
        hot_item_id="hot-500",
        platform="xianyu",
        title="升降桌",
        price=99.0,
    )
    bundle = resolve_hot_items_to_ali1688_urls(
        [hot_item],
        result_urls_by_hot_item_id={"hot-500": "https://s.1688.com/selloffer/offer_search.htm?keywords=x"},
        adapter=FailingAli1688Adapter(),
    )
    assert bundle["source_items"] == []
    assert bundle["source_resolution"][0]["resolved"] is False
    assert bundle["source_resolution"][0]["resolution_reason"] == "ali1688_parse_error"


def test_resolve_hot_items_to_ali1688_urls_records_captcha() -> None:
    class FailingAli1688Adapter:
        def search_from_result_url(self, url: str, *, limit: int = 20):
            raise Ali1688CaptchaError("captcha blocked")

    hot_item = HotItem(
        hot_item_id="hot-501",
        platform="xianyu",
        title="升降桌",
        price=99.0,
    )
    bundle = resolve_hot_items_to_ali1688_urls(
        [hot_item],
        result_urls_by_hot_item_id={"hot-501": "https://s.1688.com/selloffer/offer_search.htm?keywords=x"},
        adapter=FailingAli1688Adapter(),
    )
    assert bundle["source_items"] == []
    assert bundle["source_resolution"][0]["resolved"] is False
    assert bundle["source_resolution"][0]["resolution_reason"] == "ali1688_captcha"


def test_filter_ali1688_source_items_by_relevance_keeps_related_titles() -> None:
    hot_item = HotItem(
        hot_item_id="hot-600",
        platform="xianyu",
        title="加密蒙古包蚊帐家用宿舍",
        price=99.0,
        metadata={"category_keyword": "蚊帐"},
    )
    raw_items = [
        RawSourceItem(
            source_platform="1688",
            source_item_id="src-keep",
            title="加密蒙古包蚊帐家用",
            price=20.0,
            item_url="https://detail.1688.com/offer/src-keep.html",
        ),
        RawSourceItem(
            source_platform="1688",
            source_item_id="src-drop",
            title="折叠电脑桌宿舍桌子",
            price=30.0,
            item_url="https://detail.1688.com/offer/src-drop.html",
        ),
    ]
    kept, rejected, metadata = filter_ali1688_source_items_by_relevance(hot_item, raw_items)
    assert [item.source_item_id for item in kept] == ["src-keep"]
    assert [item.source_item_id for item in rejected] == ["src-drop"]
    assert metadata["filtered_out_count"] == 1


def test_resolve_hot_items_to_ali1688_urls_marks_all_irrelevant_candidates() -> None:
    class FakeAli1688Adapter:
        def search_from_result_url(self, url: str, *, limit: int = 20):
            return [
                RawSourceItem(
                    source_platform="1688",
                    source_item_id="src-700",
                    title="折叠电脑桌宿舍桌子",
                    price=30.0,
                    item_url="https://detail.1688.com/offer/src-700.html",
                )
            ]

    hot_item = HotItem(
        hot_item_id="hot-700",
        platform="xianyu",
        title="加密蒙古包蚊帐家用宿舍",
        price=99.0,
        metadata={"category_keyword": "蚊帐"},
    )
    bundle = resolve_hot_items_to_ali1688_urls(
        [hot_item],
        result_urls_by_hot_item_id={"hot-700": "https://s.1688.com/selloffer/offer_search.htm?keywords=x"},
        adapter=FakeAli1688Adapter(),
    )
    assert len(bundle["source_items"]) == 1
    assert bundle["source_items"][0]["candidate_status"] == "filtered"
    assert bundle["source_resolution"][0]["resolved"] is False
    assert bundle["source_resolution"][0]["resolution_reason"] == "all_source_items_irrelevant"


def test_summarize_xianyu_market_builds_fixed_shape() -> None:
    hot_item = HotItem(
        hot_item_id="hot-003",
        platform="1688",
        title="iPhone 13",
        price=3000.0,
    )
    market = summarize_xianyu_market(
        hot_item,
        "iphone 13",
        [
            XianyuSearchItem(item_id="xy-1", title="iPhone 13", price=3200.0, seller_name="小王数码店"),
            XianyuSearchItem(item_id="xy-2", title="iPhone 13 128G", price=3100.0, seller_name="个人卖家"),
            XianyuSearchItem(item_id="xy-3", title="iPhone 13 国行", price=3300.0, seller_name="企业严选"),
        ],
        sample_size=2,
    )
    assert market.hot_item_id == "hot-003"
    assert market.listing_count == 3
    assert market.min_price == 3100.0
    assert market.median_price == 3200.0
    assert market.competition_level in {"medium", "high"}
    assert len(market.sample_items) == 2


def test_build_xianyu_sourcing_summary_uses_shared_reporting_shape() -> None:
    bundle = {
        "search_returned_count": 1,
        "search_items": [
            {
                "item_id": "xy-001",
                "title": "iPhone 15 Pro Max",
                "price": 5999.0,
                "item_url": "https://www.goofish.com/item?id=xy-001",
                "source_keyword": "iphone 15 pro max",
                "matched_candidates": [
                    {
                        "item": {
                            "source_platform": "1688",
                            "title": "iPhone 15 Pro Max",
                            "price": 4200.0,
                            "item_url": "https://example.com/src-001",
                        },
                        "match_score": 0.92,
                        "estimated_margin": 800.0,
                        "xianyu_resale_margin": 700.0,
                        "is_profitable_vs_xianyu": True,
                    }
                ],
            }
        ],
    }
    summary = build_xianyu_sourcing_summary(bundle)
    assert summary["search_returned_count"] == 1
    assert summary["search_items"][0]["source_keyword"] == "iphone 15 pro max"
    assert summary["search_items"][0]["top_candidates"][0]["platform"] == "1688"
    assert simplify_xianyu_item(bundle["search_items"][0])["item_id"] == "xy-001"


def test_build_profit_analysis_uses_hot_item_price_as_target() -> None:
    hot_item = HotItem(
        hot_item_id="xy-001",
        platform="xianyu",
        title="升降桌",
        price=99.0,
        want_count=120,
    )
    source_item = RawSourceItem(
        source_platform="1688",
        source_item_id="src-001",
        title="升降桌 工厂直发",
        price=60.0,
        shipping_fee=5.0,
        item_url="https://detail.1688.com/offer/src-001.html",
        sales=200,
        metadata={"hot_item_id": "xy-001"},
    )
    rows = build_profit_analysis([hot_item], [source_item])
    assert len(rows) == 1
    assert rows[0]["hot_item_id"] == "xy-001"
    assert rows[0]["source_item_id"] == "src-001"
    assert rows[0]["target_xianyu_price"] == 99.0
    assert rows[0]["source_cost"] == 65.0
    assert rows[0]["estimated_margin"] > 0
    assert "gross_margin_rate" in rows[0]
    assert "cost_profit_rate" in rows[0]


def test_build_listing_candidates_picks_best_source_per_hot_item() -> None:
    candidates = build_listing_candidates(
        hot_items=[
            {"hot_item_id": "xy-001", "title": "升降桌", "price": 99.0},
        ],
        source_items=[
            {"source_item_id": "src-001", "title": "升降桌A", "item_url": "https://example.com/a"},
            {"source_item_id": "src-002", "title": "升降桌B", "item_url": "https://example.com/b"},
        ],
        profit_analysis=[
            {
                "hot_item_id": "xy-001",
                "source_item_id": "src-001",
                "estimated_margin": 10.0,
                "gross_margin_rate": 0.2,
                "cost_profit_rate": 0.25,
                "risk_flags": [],
            },
            {
                "hot_item_id": "xy-001",
                "source_item_id": "src-002",
                "estimated_margin": 20.0,
                "gross_margin_rate": 0.25,
                "cost_profit_rate": 0.4,
                "risk_flags": [],
            },
        ],
    )
    assert len(candidates) == 1
    assert candidates[0]["source_item_id"] == "src-002"
    assert candidates[0]["is_recommended"] is True
