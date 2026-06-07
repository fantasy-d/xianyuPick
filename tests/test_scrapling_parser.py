from __future__ import annotations

import re
import pytest
from xianyu_tools.source_adapter import Ali1688SourceAdapter

# 模拟以图搜的 HTML
MOCK_IMAGE_SEARCH_HTML = """
<html>
  <body>
    <div
      data-renderkey="1_1_normal_b2b-111"
      data-index="1"
      class="searchOfferWrapper--lmbrqOXR cardui-normal searchOfferItem--KlzJCOF8 searchOfferItemLink--dF0K0vIe"
      data-aplus-report="object_id@974690115262"
    >
      <div class="offerImgWrapper--kInuSwti">
        <div class="offerImgInner--Kj0eKAH2">
          <img src="https://cbu01.alicdn.com/test_img.webp" class="mainImg--GT1EYFGa">
        </div>
      </div>
      <div class="offerTitleRow--B50QDpVK">
        <div class="titleText--TB6mnS3m"><div>自愈测试：宇航员夕阳氛围灯</div></div>
      </div>
      <div class="offerPriceRow--IQUZJRP7 offer-price-row">
        <div class="colDesc--eV2rjEXh">
          <div class="priceItem--KqgIKB16">
            <div class="priceUnits--O_3yaifa">¥</div>
            <div class="textMain--s_l2eHVJ ">29</div>
            <div>.90</div>
          </div>
        </div>
        <div class="colDescAfter--P6Qn7AvC">
          <div class="offerDescItem--h75gHVC0"><div class="descText--ZgjQ0TWW">3000+件</div></div>
        </div>
      </div>
      <div class="offerShopRow--YiSKrZrM">
        <div class="colLeft--oaoNb9Cu">
          <div class="imageSearchShopInfo--nlEDo0Nj">
            <div class="shopName--vsCP_gNh">自愈测试源头工厂</div>
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

# 模拟普通搜索的 HTML
MOCK_NORMAL_SEARCH_HTML = """
<html>
  <body>
    <a
      class="ocms-fusion-1688-pc-pc-ad-common-offer-2024"
      target="_blank"
      href="https://dj.1688.com/ci_bb?a=123"
      data-tracker="offer"
      data-aplus-report="position@1^object_id@914998390655"
      data-key-value="offer_4064360219"
    >
      <div class="search-offer-item">
        <div class="offer-title-row">
          <div class="title-text text-row-1">
            <div>极光幻彩升降电脑桌</div>
          </div>
        </div>
        <div class="offer-price-row">
          <div class="col-desc-price">
            <div class="price-item">
              <div>¥</div>
              <div class="text-main">888</div>
              <div>.00</div>
            </div>
            <div class="col-desc_after">
              <div class="offer-desc-item"><div class="desc-text">已售100+件</div></div>
            </div>
          </div>
        </div>
        <div class="offer-shop-row">
          <div class="col-left">
            <div class="desc-text">智能家居直销店</div>
          </div>
        </div>
      </div>
    </a>
  </body>
</html>
""".strip()


def test_scrapling_parser_image_search_normal() -> None:
    adapter = Ali1688SourceAdapter()
    items = adapter.search_from_html(MOCK_IMAGE_SEARCH_HTML)
    assert len(items) == 1
    item = items[0]
    assert item.source_item_id == "974690115262"
    assert item.title == "自愈测试：宇航员夕阳氛围灯"
    assert item.price == 29.90
    assert item.sales == 3000
    assert item.shop_name == "自愈测试源头工厂"
    assert item.images == ["https://cbu01.alicdn.com/test_img.webp"]


def test_scrapling_parser_normal_search_normal() -> None:
    adapter = Ali1688SourceAdapter()
    items = adapter.search_from_html(MOCK_NORMAL_SEARCH_HTML)
    assert len(items) == 1
    item = items[0]
    assert item.source_item_id == "914998390655"
    assert item.title == "极光幻彩升降电脑桌"
    assert item.price == 888.00
    assert item.sales == 100
    assert item.shop_name == "智能家居直销店"


def test_scrapling_parser_self_healing_broken_classes() -> None:
    """
    破坏性测试：将 HTML 中的核心 CSS 类名完全打乱/修改，
    验证 Scrapling 基于 DOM 结构及内置自愈选择器的自适应检索能力。
    """
    adapter = Ali1688SourceAdapter()

    # 1. 破坏以图搜的 Class，甚至将 searchOfferWrapper 替换成无关词
    broken_image_html = MOCK_IMAGE_SEARCH_HTML
    # 替换所有的 Wrapper 类名
    broken_image_html = broken_image_html.replace("searchOfferWrapper--lmbrqOXR", "randomBox_123")
    broken_image_html = broken_image_html.replace("titleText--TB6mnS3m", "completelyBrokenTitleClass")
    broken_image_html = broken_image_html.replace("shopName--vsCP_gNh", "fooBarShopClass")

    items = adapter.search_from_html(broken_image_html)
    assert len(items) == 1
    item = items[0]
    
    # 核心字段应该依然可以通过 XPath 兜底或 Scrapling 自愈匹配解析成功！
    assert item.source_item_id == "974690115262"
    assert item.title == "自愈测试：宇航员夕阳氛围灯"
    assert item.price == 29.90
    assert item.shop_name == "自愈测试源头工厂"
    assert item.sales == 3000


def test_scrapling_parser_self_healing_normal_search_broken() -> None:
    """
    破坏普通搜索的 Class 名，验证兜底定位和自愈。
    """
    adapter = Ali1688SourceAdapter()

    broken_normal_html = MOCK_NORMAL_SEARCH_HTML
    # 破坏 a 标签和 shop-row 的类名
    broken_normal_html = broken_normal_html.replace("ocms-fusion-1688-pc-pc-ad-common-offer-2024", "brokenCommonOffer")
    broken_normal_html = broken_normal_html.replace("title-text", "brokenTitleText")
    broken_normal_html = broken_normal_html.replace("offer-shop-row", "brokenShopRow")

    items = adapter.search_from_html(broken_normal_html)
    assert len(items) == 1
    item = items[0]

    assert item.source_item_id == "914998390655"
    assert item.title == "极光幻彩升降电脑桌"
    assert item.price == 888.00
    assert item.shop_name == "智能家居直销店"
