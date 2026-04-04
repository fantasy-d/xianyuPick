from pathlib import Path
import json

from xianyu_tools.xianyu_adapter import PlaywrightBrowserConfig, PlaywrightXianyuAdapter
from xianyu_tools.xianyu_adapter.browser_transport import (
    PlaywrightBrowserTransport,
    XianyuSearchTimeoutError,
    XianyuStateInvalidError,
)
from xianyu_tools.xianyu_adapter.parsers import (
    parse_xianyu_detail,
    parse_xianyu_search_results,
    parse_xianyu_seller_profile,
)


def fake_search_payload() -> dict:
    return {
        "data": {
            "resultList": [
                {
                    "data": {
                        "item": {
                            "main": {
                                "targetUrl": "fleamarket://item?id=123",
                                "clickParam": {
                                    "args": {"publishTime": "1719999999000", "wantNum": "88"},
                                },
                                "exContent": {
                                    "itemId": "123",
                                    "title": "iPhone 15 Pro Max 国行",
                                    "price": [{"text": "¥"}, {"text": "5999"}],
                                    "oriPrice": "6999",
                                    "userNickName": "数码玩家",
                                    "area": "上海",
                                    "picUrl": "https://example.com/item.jpg",
                                    "fishTags": {"r1": {"tagList": [{"data": {"content": "验货宝"}}]}},
                                },
                            }
                        }
                    }
                }
            ]
        }
    }


def fake_detail_payload() -> dict:
    return {
        "data": {
            "itemDO": {
                "itemId": "123",
                "title": "iPhone 15 Pro Max 国行",
                "price": "5999",
                "oriPrice": "6999",
                "desc": "99新，全套在",
                "area": "上海",
                "wantCnt": "88",
                "browseCnt": "1024",
                "imageInfos": [{"url": "https://example.com/item.jpg"}],
            },
            "sellerDO": {
                "sellerId": "u-001",
                "nick": "数码玩家",
                "userRegDay": "1200",
                "zhimaLevelInfo": {"levelName": "优秀"},
            },
        }
    }


def fake_seller_payload() -> tuple[dict, list[dict]]:
    head = {
        "data": {
            "module": {
                "base": {
                    "userId": "u-001",
                    "displayName": "数码玩家",
                    "avatar": {"avatar": "https://example.com/avatar.jpg"},
                    "introduction": "只卖自用数码",
                    "ylzTags": [
                        {"text": "极好卖家", "attributes": {"role": "seller"}},
                        {"text": "信用极好", "attributes": {"role": "buyer"}},
                    ],
                },
                "tabs": {
                    "item": {"number": "12"},
                    "rate": {"number": "36"},
                },
            }
        }
    }
    ratings = [
        {"cardData": {"rateTagList": [{"text": "作为卖家"}], "rate": 1}},
        {"cardData": {"rateTagList": [{"text": "作为卖家"}], "rate": 1}},
        {"cardData": {"rateTagList": [{"text": "作为买家"}], "rate": 1}},
    ]
    return head, ratings


def test_parse_xianyu_search_results() -> None:
    items = parse_xianyu_search_results(fake_search_payload())
    assert len(items) == 1
    assert items[0].item_id == "123"
    assert items[0].title == "iPhone 15 Pro Max 国行"
    assert items[0].price == 5999.0
    assert items[0].original_price == 6999.0
    assert items[0].seller_name == "数码玩家"
    assert items[0].area == "上海"
    assert items[0].image_url == "https://example.com/item.jpg"
    assert items[0].item_url == "https://www.goofish.com/item?id=123"
    assert "验货宝" in items[0].tags


def test_parse_xianyu_search_results_falls_back_to_visible_want_count() -> None:
    payload = fake_search_payload()
    main = payload["data"]["resultList"][0]["data"]["item"]["main"]
    main["clickParam"]["args"]["wantNum"] = "0"
    main["exContent"]["fishTags"]["r3"] = {
        "tagList": [
            {"data": {"content": "568人想要"}}
        ]
    }
    items = parse_xianyu_search_results(payload)
    assert items[0].want_count == 568


def test_parse_xianyu_detail() -> None:
    item = parse_xianyu_detail(fake_detail_payload(), item_url="https://www.goofish.com/item?id=123")
    assert item.seller_id == "u-001"
    assert item.browse_count == 1024
    assert item.images == ["https://example.com/item.jpg"]


def test_parse_xianyu_seller_profile() -> None:
    head, ratings = fake_seller_payload()
    profile = parse_xianyu_seller_profile(head, ratings)
    assert profile.user_id == "u-001"
    assert profile.seller_positive_rate == "100.00%"
    assert profile.buyer_positive_rate == "100.00%"


def test_playwright_xianyu_adapter_uses_injected_transports() -> None:
    head, ratings = fake_seller_payload()
    adapter = PlaywrightXianyuAdapter(
        search_transport=lambda keyword, page: fake_search_payload(),
        detail_transport=lambda item_id: fake_detail_payload(),
        seller_transport=lambda user_id: (head, ratings),
    )
    assert adapter.search("iphone")[0].title == "iPhone 15 Pro Max 国行"
    assert adapter.detail("123").seller_name == "数码玩家"
    assert adapter.seller("u-001").seller_credit_level == "极好卖家"


def test_playwright_xianyu_adapter_search_all_uses_transport_when_available() -> None:
    class FakeTransport:
        def search_payload(self, keyword: str, page: int) -> dict:
            return {"data": {"resultList": []}}

        def search_all_payloads(
            self,
            keyword: str,
            *,
            max_pages: int = 5,
            require_chaozan_fish_shop: bool = False,
        ) -> list[dict]:
            assert keyword == "iphone"
            assert max_pages == 3
            assert require_chaozan_fish_shop is True
            return [fake_search_payload()]

    transport = FakeTransport()
    adapter = PlaywrightXianyuAdapter(search_transport=transport.search_payload)
    items = adapter.search_all("iphone", max_pages=3, require_chaozan_fish_shop=True)
    assert len(items) == 1
    assert items[0].item_id == "123"


def test_playwright_xianyu_adapter_from_browser_wires_transports() -> None:
    class FakeTransport:
        def __init__(self, *, config=None, async_playwright_factory=None) -> None:
            self.config = config
            self.async_playwright_factory = async_playwright_factory

        def search_payload(self, keyword: str, page: int) -> dict:
            return fake_search_payload()

        def detail_payload(self, item_url_or_id: str) -> dict:
            return fake_detail_payload()

        def seller_payload(self, user_id: str) -> tuple[dict, list[dict]]:
            return fake_seller_payload()

    from xianyu_tools.xianyu_adapter import browser_transport as module

    original = module.PlaywrightBrowserTransport
    module.PlaywrightBrowserTransport = FakeTransport
    try:
        adapter = PlaywrightXianyuAdapter.from_browser(
            config=PlaywrightBrowserConfig(state_file="xianyu_state.json")
        )
    finally:
        module.PlaywrightBrowserTransport = original

    assert adapter.search("iphone")[0].item_id == "123"
    assert adapter.detail("123").seller_id == "u-001"
    assert adapter.seller("u-001").user_id == "u-001"


def test_browser_transport_accepts_extension_snapshot_shape(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "xianyu_state.json"
    snapshot_path.write_text(
        """
        {
          "cookies": [{"name": "cna", "value": "abc", "domain": ".goofish.com", "path": "/"}],
          "origins": [],
          "headers": {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)", "Accept-Language": "zh-CN,zh;q=0.9"},
          "env": {
            "navigator": {"userAgent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)", "language": "zh-CN", "maxTouchPoints": 5},
            "screen": {"width": 393, "height": 852, "devicePixelRatio": 3},
            "intl": {"timeZone": "Asia/Shanghai"}
          }
        }
        """.strip(),
        encoding="utf-8",
    )
    transport = PlaywrightBrowserTransport(config=PlaywrightBrowserConfig(state_file=str(snapshot_path)))
    payload = transport._load_json(snapshot_path)
    overrides = transport._build_context_overrides(payload)
    headers = transport._build_extra_headers(payload["headers"])
    storage_state = transport._extract_storage_state(payload)

    assert transport._is_playwright_storage_state(payload) is True
    assert overrides["is_mobile"] is True
    assert overrides["viewport"] == {"width": 393, "height": 852}
    assert headers["User-Agent"].startswith("Mozilla/5.0")
    assert storage_state["cookies"][0]["name"] == "cna"


def test_browser_transport_uses_desktop_defaults_without_state() -> None:
    transport = PlaywrightBrowserTransport(config=PlaywrightBrowserConfig())

    class FakeContext:
        async def set_extra_http_headers(self, headers):
            raise AssertionError("should not set headers without state")

    class FakeBrowser:
        async def new_context(self, **kwargs):
            return kwargs

    context = transport._run_sync(transport._new_context(FakeBrowser()))
    assert context["is_mobile"] is False
    assert context["has_touch"] is False
    assert context["no_viewport"] is True
    assert "viewport" not in context
    assert "Macintosh" in context["user_agent"]


def test_browser_transport_launch_args_include_desktop_anti_detection_flags() -> None:
    transport = PlaywrightBrowserTransport(
        config=PlaywrightBrowserConfig(launch_args=["--start-maximized"])
    )
    args = transport._launch_args()
    assert "--disable-blink-features=AutomationControlled" in args
    assert "--start-maximized" not in args


def test_browser_transport_headful_keeps_window_management_args() -> None:
    transport = PlaywrightBrowserTransport(
        config=PlaywrightBrowserConfig(headless=False, launch_args=["--start-maximized"])
    )
    args = transport._launch_args()
    assert "--start-maximized" in args


def test_search_response_matcher_excludes_shade_api() -> None:
    class FakeRequest:
        method = "POST"

    class FakeResponse:
        def __init__(self, url: str) -> None:
            self.url = url
            self.request = FakeRequest()

    transport = PlaywrightBrowserTransport()

    assert transport._is_search_response(
        FakeResponse("https://h5api.m.goofish.com/h5/mtop.taobao.idlemtopsearch.pc.search/1.0/")
    ) is True
    assert transport._is_search_response(
        FakeResponse("https://h5api.m.goofish.com/h5/mtop.taobao.idlemtopsearch.pc.search.shade/1.0/")
    ) is False


def test_browser_transport_retries_search_once() -> None:
    transport = PlaywrightBrowserTransport(
        config=PlaywrightBrowserConfig(search_max_retries=1, retry_delay_seconds=0)
    )
    calls = {"count": 0}

    async def fake_once(keyword: str, page: int) -> dict:
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("temporary search failure")
        return {"data": {"resultList": []}}

    transport._search_payload_once = fake_once  # type: ignore[method-assign]
    result = transport.search_payload("iphone", 1)
    assert result == {"data": {"resultList": []}}
    assert calls["count"] == 2


def test_browser_transport_rejects_state_without_cookies(tmp_path: Path) -> None:
    state_file = tmp_path / "xianyu_state.json"
    state_file.write_text(
        json.dumps({"cookies": [], "origins": [], "headers": {}, "env": {}}),
        encoding="utf-8",
    )
    transport = PlaywrightBrowserTransport(
        config=PlaywrightBrowserConfig(state_file=str(state_file))
    )
    try:
        transport._run_sync(transport._new_context(browser=None))  # type: ignore[arg-type]
    except XianyuStateInvalidError as exc:
        assert "no usable cookies" in str(exc)
    else:
        raise AssertionError("Expected XianyuStateInvalidError")


def test_browser_transport_wraps_search_timeout() -> None:
    transport = PlaywrightBrowserTransport(
        config=PlaywrightBrowserConfig(search_max_retries=0, retry_delay_seconds=0, search_timeout_ms=1234)
    )

    async def timeout_once(keyword: str, page: int) -> dict:
        raise asyncio.TimeoutError()

    import asyncio

    transport._search_payload_once = timeout_once  # type: ignore[method-assign]
    try:
        transport.search_payload("iphone", 1)
    except XianyuSearchTimeoutError as exc:
        assert "1234ms" in str(exc)
    else:
        raise AssertionError("Expected XianyuSearchTimeoutError")


def test_browser_transport_search_payload_once_reads_requested_page_from_search_all() -> None:
    transport = PlaywrightBrowserTransport()

    async def fake_all(keyword: str, *, max_pages: int = 5, require_chaozan_fish_shop: bool = False) -> list[dict]:
        return [
            {"data": {"resultList": [{"data": {"item": {"main": {"exContent": {"itemId": "1", "title": "A", "price": "1"}}}}}]}},
            {"data": {"resultList": [{"data": {"item": {"main": {"exContent": {"itemId": "2", "title": "B", "price": "2"}}}}}]}}
        ]

    transport._search_all_payloads = fake_all  # type: ignore[method-assign]
    result = transport.search_payload("iphone", 2)
    result_list = result["data"]["resultList"]
    assert result_list[0]["data"]["item"]["main"]["exContent"]["itemId"] == "2"
