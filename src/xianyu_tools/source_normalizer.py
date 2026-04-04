from __future__ import annotations

import re
from collections import Counter

from xianyu_tools.models import NormalizedSourceItem, RawSourceItem

_NOISE_PATTERN = re.compile(
    r"\s+|包邮|工厂直供|新款|爆款|低价货源|旗舰店|政府补贴\d+%|官方正品|工厂直营|源头厂家"
)
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]{2,}")
_MODEL_PATTERN = re.compile(r"[a-z]{1,6}\d{1,4}[a-z0-9-]*", re.IGNORECASE)
_STOPWORDS = {
    "官方",
    "正品",
    "旗舰",
    "补贴",
    "无线",
    "运动",
    "跑步",
    "同款",
    "耳机",
    "蓝牙",
    "低价",
    "货源",
}


def normalize_source_item(raw_item: RawSourceItem) -> NormalizedSourceItem:
    normalized_title = _NOISE_PATTERN.sub("", raw_item.title).strip().lower()
    tokens = extract_title_tokens(raw_item.title)
    brand_or_shop = raw_item.specs.get("品牌") or raw_item.shop_name or ""
    return NormalizedSourceItem(
        source_platform=raw_item.source_platform,
        source_item_id=raw_item.source_item_id,
        title=raw_item.title,
        normalized_title=normalized_title,
        price=raw_item.price,
        original_price=raw_item.original_price,
        item_url=raw_item.item_url,
        images=raw_item.images,
        specs=raw_item.specs,
        shop_name=raw_item.shop_name,
        sales=raw_item.sales,
        shipping_fee=raw_item.shipping_fee or 0.0,
        metadata={
            **raw_item.metadata,
            "normalized_tokens": tokens,
            "title_signature": build_title_signature(raw_item.title, brand_or_shop),
            "model_hint": extract_model_hint(raw_item.title),
            "brand_hint": normalize_brand_hint(brand_or_shop),
        },
    )


def extract_title_tokens(title: str) -> list[str]:
    cleaned = _NOISE_PATTERN.sub(" ", title).lower()
    tokens = []
    for token in _TOKEN_PATTERN.findall(cleaned):
        if token in _STOPWORDS:
            continue
        tokens.append(token)
    counts = Counter(tokens)
    return [token for token, _count in counts.most_common(8)]


def extract_model_hint(title: str) -> str:
    match = _MODEL_PATTERN.search(title.lower())
    return match.group(0) if match else ""


def normalize_brand_hint(value: str) -> str:
    if not value:
        return ""
    value = re.sub(r"(旗舰店|官方店|专卖店|企业店)$", "", value.strip().lower())
    return value


def build_title_signature(title: str, brand_hint: str = "") -> str:
    tokens = extract_title_tokens(title)
    model_hint = extract_model_hint(title)
    brand = normalize_brand_hint(brand_hint)
    key_parts = [part for part in [brand, model_hint, *tokens[:4]] if part]
    return "|".join(dict.fromkeys(key_parts))
