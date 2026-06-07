from __future__ import annotations

import json
import re
import time
from scrapling import Selector
from dataclasses import dataclass
from html import unescape
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from xianyu_tools.models import RawSourceItem

ALI1688_SEARCH_URL = "https://s.1688.com/selloffer/offer_search.htm"
ALI1688_FIXED_QUERY_PARAMS = {
    "filtOfferTags": "1988226,98306,235906",
    "complexTags": "1001",
    "tags": "386434",
}
ALI1688_DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
    ),
}

HTMLTransport = Callable[[str], str]


class Ali1688Error(RuntimeError):
    pass


class Ali1688HTTPError(Ali1688Error):
    pass


class Ali1688NetworkError(Ali1688Error):
    pass


class Ali1688PayloadError(Ali1688Error):
    pass


class Ali1688CaptchaError(Ali1688Error):
    pass


@dataclass(slots=True)
class Ali1688Config:
    timeout: float = 20.0
    max_retries: int = 2
    retry_delay_seconds: float = 1.0
    default_begin_page: int = 1


class Ali1688SourceAdapter:
    def __init__(
        self,
        *,
        config: Ali1688Config | None = None,
        transport: HTMLTransport | None = None,
    ) -> None:
        self.config = config or Ali1688Config()
        self.transport = transport or self._get

    def build_search_url(self, keyword: str, *, page: int = 1) -> str:
        encoded_keyword = quote(keyword, safe="", encoding="gbk", errors="ignore")
        return (
            f"{ALI1688_SEARCH_URL}?keywords={encoded_keyword}"
            f"&beginPage={max(page, self.config.default_begin_page)}"
            f"&filtOfferTags={ALI1688_FIXED_QUERY_PARAMS['filtOfferTags']}"
            f"&complexTags={ALI1688_FIXED_QUERY_PARAMS['complexTags']}"
            f"&tags={ALI1688_FIXED_QUERY_PARAMS['tags']}"
        )

    def search(
        self,
        keyword: str,
        *,
        limit: int = 20,
        source: int = 10,
        page: int = 1,
    ) -> list[RawSourceItem]:
        url = self.build_search_url(keyword, page=page)
        items = self.search_from_result_url(url, limit=limit)
        for item in items:
            item.metadata.setdefault("source_type", source)
            item.metadata.setdefault("source_query", keyword)
            item.metadata.setdefault("search_url", url)
            item.metadata.setdefault("filter_flags", dict(ALI1688_FIXED_QUERY_PARAMS))
        return items

    def search_from_result_url(self, url: str, *, limit: int = 20) -> list[RawSourceItem]:
        html = self.transport(url)
        return self._parse_search_html(html)[:limit]

    def search_from_html(self, html: str, *, limit: int = 20) -> list[RawSourceItem]:
        return self._parse_search_html(html)[:limit]

    def detail(self, item_id_or_url: str, *, source: int = 10) -> RawSourceItem:
        if not item_id_or_url.startswith("http"):
            raise Ali1688PayloadError("Ali1688 detail currently requires a full item URL")
        html = self.transport(item_id_or_url)
        item = self._parse_detail_html(item_id_or_url, html)
        item.metadata.setdefault("source_type", source)
        return item

    def _parse_search_html(self, html: str) -> list[RawSourceItem]:
        if self._is_captcha_page(html):
            raise Ali1688CaptchaError("Ali1688 search page was blocked by captcha/punish middleware")
        state = self._extract_state_json(html)
        if state is not None:
            items = self._parse_search_state_items(state)
            if items:
                return items
        items = self._parse_search_card_items(html)
        if items:
            return items
        raise Ali1688PayloadError("Ali1688 search page did not contain a parseable result set")

    @staticmethod
    def _is_captcha_page(html: str) -> bool:
        markers = (
            "_____tmd_____",
            "action\":\"captcha\"",
            "rgv587_flag:sm",
            "/punish?x5secdata=",
            "访问被拒绝",
            "baxia-punish",
        )
        return any(marker in html for marker in markers)

    def _parse_detail_html(self, item_url: str, html: str) -> RawSourceItem:
        json_ld = self._extract_json_ld(html)
        if isinstance(json_ld, dict):
            title = str(json_ld.get("name") or "")
            offers = json_ld.get("offers") or {}
            price = _to_float(offers.get("price"))
            images = json_ld.get("image") or []
            if isinstance(images, str):
                images = [images]
            shop_name = (
                (json_ld.get("brand") or {}).get("name")
                if isinstance(json_ld.get("brand"), dict)
                else None
            )
            return RawSourceItem(
                source_platform="1688",
                source_item_id=self._extract_offer_id(item_url),
                title=title,
                price=price,
                item_url=item_url,
                images=[str(url) for url in images if url],
                shop_name=shop_name,
                shipping_fee=None,
                metadata={"provider": "ali1688", "detail_json_ld": json_ld},
            )

        title = _first_match(
            html,
            [
                r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
                r"<title>([^<]+)</title>",
            ],
        )
        price = _to_float(_first_match(html, [r'"price"\s*:\s*"([^"]+)"', r'data-price=["\']([^"\']+)["\']']))
        return RawSourceItem(
            source_platform="1688",
            source_item_id=self._extract_offer_id(item_url),
            title=unescape(title or ""),
            price=price,
            item_url=item_url,
            shipping_fee=None,
            metadata={"provider": "ali1688", "detail_html_fallback": True},
        )

    @staticmethod
    def extract_detail_sku_and_images(html: str) -> dict:
        """从 1688 详情页完整渲染 HTML 中提取 SKU 列表和图片列表。
        
        优先从页面内嵌的 JS 变量（window.__INIT_DATA__ 等）提取结构化数据；
        失败则通过 Scrapling CSS/XPath 从 DOM 提取。
        返回: {"sku_details": [...], "images": [...]}
        """
        result: dict = {"sku_details": [], "images": []}

        # ── 1. 从内嵌 JS 变量中提取 SKU ──
        js_patterns = [
            r"window\.__INIT_DATA__\s*=\s*(\{.*?\})\s*;",
            r"window\.__GLOBAL_DATA__\s*=\s*(\{.*?\})\s*;",
            r"window\.detailData\s*=\s*(\{.*?\})\s*;",
            r"\"skuInfoMap\"\s*:\s*(\{.*?\})\s*,",
            r"\"skuProps\"\s*:\s*(\[.*?\])\s*,",
        ]
        for pattern in js_patterns:
            m = re.search(pattern, html, re.DOTALL)
            if not m:
                continue
            try:
                obj = json.loads(m.group(1))
            except Exception:
                continue
            def clean_span(val_str: str) -> str:
                if not val_str: return ""
                val_str = re.sub(r'<span[^>]*?>.*?</span>', '', val_str, flags=re.IGNORECASE | re.DOTALL)
                val_str = re.sub(r'<[^>]+>', '', val_str)
                parts = [p.strip() for p in val_str.split(";") if p.strip()]
                return ";".join(parts)

            # 递归寻找 skuProps 并建立图片映射
            sku_props = _find_key_recursive_plain(obj, "skuProps")
            prop_images = {}
            if isinstance(sku_props, list):
                for prop in sku_props:
                    if isinstance(prop, dict) and isinstance(prop.get("value"), list):
                        for val in prop["value"]:
                            if isinstance(val, dict) and val.get("name") and val.get("imageUrl"):
                                cleaned_val_name = clean_span(str(val["name"]))
                                prop_images[cleaned_val_name] = val["imageUrl"]

            def match_image(attrs_str):
                if not attrs_str: return None
                cleaned_attrs = clean_span(attrs_str)
                for part in cleaned_attrs.split(";"):
                    val_name = part.split(":")[1].strip() if ":" in part else part.strip()
                    if val_name in prop_images:
                        return prop_images[val_name]
                return None

            # 递归寻找 skuInfoMap
            sku_map = _find_key_recursive_plain(obj, "skuInfoMap")
            if isinstance(sku_map, dict) and sku_map:
                for attr_name, info in sku_map.items():
                    if not isinstance(info, dict):
                        continue
                    result["sku_details"].append({
                        "attributes": clean_span(unescape(str(attr_name))).replace(">", " - "),
                        "price": info.get("discountPrice") or info.get("price"),
                        "stock": info.get("canBookCount"),
                        "spec_id": info.get("specId"),
                        "image": match_image(attr_name),
                        "source": "html_js_skuInfoMap",
                    })
                break
            # 从 offerDetail 里寻找 skuInfos / skuList
            offer_detail = _find_key_recursive_plain(obj, "offerDetail") or {}
            sku_list = (
                _find_key_recursive_plain(offer_detail, "skuInfos")
                or _find_key_recursive_plain(offer_detail, "skuList")
                or []
            )
            if isinstance(sku_list, list) and sku_list:
                for sku in sku_list:
                    if not isinstance(sku, dict):
                        continue
                    attrs = sku.get("attributes") or sku.get("specName") or sku.get("skuName") or ""
                    result["sku_details"].append({
                        "attributes": clean_span(unescape(str(attrs))).replace(">", " - "),
                        "price": sku.get("discountPrice") or sku.get("price"),
                        "stock": sku.get("canBookCount") or sku.get("stock"),
                        "spec_id": sku.get("specId") or sku.get("skuId"),
                        "image": match_image(attrs),
                        "source": "html_js_skuList",
                    })
                break

        # ── 2. 从内嵌 JSON-LD 提取图片 ──
        ld_matches = re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html, re.DOTALL | re.IGNORECASE,
        )
        for raw in ld_matches:
            try:
                data = json.loads(raw.strip())
            except Exception:
                continue
            imgs = data.get("image") or []
            if isinstance(imgs, str):
                imgs = [imgs]
            for img in imgs:
                if img and "alicdn.com" in str(img):
                    result["images"].append(str(img))
            if result["images"]:
                break

        # ── 3. 用 Scrapling 从 DOM 提取图片（兜底）──
        if not result["images"]:
            try:
                sel = Selector(html)
                img_selectors = [
                    ".module-od-picture-gallery img",
                    ".od-gallery-list-wapper img",
                    ".detail-gallery img",
                    "[class*='gallery'] img",
                    "[class*='mainImg'] img",
                ]
                for css in img_selectors:
                    for img_el in sel.css(css):
                        src = (
                            img_el.attrib.get("data-lazyload-src")
                            or img_el.attrib.get("src")
                            or ""
                        )
                        if src and "alicdn.com" in src:
                            result["images"].append(src)
                    if result["images"]:
                        break
            except Exception:
                pass

        # ── 4. 正则兜底图片（从内嵌 JS 中找 imageList）──
        if not result["images"]:
            m = re.search(r'"imageList"\s*:\s*(\[.*?\])', html, re.DOTALL)
            if m:
                try:
                    img_list = json.loads(m.group(1))
                    for item in img_list:
                        u = None
                        if isinstance(item, str):
                            u = item
                        elif isinstance(item, dict):
                            u = (
                                item.get("fullPathImageURI")
                                or item.get("originalImageUri")
                                or item.get("url")
                            )
                        if u and "alicdn.com" in str(u):
                            result["images"].append(str(u))
                except Exception:
                    pass

        result["images"] = list(dict.fromkeys(result["images"]))  # 去重保序
        return result

    def _parse_search_state_items(self, state: dict[str, Any]) -> list[RawSourceItem]:
        candidates = (
            state.get("offerList")
            or state.get("data", {}).get("offerList")
            or state.get("data", {}).get("list")
            or []
        )
        if not isinstance(candidates, list):
            return []
        items: list[RawSourceItem] = []
        for row in candidates:
            if not isinstance(row, dict):
                continue
            offer_id = str(row.get("offerId") or row.get("id") or row.get("itemId") or "")
            item_url = str(row.get("offerUrl") or row.get("url") or "")
            title = str(row.get("title") or row.get("subject") or "")
            price = _to_float(row.get("price") or row.get("finalPrice"))
            if not offer_id and item_url:
                offer_id = self._extract_offer_id(item_url)
            items.append(
                RawSourceItem(
                    source_platform="1688",
                    source_item_id=offer_id,
                    title=title,
                    price=price,
                    item_url=item_url,
                    shop_name=_to_str_or_none(row.get("companyName") or row.get("shopName")),
                    sales=_to_int_or_none(row.get("tradeQuantity") or row.get("sales")),
                    shipping_fee=None,
                    metadata={"provider": "ali1688", "search_payload": row},
                )
            )
        return [item for item in items if item.source_item_id or item.item_url]

    def _parse_search_card_items(self, html: str) -> list[RawSourceItem]:
        pattern = re.compile(
            r'<a(?P<attrs>[^>]+)href=["\'](?P<href>https?://detail\.1688\.com/offer/(?P<id>\d+)\.html[^"\']*)["\'](?P<tail>[^>]*)>'
            r'(?P<body>.*?)</a>',
            re.IGNORECASE | re.DOTALL,
        )
        items: list[RawSourceItem] = []
        for match in pattern.finditer(html):
            attrs = f"{match.group('attrs')} {match.group('tail')}"
            body = match.group("body")
            title = unescape(
                _first_match(attrs, [r'title=["\']([^"\']+)["\']'])
                or _first_match(body, [r'data-title=["\']([^"\']+)["\']'])
                or _strip_tags(body)
            )
            price = _to_float(
                _first_match(body, [r'data-price=["\']([^"\']+)["\']', r'¥\s*([0-9]+(?:\.[0-9]+)?)'])
            )
            shop_name = _to_str_or_none(
                _first_match(body, [r'data-company=["\']([^"\']+)["\']', r'class=["\']company["\'][^>]*>([^<]+)<'])
            )
            items.append(
                RawSourceItem(
                    source_platform="1688",
                    source_item_id=match.group("id"),
                    title=title.strip(),
                    price=price,
                    item_url=match.group("href"),
                    shop_name=shop_name,
                    shipping_fee=None,
                    metadata={"provider": "ali1688", "search_html_fallback": True},
                )
            )
        if items:
            return items

        items = self._parse_image_search_offer_blocks(html)
        if items:
            return items

        return self._parse_search_offer_card_blocks(html)
    def _parse_image_search_offer_blocks(self, html: str) -> list[RawSourceItem]:
        sel = Selector(html)
        cards = sel.css(".searchOfferWrapper, [class*='OfferWrapper'], [class*='offer-wrapper'], [class*='common-offer']")
        if not cards:
            cards = sel.xpath("//div[descendant::a[contains(@href, '/offer/')]]")
        if not cards:
            cards = sel.xpath("//div[descendant::img[contains(@src, 'alicdn.com') or contains(@data-lazyload-src, 'alicdn.com')] and descendant::*[contains(text(), '¥')] and not(descendant::div[descendant::img[contains(@src, 'alicdn.com') or contains(@data-lazyload-src, 'alicdn.com')] and descendant::*[contains(text(), '¥')]])]")
        
        items: list[RawSourceItem] = []
        for card in cards:
            offer_id = self._extract_offer_id_from_card(card)
            
            link = card.css("a[href*='/offer/']").first
            if not link:
                link = card.css("a").first
            href = link.attrib.get("href") if link else ""
                    
            title_el = card.css("[class*='titleText'], [class*='offerTitle'], [class*='title-text']").first
            title = title_el.get_all_text() if title_el else ""
            if not title:
                title = link.attrib.get("title") or link.get_all_text() if link else ""
            if not title:
                # 兜底：取 card 中除价格、销量、店名外字符长度最长的文本节点
                all_els = card.xpath(".//*[not(*)]")
                longest_text = ""
                for el in all_els:
                    txt = el.get_all_text().strip()
                    if txt and len(txt) > len(longest_text) and not any(k in txt for k in ["¥", "件", "售", "成交", "评价"]):
                        longest_text = txt
                title = longest_text
                
            # 1. 查找店铺容器
            shop_container = card.css("[class*='shop-row'], [class*='ShopInfo'], [class*='company'], [class*='shopName']").first
            shop_name = ""
            if shop_container:
                # 优先取容器内比较精准的 desc-text 或 a 标签
                shop_el = shop_container.css("[class*='desc-text'], [class*='shopName'], a").first
                if shop_el:
                    shop_name = shop_el.get_all_text()
                else:
                    shop_name = shop_container.get_all_text()
            
            # 2. 如果没找到店铺容器，再全局兜底
            if not shop_name:
                shop_el = card.xpath(".//*[contains(text(), '公司') or contains(text(), '厂') or contains(text(), '商行') or contains(text(), '经营部') or contains(text(), '旗舰店') or contains(text(), '店')]").first
                shop_name = shop_el.get_all_text() if shop_el else ""
                
            if shop_name:
                shop_name = re.sub(r'旺旺在线|旺旺|在线', '', shop_name).strip()
            
            sales_el = card.xpath(".//*[contains(text(), '件') or contains(text(), '售')]").first
            sales_text = sales_el.get_all_text() if sales_el else ""
            sales = _to_int_or_none(sales_text)
            
            price = _extract_offer_block_price(card.html_content)
            
            img = card.css("img[src*='alicdn.com']").first
            image_url = img.attrib.get("src") or img.attrib.get("data-lazyload-src") if img else ""
            
            item_url = f"https://detail.1688.com/offer/{offer_id}.html" if offer_id else href
            if not (offer_id or title):
                continue
                
            card_class = card.attrib.get("class") or ""
            variant = "image_search_offer"
            if "ocms-fusion" in card_class or "common-offer" in card_class:
                if "searchOfferWrapper" not in card_class and "OfferWrapper" not in card_class and "offer-wrapper" not in card_class:
                    variant = "offer_card_2024"

            items.append(
                RawSourceItem(
                    source_platform="1688",
                    source_item_id=offer_id,
                    title=_normalize_space(_strip_tags(title)),
                    price=price,
                    item_url=item_url,
                    images=[image_url] if image_url else [],
                    shop_name=_to_str_or_none(shop_name),
                    sales=sales,
                    shipping_fee=None,
                    metadata={
                        "provider": "ali1688",
                        "search_html_fallback": True,
                        "search_html_variant": variant,
                    },
                )
            )
        return items

    def _parse_search_offer_card_blocks(self, html: str) -> list[RawSourceItem]:
        sel = Selector(html)
        cards = sel.css("[class*='ocms-fusion-1688-pc-pc-ad-common-offer'], [class*='common-offer']")
        if not cards:
            cards = sel.xpath("//div[descendant::a[contains(@href, '/offer/')]]")
        if not cards:
            cards = sel.xpath("//a[descendant::*[contains(text(), '¥')]]")
            
        items: list[RawSourceItem] = []
        for card in cards:
            offer_id = self._extract_offer_id_from_card(card)
            
            link = card.css("a[href*='/offer/']").first
            if not link:
                link = card.css("a").first
            href = link.attrib.get("href") if link else ""
                
            title_el = card.css("[class*='title-text'], [class*='offer-title']").first
            title = title_el.get_all_text() if title_el else ""
            if not title and link:
                title = link.get_all_text()
            if not title:
                # 兜底：取 card 中除价格、销量、店名外字符长度最长的文本节点
                all_els = card.xpath(".//*[not(*)]")
                longest_text = ""
                for el in all_els:
                    txt = el.get_all_text().strip()
                    if txt and len(txt) > len(longest_text) and not any(k in txt for k in ["¥", "件", "售", "成交", "评价"]):
                        longest_text = txt
                title = longest_text
                
            # 1. 查找店铺容器
            shop_container = card.css("[class*='shop-row'], [class*='ShopInfo'], [class*='company'], [class*='shopName']").first
            shop_name = ""
            if shop_container:
                # 优先取容器内比较精准的 desc-text 或 a 标签
                shop_el = shop_container.css("[class*='desc-text'], [class*='shopName'], a").first
                if shop_el:
                    shop_name = shop_el.get_all_text()
                else:
                    shop_name = shop_container.get_all_text()
            
            # 2. 如果没找到店铺容器，再全局兜底
            if not shop_name:
                shop_el = card.xpath(".//*[contains(text(), '公司') or contains(text(), '厂') or contains(text(), '商行') or contains(text(), '经营部') or contains(text(), '旗舰店') or contains(text(), '店')]").first
                shop_name = shop_el.get_all_text() if shop_el else ""
                
            if shop_name:
                shop_name = re.sub(r'旺旺在线|旺旺|在线', '', shop_name).strip()
            
            sales_el = card.xpath(".//*[contains(text(), '件') or contains(text(), '售') or contains(text(), '成交')]").first
            sales_text = sales_el.get_all_text() if sales_el else ""
            sales = _to_int_or_none(sales_text)
            
            price = _extract_offer_block_price(card.html_content)
            item_url = f"https://detail.1688.com/offer/{offer_id}.html" if offer_id else href
            
            if not (offer_id or item_url or title):
                continue
                
            items.append(
                RawSourceItem(
                    source_platform="1688",
                    source_item_id=offer_id,
                    title=_normalize_space(_strip_tags(title)),
                    price=price,
                    item_url=item_url,
                    shop_name=_to_str_or_none(shop_name),
                    sales=sales,
                    shipping_fee=None,
                    metadata={
                        "provider": "ali1688",
                        "search_html_fallback": True,
                        "search_html_variant": "offer_card_2024",
                    },
                )
            )
        return items

    def _extract_offer_id_from_card(self, card) -> str:
        # 1. 尝试从 a 标签的 href 中提取
        for a_sel in [card.css("a[href*='/offer/']"), card.css("a")]:
            for a in a_sel:
                href = a.attrib.get("href") or ""
                if href:
                    oid = self._extract_offer_id(href)
                    if oid:
                        return oid
                    match = re.search(r'offerId=(\d+)', href)
                    if match:
                        return match.group(1)
        
        # 2. 从 html_content 中正则匹配
        patterns = [
            r"object_id@(\d+)",
            r"offer_(\d+)",
            r'"offerId"\s*:\s*"(\d+)"',
            r'"offerId"\s*:\s*(\d+)',
            r'offerId=(\d+)',
            r'/offer/(\d+)\.html',
        ]
        for pattern in patterns:
            match = re.search(pattern, card.html_content)
            if match:
                return match.group(1)
        return ""

    def _extract_state_json(self, html: str) -> dict[str, Any] | None:
        patterns = [
            r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;",
            r"window\.__GLOBAL_DATA__\s*=\s*(\{.*?\})\s*;",
            r"offerListData\s*=\s*(\{.*?\})\s*;",
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if not match:
                continue
            raw = match.group(1)
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                continue
        return None

    @staticmethod
    def _extract_json_ld(html: str) -> dict[str, Any] | None:
        matches = re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        for raw in matches:
            try:
                data = json.loads(raw.strip())
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                return data
        return None

    @staticmethod
    def _extract_offer_id(item_url: str) -> str:
        match = re.search(r"/offer/(\d+)\.html", item_url)
        return match.group(1) if match else ""

    def _get(self, url: str) -> str:
        last_error: Exception | None = None
        attempts = max(self.config.max_retries + 1, 1)
        request = Request(url, headers=ALI1688_DEFAULT_HEADERS)
        for attempt in range(1, attempts + 1):
            try:
                with urlopen(request, timeout=self.config.timeout) as response:
                    return response.read().decode("utf-8", errors="replace")
            except HTTPError as exc:
                last_error = exc
                if attempt >= attempts or exc.code < 500:
                    raise Ali1688HTTPError(f"Ali1688 request failed with HTTP {exc.code}") from exc
            except URLError as exc:
                last_error = exc
                if attempt >= attempts:
                    raise Ali1688NetworkError(f"Ali1688 request failed: {exc.reason}") from exc
            if self.config.retry_delay_seconds > 0:
                time.sleep(self.config.retry_delay_seconds)
        if isinstance(last_error, HTTPError):
            raise Ali1688HTTPError(f"Ali1688 request failed with HTTP {last_error.code}") from last_error
        if isinstance(last_error, URLError):
            raise Ali1688NetworkError(f"Ali1688 request failed: {last_error.reason}") from last_error
        raise Ali1688NetworkError("Ali1688 request failed for unknown reason")


def _first_match(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1)
    return None


def _strip_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value).strip()


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _extract_offer_block_price(value: str) -> float:
    integer_part = _first_match(
        value,
        [
            r'class=["\'][^"\']*(?:text-main|textMain)[^"\']*["\'][^>]*>(\d+)',
            r'class=["\'][^"\']*priceItem[^"\']*["\'][^>]*>.*?<div[^>]*>\s*¥\s*</div>\s*<div[^>]*>(\d+)</div>',
        ],
    )
    if integer_part:
        decimal_part = _first_match(
            value,
            [
                r'class=["\'][^"\']*(?:text-main|textMain)[^"\']*["\'][^>]*>\d+</div>\s*<div>\.(\d+)</div>',
                r'class=["\'][^"\']*priceItem[^"\']*["\'][^>]*>.*?<div[^>]*>\s*¥\s*</div>\s*<div[^>]*>\d+</div>\s*<div>\.(\d+)</div>',
            ],
        )
        price_text = integer_part if decimal_part is None else f"{integer_part}.{decimal_part}"
        return _to_float(price_text)
    return _to_float(
        _first_match(
            value,
            [
                r'class=["\'][^"\']*price-item[^"\']*["\'][^>]*>(.*?)</div>\s*</div>\s*<div class=["\'][^"\']*col-desc_after',
                r"¥\s*([0-9]+(?:\.[0-9]+)?)",
            ],
        )
    )


def _to_float(value: Any) -> float:
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    if not value:
        return 0.0
    match = re.search(r"\d+(?:\.\d+)?", str(value))
    if not match:
        return 0.0
    return round(float(match.group(0)), 2)


def _to_int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    raw = str(value)
    match = re.search(r"(\d+(?:\.\d+)?)\s*万", raw)
    if match:
        return int(float(match.group(1)) * 10000)
    match = re.search(r"\d+", raw)
    if not match:
        return None
    return int(match.group(0))


def _to_str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _find_key_recursive_plain(obj: Any, target_key: str) -> Any:
    """递归从嵌套 dict/list 中查找第一个匹配的 key 的值。"""
    if isinstance(obj, dict):
        if target_key in obj:
            return obj[target_key]
        for v in obj.values():
            res = _find_key_recursive_plain(v, target_key)
            if res is not None:
                return res
    elif isinstance(obj, list):
        for item in obj:
            res = _find_key_recursive_plain(item, target_key)
            if res is not None:
                return res
    return None
