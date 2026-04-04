from __future__ import annotations

import json
import re
import time
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
        start_pattern = re.compile(
            r'<div(?P<attrs>[^>]*class=["\'][^"\']*searchOfferWrapper[^"\']*["\'][^>]*)>',
            re.IGNORECASE | re.DOTALL,
        )
        matches = list(start_pattern.finditer(html))
        if not matches:
            return []

        items: list[RawSourceItem] = []
        for index, match in enumerate(matches):
            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(html)
            chunk = html[start:end]
            attrs = match.group("attrs")
            offer_id = (
                _first_match(attrs, [r"object_id@(\d+)", r"_(\d{6,})"])
                or _first_match(chunk, [r'data-extra="\{&quot;offerId&quot;:&quot;(\d+)&quot;\}', r'"offerId"\s*:\s*"(\d+)"'])
                or ""
            )
            title = unescape(
                _first_match(
                    chunk,
                    [
                        r'class=["\'][^"\']*titleText[^"\']*["\'][^>]*>\s*<div>(.*?)</div>',
                        r'class=["\'][^"\']*offerTitleRow[^"\']*["\'][^>]*>.*?<div>(.*?)</div>',
                    ],
                )
                or ""
            )
            shop_name = _to_str_or_none(
                unescape(
                    _first_match(
                        chunk,
                        [
                            r'class=["\'][^"\']*shopName[^"\']*["\'][^>]*>([^<]+)</div>',
                            r'class=["\'][^"\']*imageSearchShopInfo[^"\']*["\'][^>]*>.*?>([^<]*(?:有限公司|厂|经营部|商行|旗舰店)[^<]*)</div>',
                        ],
                    )
                    or ""
                )
            )
            sales = _to_int_or_none(
                _first_match(
                    chunk,
                    [
                        r'>([0-9]+(?:\.[0-9]+)?万?\+?)件<',
                        r'已售\s*([0-9]+(?:\.[0-9]+)?万?\+?)件',
                    ],
                )
            )
            price = _extract_offer_block_price(chunk)
            image_url = _to_str_or_none(
                _first_match(
                    chunk,
                    [
                        r'<img[^>]+class=["\'][^"\']*mainImg[^"\']*["\'][^>]+src=["\']([^"\']+)["\']',
                        r'<img[^>]+src=["\']([^"\']+)["\'][^>]+class=["\'][^"\']*mainImg[^"\']*["\']',
                    ],
                )
            )
            item_url = f"https://detail.1688.com/offer/{offer_id}.html" if offer_id else ""
            if not (offer_id or title):
                continue
            items.append(
                RawSourceItem(
                    source_platform="1688",
                    source_item_id=offer_id,
                    title=_normalize_space(_strip_tags(title)),
                    price=price,
                    item_url=item_url,
                    images=[image_url] if image_url else [],
                    shop_name=shop_name,
                    sales=sales,
                    shipping_fee=None,
                    metadata={
                        "provider": "ali1688",
                        "search_html_fallback": True,
                        "search_html_variant": "image_search_offer",
                    },
                )
            )
        return items

    def _parse_search_offer_card_blocks(self, html: str) -> list[RawSourceItem]:
        start_pattern = re.compile(
            r'<a(?P<attrs>[^>]*class=["\'][^"\']*ocms-fusion-1688-pc-pc-ad-common-offer-2024[^"\']*["\'][^>]*)>',
            re.IGNORECASE | re.DOTALL,
        )
        matches = list(start_pattern.finditer(html))
        if not matches:
            return []

        items: list[RawSourceItem] = []
        for index, match in enumerate(matches):
            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(html)
            chunk = html[start:end]
            attrs = match.group("attrs")
            href = _first_match(attrs, [r'href=["\']([^"\']+)["\']']) or ""
            offer_id = (
                _first_match(attrs, [r"object_id@(\d+)", r"offer_(\d+)", r"offerId=(\d+)"])
                or _first_match(chunk, [r"offerId=(\d+)", r'"offerId"\s*:\s*"(\d+)"'])
                or ""
            )
            title = unescape(
                _first_match(
                    chunk,
                    [
                        r'class=["\'][^"\']*offer-title-row[^"\']*["\'][^>]*>.*?<div[^>]*>(.*?)</div>',
                        r'class=["\'][^"\']*title-text[^"\']*["\'][^>]*>.*?<div[^>]*>(.*?)</div>',
                    ],
                )
                or ""
            )
            shop_name = _to_str_or_none(
                unescape(
                    _first_match(
                        chunk,
                        [
                            r'class=["\'][^"\']*offer-shop-row[^"\']*["\'][^>]*>.*?<div class=["\'][^"\']*desc-text[^"\']*["\'][^>]*>([^<]+)</div>',
                            r'class=["\'][^"\']*offer-shop-row[^"\']*["\'][^>]*>.*?>([^<]*(?:有限公司|厂|经营部|商行|旗舰店)[^<]*)<',
                        ],
                    )
                    or ""
                )
            )
            sales = _to_int_or_none(
                _first_match(
                    chunk,
                    [
                        r"已售\s*([0-9]+(?:\.[0-9]+)?\+?)件",
                        r"成交\s*([0-9]+(?:\.[0-9]+)?\+?)件",
                    ],
                )
            )
            price = _extract_offer_block_price(chunk)
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
                    shop_name=shop_name,
                    sales=sales,
                    shipping_fee=None,
                    metadata={
                        "provider": "ali1688",
                        "search_html_fallback": True,
                        "search_html_variant": "offer_card_2024",
                        "raw_href": href,
                    },
                )
            )
        return items

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
