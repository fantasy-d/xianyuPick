from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

from xianyu_tools.models import XianyuDetailItem, XianyuSearchItem, XianyuSellerProfile


def parse_xianyu_search_results(payload: dict[str, Any]) -> list[XianyuSearchItem]:
    results = payload.get("data", {}).get("resultList", [])
    items: list[XianyuSearchItem] = []
    for result in results:
        main = (
            result.get("data", {})
            .get("item", {})
            .get("main", {})
        )
        ex_content = main.get("exContent", {})
        click_args = main.get("clickParam", {}).get("args", {})
        raw_link = main.get("targetUrl", "") or ""
        item_url = _normalize_xianyu_item_url(raw_link, ex_content.get("itemId"))

        items.append(
            XianyuSearchItem(
                item_id=str(ex_content.get("itemId") or ""),
                title=str(ex_content.get("title") or ""),
                price=_extract_price(ex_content.get("price")),
                original_price=_to_float_or_none(ex_content.get("oriPrice")),
                want_count=_extract_want_count(ex_content, click_args),
                seller_name=_to_str_or_none(ex_content.get("userNickName")),
                area=_to_str_or_none(ex_content.get("area")),
                publish_time=_format_publish_time(click_args.get("publishTime")),
                item_url=item_url,
                image_url=_to_str_or_none(ex_content.get("picUrl")),
                tags=_extract_tags(ex_content, click_args),
                metadata={"search_payload": result},
            )
        )
    return items


def parse_xianyu_detail(payload: dict[str, Any], *, item_url: str = "") -> XianyuDetailItem:
    data = payload.get("data", {})
    item_do = data.get("itemDO", {})
    seller_do = data.get("sellerDO", {})
    image_infos = item_do.get("imageInfos", []) or []
    images = [img.get("url") for img in image_infos if isinstance(img, dict) and img.get("url")]
    return XianyuDetailItem(
        item_id=str(item_do.get("itemId") or item_do.get("id") or ""),
        title=str(item_do.get("title") or ""),
        price=_to_float(item_do.get("price") or item_do.get("transPrice")),
        original_price=_to_float_or_none(item_do.get("oriPrice")),
        seller_id=_to_str_or_none(seller_do.get("sellerId")),
        seller_name=_to_str_or_none(seller_do.get("nick")),
        description=_to_str(item_do.get("desc") or item_do.get("description")),
        images=images,
        area=_to_str_or_none(item_do.get("area")),
        want_count=_to_int_or_none(item_do.get("wantCnt")),
        browse_count=_to_int_or_none(item_do.get("browseCnt")),
        seller_credit_level=_to_str_or_none(
            seller_do.get("zhimaLevelInfo", {}).get("levelName")
        ),
        user_registration_days=_to_int_or_none(seller_do.get("userRegDay")),
        item_url=item_url,
        metadata={"detail_payload": payload},
    )


def parse_xianyu_seller_profile(
    head_payload: dict[str, Any],
    ratings_payload: list[dict[str, Any]] | None = None,
) -> XianyuSellerProfile:
    data = head_payload.get("data", {})
    module = data.get("module", {})
    base = module.get("base", {})
    tabs = module.get("tabs", {})

    seller_credit = ""
    buyer_credit = ""
    for tag in base.get("ylzTags", []) or []:
        attributes = tag.get("attributes", {})
        role = attributes.get("role")
        if role == "seller":
            seller_credit = tag.get("text") or ""
        elif role == "buyer":
            buyer_credit = tag.get("text") or ""

    profile = XianyuSellerProfile(
        user_id=str(base.get("userId") or ""),
        seller_name=str(base.get("displayName") or ""),
        avatar_url=_to_str_or_none(base.get("avatar", {}).get("avatar")),
        bio=_to_str(base.get("introduction")),
        on_sale_count=_to_int_or_none(tabs.get("item", {}).get("number")),
        rating_count=_to_int_or_none(tabs.get("rate", {}).get("number")),
        seller_credit_level=seller_credit or None,
        buyer_credit_level=buyer_credit or None,
        metadata={"head_payload": head_payload},
    )
    if ratings_payload:
        seller_good, seller_total, buyer_good, buyer_total = _calculate_ratings(ratings_payload)
        profile.seller_positive_rate = _format_rate(seller_good, seller_total)
        profile.buyer_positive_rate = _format_rate(buyer_good, buyer_total)
        profile.metadata["ratings_payload"] = ratings_payload
    return profile


def _extract_price(value: Any) -> float:
    if isinstance(value, list):
        text = "".join(part.get("text", "") for part in value if isinstance(part, dict))
        return _to_float(text)
    return _to_float(value)


def _extract_tags(ex_content: dict[str, Any], click_args: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    if click_args.get("tag") == "freeship":
        tags.append("包邮")
    fish_tags = ex_content.get("fishTags", {}).get("r1", {}).get("tagList", [])
    for item in fish_tags:
        content = item.get("data", {}).get("content", "")
        if content:
            tags.append(str(content))
    return list(dict.fromkeys(tags))


def _extract_want_count(ex_content: dict[str, Any], click_args: dict[str, Any]) -> int | None:
    direct_value = _to_int_or_none(click_args.get("wantNum"))
    if direct_value:
        return direct_value

    fish_tags = ex_content.get("fishTags", {})
    rank_three_tags = fish_tags.get("r3", {}).get("tagList", [])
    for item in rank_three_tags:
        content = str(item.get("data", {}).get("content") or "")
        if "想要" in content:
            parsed = _to_int_or_none(content)
            if parsed is not None:
                return parsed

    return direct_value


def _format_publish_time(value: Any) -> str | None:
    try:
        timestamp_ms = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(timestamp_ms / 1000).strftime("%Y-%m-%d %H:%M")


def _calculate_ratings(ratings_payload: list[dict[str, Any]]) -> tuple[int, int, int, int]:
    seller_good = seller_total = buyer_good = buyer_total = 0
    for card in ratings_payload:
        data = card.get("cardData", {})
        rate_tag = ""
        rate_tag_list = data.get("rateTagList", [])
        if rate_tag_list:
            rate_tag = str(rate_tag_list[0].get("text") or "")
        rate = data.get("rate")
        if "卖家" in rate_tag:
            seller_total += 1
            if rate == 1:
                seller_good += 1
        elif "买家" in rate_tag:
            buyer_total += 1
            if rate == 1:
                buyer_good += 1
    return seller_good, seller_total, buyer_good, buyer_total


def _format_rate(positive: int, total: int) -> str | None:
    if total <= 0:
        return None
    return f"{(positive / total) * 100:.2f}%"


def _to_float(value: Any) -> float:
    if isinstance(value, str):
        cleaned = value.replace("当前价", "").replace("¥", "").replace("￥", "").strip()
        if "万" in cleaned:
            try:
                return round(float(cleaned.replace("万", "")) * 10000, 2)
            except ValueError:
                return 0.0
        match = re.search(r"\d+(?:\.\d+)?", cleaned)
        if match:
            return round(float(match.group(0)), 2)
        return 0.0
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return 0.0


def _to_float_or_none(value: Any) -> float | None:
    parsed = _to_float(value)
    return parsed if parsed else None


def _to_int_or_none(value: Any) -> int | None:
    if isinstance(value, str):
        digits = re.sub(r"[^\d]", "", value)
        if digits:
            return int(digits)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_str(value: Any) -> str:
    return "" if value is None else str(value)


def _to_str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_xianyu_item_url(raw_link: str, fallback_item_id: Any) -> str:
    item_id = _extract_item_id(raw_link) or _to_str_or_none(fallback_item_id) or ""
    if not item_id:
        return raw_link.replace("fleamarket://", "https://www.goofish.com/")
    return f"https://www.goofish.com/item?id={item_id}"


def _extract_item_id(raw_link: str) -> str | None:
    if not raw_link:
        return None
    normalized = raw_link.replace("fleamarket://", "https://www.goofish.com/")
    parsed = urlparse(normalized)
    item_ids = parse_qs(parsed.query).get("id")
    if item_ids and item_ids[0]:
        return item_ids[0]
    return None
