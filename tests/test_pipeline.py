import json
from urllib.error import HTTPError, URLError
from urllib.request import Request
from unittest.mock import patch

from xianyu_tools.models import PricingConfig
from xianyu_tools.pipeline import build_candidate_report
from xianyu_tools.source_adapter import MaishouAdapter
from xianyu_tools.source_adapter.maishou import MaishouConfig, MaishouHTTPError, MaishouNetworkError, MaishouPayloadError
from xianyu_tools.source_normalizer import build_title_signature, normalize_source_item


def fake_transport(request: Request) -> dict:
    if request.full_url.endswith("/searchList"):
        return {
            "data": [
                {
                    "goodsId": "1688-001",
                    "sourceType": "10",
                    "title": "蓝牙耳机 新款低价货源",
                    "shopName": "义乌样品仓",
                    "originalPrice": "32.9",
                    "actualPrice": "22.9",
                    "couponPrice": "3",
                    "commission": "1.8",
                    "monthSales": "582",
                    "picUrl": "https://example.com/1.jpg",
                },
                {
                    "goodsId": "1688-002",
                    "sourceType": "10",
                    "title": "蓝牙耳机 工厂直营",
                    "shopName": "义乌样品仓",
                    "originalPrice": "34.9",
                    "actualPrice": "23.9",
                    "couponPrice": "2",
                    "commission": "1.2",
                    "monthSales": "231",
                    "picUrl": "https://example.com/2.jpg",
                }
            ]
        }
    if request.full_url.endswith("/goods/detail"):
        if request.data and b"1688-002" in request.data:
            return {
                "data": {
                    "goodsId": "1688-002",
                    "title": "蓝牙耳机 工厂直营",
                    "actualPrice": "23.9",
                    "originalPrice": "34.9",
                    "couponPrice": "2",
                    "commission": "1.2",
                    "monthSales": "231",
                    "shopName": "义乌样品仓",
                    "images": ["https://example.com/2.jpg"],
                    "brandName": "测试品牌",
                    "postFee": "6.0",
                }
            }
        return {
            "data": {
                "goodsId": "1688-001",
                "title": "蓝牙耳机 新款低价货源",
                "actualPrice": "22.9",
                "originalPrice": "32.9",
                "couponPrice": "3",
                "commission": "1.8",
                "monthSales": "582",
                "shopName": "义乌样品仓",
                "images": ["https://example.com/1.jpg"],
                "brandName": "测试品牌",
                "postFee": "5.5",
            }
        }
    if request.full_url.endswith("/getTargetUrl"):
        if request.data and b"1688-002" in request.data:
            return {"data": {"appUrl": "https://example.com/buy/1688-002", "kl": "￥efgh￥"}}
        return {"data": {"appUrl": "https://example.com/buy/1688-001", "kl": "￥abcd￥"}}
    raise AssertionError(f"Unexpected request: {request.full_url}")


def test_maishou_adapter_search_returns_items() -> None:
    items = MaishouAdapter(transport=fake_transport).search("蓝牙耳机")
    assert len(items) >= 1
    assert items[0].source_platform
    assert items[0].source_item_id == "1688-001"
    assert items[0].item_url == ""
    assert items[0].shipping_fee == 0.0
    assert items[0].sales == 582
    assert items[0].metadata["provider"] == "maishou"
    assert items[0].metadata["source_type"] == 10


def test_normalizer_strips_noise_terms() -> None:
    item = MaishouAdapter(transport=fake_transport).search("蓝牙耳机")[0]
    normalized = normalize_source_item(item)
    assert "低价货源" not in normalized.normalized_title
    assert normalized.metadata["title_signature"]


def test_candidate_report_is_ranked() -> None:
    report = build_candidate_report("蓝牙耳机", adapter=MaishouAdapter(transport=fake_transport))
    assert len(report) >= 1
    assert report[0]["score"] >= report[-1]["score"]
    assert "estimated_margin_rate" in report[0]
    assert report[0]["xianyu_viable"] is True


def test_maishou_detail_returns_buy_url() -> None:
    item = MaishouAdapter(transport=fake_transport).detail("1688-001", source=10)
    assert item.source_item_id == "1688-001"
    assert item.item_url == "https://example.com/buy/1688-001"
    assert item.shipping_fee == 5.5
    assert item.metadata["copy_code"] == "￥abcd￥"
    assert "detail_payload" in item.metadata
    assert "target_payload" in item.metadata


def test_maishou_sales_parser_handles_suffix() -> None:
    adapter = MaishouAdapter(transport=lambda request: {"data": [{
        "goodsId": "tb-123",
        "sourceType": 1,
        "platformName": "天猫",
        "title": "测试商品",
        "actualPrice": "100",
        "monthSales": "9000+",
    }]})
    item = adapter.search("测试", source=0)[0]
    assert item.source_platform == "tmall"
    assert item.sales == 9000


def test_maishou_detail_falls_back_to_schema_url() -> None:
    adapter = MaishouAdapter(
        transport=lambda request: (
            {
                "data": {
                    "goodsId": "tb-123",
                    "title": "测试商品",
                    "actualPrice": "100",
                    "shopName": "测试店铺",
                    "images": ["https://example.com/test.jpg"],
                }
            }
            if request.full_url.endswith("/goods/detail")
            else {"data": {"schemaUrl": "taobao://item?id=tb-123", "kl": "￥test￥"}}
        )
    )
    item = adapter.detail("tb-123", source=1)
    assert item.item_url == "taobao://item?id=tb-123"
    assert item.metadata["copy_code"] == "￥test￥"


def test_maishou_search_returns_empty_list_when_data_empty() -> None:
    adapter = MaishouAdapter(transport=lambda request: {"data": []})
    assert adapter.search("空结果") == []


def test_maishou_search_raises_payload_error_for_non_list_data() -> None:
    adapter = MaishouAdapter(transport=lambda request: {"data": {}})
    try:
        adapter.search("异常")
    except MaishouPayloadError as exc:
        assert "Unexpected search payload" in str(exc)
    else:
        raise AssertionError("Expected MaishouPayloadError")


def test_maishou_detail_raises_payload_error_for_non_dict_detail() -> None:
    adapter = MaishouAdapter(
        transport=lambda request: {"data": []} if request.full_url.endswith("/goods/detail") else {"data": {}}
    )
    try:
        adapter.detail("1688-001", source=10)
    except MaishouPayloadError as exc:
        assert "Unexpected detail payload" in str(exc)
    else:
        raise AssertionError("Expected MaishouPayloadError")


def test_maishou_detail_raises_payload_error_for_non_dict_target() -> None:
    adapter = MaishouAdapter(
        transport=lambda request: (
            {
                "data": {
                    "goodsId": "1688-001",
                    "title": "测试商品",
                    "actualPrice": "100",
                }
            }
            if request.full_url.endswith("/goods/detail")
            else {"data": []}
        )
    )
    try:
        adapter.detail("1688-001", source=10)
    except MaishouPayloadError as exc:
        assert "Unexpected target payload" in str(exc)
    else:
        raise AssertionError("Expected MaishouPayloadError")


def test_candidate_report_enriches_detail_payload() -> None:
    report = build_candidate_report(
        "蓝牙耳机",
        limit=2,
        enrich_top_n=2,
        adapter=MaishouAdapter(transport=fake_transport),
        pricing=PricingConfig(markup_rate=0.5),
    )
    item = report[0]["item"]
    assert item["item_url"] == "https://example.com/buy/1688-001"
    assert item["shipping_fee"] == 5.5
    assert report[0]["estimated_margin"] > 0


def test_title_signature_collapses_similar_titles() -> None:
    first = build_title_signature("蓝牙耳机 新款低价货源", "义乌样品仓")
    second = build_title_signature("蓝牙耳机 工厂直营", "义乌样品仓")
    assert first == second


def test_candidate_report_dedupes_similar_candidates() -> None:
    report = build_candidate_report(
        "蓝牙耳机",
        limit=2,
        enrich_top_n=2,
        adapter=MaishouAdapter(transport=fake_transport),
    )
    assert len(report) == 1


def test_maishou_send_retries_transient_network_error() -> None:
    adapter = MaishouAdapter(config=MaishouConfig(max_retries=2, retry_delay_seconds=0))
    payload = json.dumps({"data": []}).encode("utf-8")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return payload

    attempts = {"count": 0}

    def flaky_urlopen(request: Request, timeout: float):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise URLError("temporary failure")
        return FakeResponse()

    with patch("xianyu_tools.source_adapter.maishou.urlopen", flaky_urlopen):
        data = adapter._send(Request("https://example.com"))

    assert data == {"data": []}
    assert attempts["count"] == 3


def test_maishou_send_raises_http_error_without_retry_on_4xx() -> None:
    adapter = MaishouAdapter(config=MaishouConfig(max_retries=2, retry_delay_seconds=0))

    def bad_request(request: Request, timeout: float):
        raise HTTPError(request.full_url, 400, "bad request", hdrs=None, fp=None)

    with patch("xianyu_tools.source_adapter.maishou.urlopen", bad_request):
        try:
            adapter._send(Request("https://example.com"))
        except MaishouHTTPError as exc:
            assert "HTTP 400" in str(exc)
        else:
            raise AssertionError("Expected MaishouHTTPError")


def test_maishou_send_retries_http_429_then_succeeds() -> None:
    adapter = MaishouAdapter(config=MaishouConfig(max_retries=2, retry_delay_seconds=0))
    payload = json.dumps({"data": []}).encode("utf-8")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return payload

    attempts = {"count": 0}

    def flaky_http(request: Request, timeout: float):
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise HTTPError(request.full_url, 429, "rate limited", hdrs=None, fp=None)
        return FakeResponse()

    with patch("xianyu_tools.source_adapter.maishou.urlopen", flaky_http):
        data = adapter._send(Request("https://example.com"))

    assert data == {"data": []}
    assert attempts["count"] == 2


def test_maishou_send_raises_payload_error_for_invalid_json() -> None:
    adapter = MaishouAdapter(config=MaishouConfig(max_retries=0, retry_delay_seconds=0))

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return b"{invalid"

    with patch("xianyu_tools.source_adapter.maishou.urlopen", lambda request, timeout: FakeResponse()):
        try:
            adapter._send(Request("https://example.com"))
        except MaishouPayloadError as exc:
            assert "invalid JSON" in str(exc)
        else:
            raise AssertionError("Expected MaishouPayloadError")


def test_maishou_send_raises_network_error_after_retry_exhausted() -> None:
    adapter = MaishouAdapter(config=MaishouConfig(max_retries=1, retry_delay_seconds=0))
    attempts = {"count": 0}

    def always_fail(request: Request, timeout: float):
        attempts["count"] += 1
        raise URLError("offline")

    with patch("xianyu_tools.source_adapter.maishou.urlopen", always_fail):
        try:
            adapter._send(Request("https://example.com"))
        except MaishouNetworkError as exc:
            assert "offline" in str(exc)
        else:
            raise AssertionError("Expected MaishouNetworkError")

    assert attempts["count"] == 2
