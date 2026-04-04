from urllib.request import Request

from xianyu_tools.models import PricingConfig
from xianyu_tools.source_adapter import MaishouAdapter
from xianyu_tools.xianyu_adapter import PlaywrightXianyuAdapter
from xianyu_tools.xianyu_sourcing import (
    build_source_keyword_from_xianyu,
    build_xianyu_sourcing_bundle,
    build_xianyu_sourcing_report,
)


def fake_maishou_transport(request: Request) -> dict:
    if request.full_url.endswith("/searchList"):
        return {
            "data": [
                {
                    "goodsId": "1688-001",
                    "sourceType": "10",
                    "title": "iPhone 15 Pro Max 国行 全新",
                    "shopName": "深圳数码仓",
                    "originalPrice": "6699",
                    "actualPrice": "5599",
                    "couponPrice": "100",
                    "commission": "5",
                    "monthSales": "28",
                    "picUrl": "https://example.com/iphone.jpg",
                }
            ]
        }
    if request.full_url.endswith("/goods/detail"):
        return {
            "data": {
                "goodsId": "1688-001",
                "title": "iPhone 15 Pro Max 国行 全新",
                "actualPrice": "5599",
                "originalPrice": "6699",
                "couponPrice": "100",
                "commission": "5",
                "monthSales": "28",
                "shopName": "深圳数码仓",
                "images": ["https://example.com/iphone.jpg"],
                "brandName": "Apple",
                "postFee": "12",
            }
        }
    if request.full_url.endswith("/getTargetUrl"):
        return {"data": {"appUrl": "https://example.com/buy/1688-001", "kl": "￥iphone￥"}}
    raise AssertionError(f"Unexpected request: {request.full_url}")


def fake_xianyu_adapter() -> PlaywrightXianyuAdapter:
    return PlaywrightXianyuAdapter(
        search_transport=lambda keyword, page: {
            "data": {
                "resultList": [
                    {
                        "data": {
                            "item": {
                                "main": {
                                    "targetUrl": "fleamarket://item?id=xy-001",
                                    "clickParam": {"args": {"publishTime": "1719999999000", "wantNum": "13"}},
                                    "exContent": {
                                        "itemId": "xy-001",
                                        "title": "iPhone 15 Pro Max 国行 99新",
                                        "price": [{"text": "¥"}, {"text": "6299"}],
                                        "oriPrice": "6999",
                                        "userNickName": "上海数码",
                                        "area": "上海",
                                        "picUrl": "https://example.com/xy.jpg",
                                    },
                                }
                            }
                        }
                    }
                ]
            }
        }
    )


def test_build_xianyu_sourcing_report_returns_ranked_matches() -> None:
    report = build_xianyu_sourcing_report(
        "iPhone 15 Pro Max",
        xianyu_adapter=fake_xianyu_adapter(),
        source_adapter=MaishouAdapter(transport=fake_maishou_transport),
        pricing=PricingConfig(markup_rate=0.08, packaging_cost=1.0),
    )
    assert len(report) == 1
    assert report[0]["source_keyword"].startswith("iphone15")
    matches = report[0]["matched_candidates"]
    assert len(matches) == 1
    assert matches[0]["match_score"] > 0.4
    assert matches[0]["is_profitable_vs_xianyu"] is True


def test_build_source_keyword_from_xianyu_prefers_model_and_core_terms() -> None:
    item = fake_xianyu_adapter().search("iphone")[0]
    keyword = build_source_keyword_from_xianyu(item)
    assert "iphone15promax" in keyword
    assert "99新" not in keyword


def test_build_xianyu_sourcing_bundle_preserves_search_returned_count() -> None:
    bundle = build_xianyu_sourcing_bundle(
        "iPhone 15 Pro Max",
        xianyu_adapter=fake_xianyu_adapter(),
        source_adapter=MaishouAdapter(transport=fake_maishou_transport),
        pricing=PricingConfig(markup_rate=0.08, packaging_cost=1.0),
    )
    assert bundle["search_returned_count"] == 1
    assert bundle["search_items"][0]["item_id"] == "xy-001"
    assert bundle["search_items"][0]["item_url"] == "https://www.goofish.com/item?id=xy-001"
    assert bundle["search_items"][0]["source_keyword"].startswith("iphone15")
    assert len(bundle["search_items"][0]["matched_candidates"]) == 1
