from __future__ import annotations

from xianyu_tools.source_adapter import Ali1688SourceAdapter
from xianyu_tools.source_adapter.ali1688 import (
    Ali1688CaptchaError,
    Ali1688Config,
    Ali1688HTTPError,
    Ali1688NetworkError,
    Ali1688PayloadError,
)


SEARCH_HTML_WITH_STATE = """
<html>
  <head><title>1688 搜索结果</title></head>
  <body>
    <script>
      window.__INITIAL_STATE__ = {
        "offerList": [
          {
            "offerId": "123456789",
            "offerUrl": "https://detail.1688.com/offer/123456789.html",
            "title": "升降桌 工厂直销",
            "price": "88.50",
            "companyName": "杭州工厂店",
            "tradeQuantity": "999"
          },
          {
            "offerId": "987654321",
            "offerUrl": "https://detail.1688.com/offer/987654321.html",
            "title": "手摇升降桌",
            "finalPrice": "66.00",
            "shopName": "义乌源头仓"
          }
        ]
      };
    </script>
  </body>
</html>
""".strip()


SEARCH_HTML_FALLBACK = """
<html>
  <body>
    <a href="https://detail.1688.com/offer/111222333.html" title="折叠电脑桌">
      <span data-price="59.9"></span>
      <span class="company">佛山家具厂</span>
    </a>
  </body>
</html>
""".strip()


SEARCH_HTML_NEW_UI = """
<html>
  <body>
    <a
      class="ocms-fusion-1688-pc-pc-ad-common-offer-2024"
      target="_blank"
      href="https://dj.1688.com/ci_bb?a=27561"
      data-tracker="offer"
      data-aplus-report="position@1^object_id@914998390655"
      data-key-value="offer_4064360219"
      data-spm-anchor-id="a26352.13672862.offerlist.1"
    >
      <div class="search-offer-item">
        <div class="offer-title-row">
          <div class="title-text text-row-1">
            <div>书房智能<font color="red">升降</font>电脑桌家用办公书桌</div>
          </div>
        </div>
        <div class="offer-price-row">
          <div class="col-desc-price">
            <div class="price-item">
              <div>¥</div>
              <div class="text-main">327</div>
              <div>.5</div>
            </div>
            <div class="col-desc_after">
              <div class="offer-desc-item"><div class="desc-text">已售500+件</div></div>
            </div>
          </div>
        </div>
        <div class="offer-tag-row">
          <div class="col-desc-tag">
            <div class="offer-desc-item"><div class="desc-text">退货包运费</div></div>
            <div class="offer-desc-item"><div class="desc-text">先采后付</div></div>
          </div>
        </div>
        <div class="offer-shop-row">
          <div class="col-left">
            <a href="http://wenxingxiaoju1.1688.com" target="_blank" class="offer-desc-item">
              <div class="desc-text">霸州市文兴校具有限公司</div>
            </a>
          </div>
          <div class="col-right">
            <span class="J_WangWang ww-light ww-static"><span>旺旺在线</span></span>
          </div>
        </div>
      </div>
    </a>
  </body>
</html>
""".strip()


SEARCH_HTML_IMAGE_SEARCH = """
<html>
  <body>
    <div
      data-renderkey="1_1_normal_b2b-2218026418488d2103_974690115262"
      data-index="1"
      class="searchOfferWrapper--lmbrqOXR cardui-normal searchOfferItem--KlzJCOF8 searchOfferItemLink--dF0K0vIe"
      data-aplus-report="object_id@974690115262"
    >
      <div class="offerImgWrapper--kInuSwti">
        <div class="offerImgInner--Kj0eKAH2">
          <img src="https://cbu01.alicdn.com/test.webp" class="mainImg--GT1EYFGa">
        </div>
      </div>
      <div class="offerTitleRow--B50QDpVK">
        <div class="titleText--TB6mnS3m"><div>宇航员落日氛围灯卧室拍照夕阳灯余晖投影拍照补光</div></div>
      </div>
      <div class="offerPriceRow--IQUZJRP7 offer-price-row">
        <div class="colDesc--eV2rjEXh">
          <div class="priceItem--KqgIKB16">
            <div class="priceUnits--O_3yaifa">¥</div>
            <div class="textMain--s_l2eHVJ ">12</div>
            <div>.02</div>
          </div>
        </div>
        <div class="colDescAfter--P6Qn7AvC">
          <div class="offerDescItem--h75gHVC0"><div class="descText--ZgjQ0TWW">2.4万+件</div></div>
          <div class="offerDescItem--h75gHVC0"><div class="descText--ZgjQ0TWW">1件起批</div></div>
        </div>
      </div>
      <div class="offerShopRow--YiSKrZrM">
        <div class="colLeft--oaoNb9Cu">
          <div class="imageSearchShopInfo--nlEDo0Nj">
            <div class="shopName--vsCP_gNh">1688小店进货官方供应链</div>
          </div>
        </div>
        <div class="colRight--bPrNnU0K">
          <span class="J_WangWang" data-extra="{&quot;offerId&quot;:&quot;974690115262&quot;}"></span>
        </div>
      </div>
    </div>
  </body>
</html>
""".strip()


DETAIL_HTML_JSON_LD = """
<html>
  <head>
    <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "升降桌 120x60",
        "image": ["https://example.com/desk.jpg"],
        "brand": {"@type": "Brand", "name": "测试工厂"},
        "offers": {"@type": "Offer", "price": "128.0"}
      }
    </script>
  </head>
  <body></body>
</html>
""".strip()

SEARCH_HTML_CAPTCHA = """
<script>
window._config_ = {"action":"captcha","url":"https://s.1688.com/_____tmd_____/punish?x5secdata=xxx"};
</script><!--rgv587_flag:sm-->
""".strip()


def test_ali1688_build_search_url_uses_gbk_keyword_and_page() -> None:
    adapter = Ali1688SourceAdapter()
    url = adapter.build_search_url("升降桌", page=2)
    assert "beginPage=2" in url
    assert "keywords=" in url
    assert "%C9%FD%BD%B5%D7%C0" in url
    assert "filtOfferTags=1988226,98306,235906" in url
    assert "complexTags=1001" in url
    assert "tags=386434" in url


def test_ali1688_search_parses_state_payload() -> None:
    adapter = Ali1688SourceAdapter(transport=lambda url: SEARCH_HTML_WITH_STATE)
    items = adapter.search("升降桌", limit=5, page=1)
    assert len(items) == 2
    assert items[0].source_platform == "1688"
    assert items[0].source_item_id == "123456789"
    assert items[0].title == "升降桌 工厂直销"
    assert items[0].price == 88.5
    assert items[0].shop_name == "杭州工厂店"
    assert items[0].sales == 999
    assert items[0].metadata["provider"] == "ali1688"
    assert items[0].metadata["source_query"] == "升降桌"
    assert items[0].metadata["filter_flags"]["filtOfferTags"] == "1988226,98306,235906"


def test_ali1688_search_falls_back_to_card_html() -> None:
    adapter = Ali1688SourceAdapter(transport=lambda url: SEARCH_HTML_FALLBACK)
    items = adapter.search_from_result_url("https://s.1688.com/selloffer/offer_search.htm?keywords=x")
    assert len(items) == 1
    assert items[0].source_item_id == "111222333"
    assert items[0].title == "折叠电脑桌"
    assert items[0].price == 59.9
    assert items[0].shop_name == "佛山家具厂"


def test_ali1688_search_parses_new_ui_offer_card_html() -> None:
    adapter = Ali1688SourceAdapter(transport=lambda url: SEARCH_HTML_NEW_UI)
    items = adapter.search_from_html(SEARCH_HTML_NEW_UI)
    assert len(items) == 1
    assert items[0].source_item_id == "914998390655"
    assert items[0].item_url == "https://detail.1688.com/offer/914998390655.html"
    assert items[0].title == "书房智能 升降 电脑桌家用办公书桌"
    assert items[0].price == 327.5
    assert items[0].sales == 500
    assert items[0].shop_name == "霸州市文兴校具有限公司"
    assert items[0].metadata["search_html_variant"] == "offer_card_2024"


def test_ali1688_search_parses_image_search_offer_html() -> None:
    adapter = Ali1688SourceAdapter(transport=lambda url: SEARCH_HTML_IMAGE_SEARCH)
    items = adapter.search_from_html(SEARCH_HTML_IMAGE_SEARCH)
    assert len(items) == 1
    assert items[0].source_item_id == "974690115262"
    assert items[0].item_url == "https://detail.1688.com/offer/974690115262.html"
    assert items[0].title == "宇航员落日氛围灯卧室拍照夕阳灯余晖投影拍照补光"
    assert items[0].price == 12.02
    assert items[0].sales == 24000
    assert items[0].shop_name == "1688小店进货官方供应链"
    assert items[0].images == ["https://cbu01.alicdn.com/test.webp"]
    assert items[0].metadata["search_html_variant"] == "image_search_offer"


def test_ali1688_detail_parses_json_ld() -> None:
    adapter = Ali1688SourceAdapter(transport=lambda url: DETAIL_HTML_JSON_LD)
    item = adapter.detail("https://detail.1688.com/offer/123456789.html", source=10)
    assert item.source_platform == "1688"
    assert item.source_item_id == "123456789"
    assert item.title == "升降桌 120x60"
    assert item.price == 128.0
    assert item.shop_name == "测试工厂"
    assert item.images == ["https://example.com/desk.jpg"]


def test_ali1688_search_raises_payload_error_when_no_result_can_be_parsed() -> None:
    adapter = Ali1688SourceAdapter(transport=lambda url: "<html><body>empty</body></html>")
    try:
        adapter.search("升降桌")
    except Ali1688PayloadError as exc:
        assert "parseable result set" in str(exc)
    else:
        raise AssertionError("Expected Ali1688PayloadError")


def test_ali1688_search_raises_captcha_error_for_punish_page() -> None:
    adapter = Ali1688SourceAdapter(transport=lambda url: SEARCH_HTML_CAPTCHA)
    try:
        adapter.search("升降桌")
    except Ali1688CaptchaError as exc:
        assert "captcha" in str(exc)
    else:
        raise AssertionError("Expected Ali1688CaptchaError")


def test_ali1688_get_retries_network_error_then_succeeds(monkeypatch) -> None:
    adapter = Ali1688SourceAdapter(config=Ali1688Config(max_retries=2, retry_delay_seconds=0))

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return SEARCH_HTML_FALLBACK.encode("utf-8")

    attempts = {"count": 0}

    def flaky_urlopen(request, timeout):
        attempts["count"] += 1
        if attempts["count"] < 3:
            from urllib.error import URLError

            raise URLError("temporary failure")
        return FakeResponse()

    monkeypatch.setattr("xianyu_tools.source_adapter.ali1688.urlopen", flaky_urlopen)
    html = adapter._get("https://example.com")
    assert "折叠电脑桌" in html
    assert attempts["count"] == 3


def test_ali1688_get_raises_http_error_without_retry_on_4xx(monkeypatch) -> None:
    adapter = Ali1688SourceAdapter(config=Ali1688Config(max_retries=2, retry_delay_seconds=0))

    def bad_request(request, timeout):
        from urllib.error import HTTPError

        raise HTTPError(request.full_url, 403, "forbidden", hdrs=None, fp=None)

    monkeypatch.setattr("xianyu_tools.source_adapter.ali1688.urlopen", bad_request)
    try:
        adapter._get("https://example.com")
    except Ali1688HTTPError as exc:
        assert "HTTP 403" in str(exc)
    else:
        raise AssertionError("Expected Ali1688HTTPError")


def test_ali1688_get_raises_network_error_after_retry_exhausted(monkeypatch) -> None:
    adapter = Ali1688SourceAdapter(config=Ali1688Config(max_retries=1, retry_delay_seconds=0))

    def always_fail(request, timeout):
        from urllib.error import URLError

        raise URLError("offline")

    monkeypatch.setattr("xianyu_tools.source_adapter.ali1688.urlopen", always_fail)
    try:
        adapter._get("https://example.com")
    except Ali1688NetworkError as exc:
        assert "offline" in str(exc)
    else:
        raise AssertionError("Expected Ali1688NetworkError")


def test_ali1688_detail_sku_extraction_cleans_span_and_matches_images() -> None:
    mock_html = """
    <html>
      <body>
        <script>
          window.__INIT_DATA__ = {
            "globalData": {
              "skuProps": [
                {
                  "prop": "颜色",
                  "value": [
                    {
                      "name": "红色<span style=\\"line-height: 1;\\">参数</span>",
                      "imageUrl": "https://cbu01.alicdn.com/sku_red.jpg"
                    },
                    {
                      "name": "蓝色",
                      "imageUrl": "https://cbu01.alicdn.com/sku_blue.jpg"
                    }
                  ]
                }
              ],
              "skuInfoMap": {
                "颜色:红色<span style=\\"line-height: 1;\\">参数</span>": {
                  "price": "19.9",
                  "canBookCount": 99,
                  "specId": "red123"
                },
                "颜色:蓝色": {
                  "price": "20.9",
                  "canBookCount": 50,
                  "specId": "blue123"
                }
              }
            }
          };
        </script>
      </body>
    </html>
    """.strip()

    res = Ali1688SourceAdapter.extract_detail_sku_and_images(mock_html)
    sku_details = res.get("sku_details", [])
    assert len(sku_details) == 2

    # 验证红色规格
    red_sku = next(s for s in sku_details if "红色" in s["attributes"])
    assert red_sku["attributes"] == "颜色:红色"
    assert red_sku["price"] == "19.9"
    assert red_sku["stock"] == 99
    assert red_sku["image"] == "https://cbu01.alicdn.com/sku_red.jpg"

    # 验证蓝色规格
    blue_sku = next(s for s in sku_details if "蓝色" in s["attributes"])
    assert blue_sku["attributes"] == "颜色:蓝色"
    assert blue_sku["price"] == "20.9"
    assert blue_sku["stock"] == 50
    assert blue_sku["image"] == "https://cbu01.alicdn.com/sku_blue.jpg"

