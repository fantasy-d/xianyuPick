from __future__ import annotations

from dataclasses import asdict
from typing import Any
import re

from xianyu_tools.models import HotItem, RawSourceItem, SourceResolution
from xianyu_tools.pipeline import enrich_source_items
from xianyu_tools.source_adapter import Ali1688SourceAdapter
from xianyu_tools.source_adapter.ali1688 import Ali1688CaptchaError, Ali1688Error
from xianyu_tools.source_adapter.base import SourceAdapter
from xianyu_tools.source_normalizer import extract_model_hint, extract_title_tokens

_HOT_ITEM_NOISE_WORDS = {
    "爆款",
    "热卖",
    "热销",
    "官方",
    "正品",
    "包邮",
    "同款",
    "旗舰",
    "处理",
    "原价",
    "成本价",
    "现货",
    "包邮",
    "全新",
    "清仓",
    "低价",
    "同款",
    "出口",
    "美国",
    "欧洲",
    "跨境",
    "公司",
    "办公",
    "电脑",
    "学习桌",
    "书桌",
    "桌面",
    "站立式",
    "工作台",
}

_PURE_NUMBER_PATTERN = re.compile(r"^\d+(?:\.\d+)?$")
_SIZE_TOKEN_PATTERN = re.compile(r"^\d{2,4}[x×]\d{2,4}$", re.IGNORECASE)
_MEASURE_TOKEN_PATTERN = re.compile(r"^\d+(cm|mm|米|m|kg|g|元)$", re.IGNORECASE)
_ALNUM_SHORT_PATTERN = re.compile(r"^[a-z]\d{1,3}$", re.IGNORECASE)
_HIGH_SIGNAL_CHINESE = (
    "升降桌",
    "电动升降桌",
    "手摇升降桌",
    "升降桌腿",
    "桌腿",
    "桌架",
    "桌板",
)
_TOKEN_NOISE_SUBSTRINGS = (
    "低价",
    "原价",
    "处理",
    "清仓",
    "出口",
    "跨境",
    "公司",
    "现货",
    "包邮",
    "成本价",
)


def build_source_query_from_hot_item(hot_item: HotItem) -> str:
    model_hint = extract_model_hint(hot_item.title)
    raw_tokens = extract_title_tokens(hot_item.title)
    tokens = [token for token in raw_tokens if _is_source_query_token(token)]
    query_parts: list[str] = []
    signal_phrase = _extract_high_signal_phrase(hot_item.title)
    if signal_phrase:
        query_parts.append(signal_phrase)
    if model_hint and _is_source_query_token(model_hint):
        query_parts.append(model_hint)
    query_parts.extend(tokens[:4])
    if not query_parts:
        return hot_item.title
    return " ".join(dict.fromkeys(query_parts))


def _extract_high_signal_phrase(title: str) -> str:
    for phrase in _HIGH_SIGNAL_CHINESE:
        if phrase in title:
            return phrase
    return ""


def _is_source_query_token(token: str) -> bool:
    if not token:
        return False
    if token in _HOT_ITEM_NOISE_WORDS:
        return False
    if _PURE_NUMBER_PATTERN.fullmatch(token):
        return False
    if _SIZE_TOKEN_PATTERN.fullmatch(token):
        return False
    if _MEASURE_TOKEN_PATTERN.fullmatch(token):
        return False
    if _ALNUM_SHORT_PATTERN.fullmatch(token):
        return False
    if len(token) <= 1:
        return False
    if any(part in token for part in _TOKEN_NOISE_SUBSTRINGS):
        return False
    return True


def resolve_hot_items_to_sources(
    hot_items: list[HotItem],
    *,
    adapter: SourceAdapter,
    limit_per_item: int = 10,
    enrich_top_n: int = 3,
    source: int = 0,
    page: int = 1,
) -> dict[str, Any]:
    source_items: list[dict[str, Any]] = []
    source_resolutions: list[dict[str, Any]] = []

    for hot_item in hot_items:
        source_query = build_source_query_from_hot_item(hot_item)
        raw_items = adapter.search(
            source_query,
            limit=limit_per_item,
            source=source,
            page=page,
        )
        if enrich_top_n > 0 and raw_items:
            raw_items = enrich_source_items(raw_items, adapter=adapter, top_n=enrich_top_n)
        resolution = _build_resolution(hot_item, source_query, raw_items)
        source_resolutions.append(asdict(resolution))
        for raw_item in raw_items:
            source_items.append(_serialize_source_item(raw_item, hot_item.hot_item_id, source_query))

    return {
        "source_items": source_items,
        "source_resolution": source_resolutions,
    }


def resolve_hot_items_to_ali1688_urls(
    hot_items: list[HotItem],
    *,
    result_urls_by_hot_item_id: dict[str, str],
    adapter: Ali1688SourceAdapter | None = None,
    limit_per_item: int = 10,
) -> dict[str, Any]:
    adapter = adapter or Ali1688SourceAdapter()
    source_items: list[dict[str, Any]] = []
    source_resolutions: list[dict[str, Any]] = []

    for hot_item in hot_items:
        source_query = build_source_query_from_hot_item(hot_item)
        result_url = result_urls_by_hot_item_id.get(hot_item.hot_item_id, "").strip()
        if not result_url:
            source_resolutions.append(
                asdict(
                    SourceResolution(
                        hot_item_id=hot_item.hot_item_id,
                        resolved=False,
                        source_item_ids=[],
                        resolution_reason="missing_result_url",
                        source_query=source_query,
                        metadata={"candidate_count": 0},
                    )
                )
            )
            continue

        try:
            raw_items = adapter.search_from_result_url(result_url, limit=limit_per_item)
        except Ali1688CaptchaError as exc:
            source_resolutions.append(
                asdict(
                    SourceResolution(
                        hot_item_id=hot_item.hot_item_id,
                        resolved=False,
                        source_item_ids=[],
                        resolution_reason="ali1688_captcha",
                        source_query=source_query,
                        metadata={
                            "candidate_count": 0,
                            "result_url": result_url,
                            "error": str(exc),
                        },
                    )
                )
            )
            continue
        except Ali1688Error as exc:
            source_resolutions.append(
                asdict(
                    SourceResolution(
                        hot_item_id=hot_item.hot_item_id,
                        resolved=False,
                        source_item_ids=[],
                        resolution_reason="ali1688_parse_error",
                        source_query=source_query,
                        metadata={
                            "candidate_count": 0,
                            "result_url": result_url,
                            "error": str(exc),
                        },
                    )
                )
            )
            continue
        filtered_items, rejected_items, filter_metadata = filter_ali1688_source_items_by_relevance(hot_item, raw_items)
        source_resolutions.append(
            asdict(_build_resolution(hot_item, source_query, raw_items, filtered_items, filter_metadata))
        )
        for raw_item in filtered_items:
            source_items.append(
                _serialize_source_item(
                    raw_item,
                    hot_item.hot_item_id,
                    source_query,
                    candidate_status="accepted",
                    filter_reason="",
                )
            )
        for raw_item in rejected_items:
            source_items.append(
                _serialize_source_item(
                    raw_item,
                    hot_item.hot_item_id,
                    source_query,
                    candidate_status="filtered",
                    filter_reason="title_irrelevant",
                )
            )

    return {
        "source_items": source_items,
        "source_resolution": source_resolutions,
    }


def resolve_hot_items_to_ali1688_html(
    hot_items: list[HotItem],
    *,
    html_by_hot_item_id: dict[str, str],
    metadata_by_hot_item_id: dict[str, dict[str, Any]] | None = None,
    adapter: Ali1688SourceAdapter | None = None,
    limit_per_item: int = 10,
) -> dict[str, Any]:
    adapter = adapter or Ali1688SourceAdapter()
    metadata_by_hot_item_id = metadata_by_hot_item_id or {}
    source_items: list[dict[str, Any]] = []
    source_resolutions: list[dict[str, Any]] = []

    for hot_item in hot_items:
        source_query = build_source_query_from_hot_item(hot_item)
        html = html_by_hot_item_id.get(hot_item.hot_item_id, "")
        extra_metadata = metadata_by_hot_item_id.get(hot_item.hot_item_id, {})
        if not html:
            source_resolutions.append(
                asdict(
                    SourceResolution(
                        hot_item_id=hot_item.hot_item_id,
                        resolved=False,
                        source_item_ids=[],
                        resolution_reason="missing_browser_html",
                        source_query=source_query,
                        metadata={"candidate_count": 0, **extra_metadata},
                    )
                )
            )
            continue

        try:
            raw_items = adapter.search_from_html(html, limit=limit_per_item)
        except Ali1688CaptchaError as exc:
            source_resolutions.append(
                asdict(
                    SourceResolution(
                        hot_item_id=hot_item.hot_item_id,
                        resolved=False,
                        source_item_ids=[],
                        resolution_reason="ali1688_captcha",
                        source_query=source_query,
                        metadata={"candidate_count": 0, "error": str(exc), **extra_metadata},
                    )
                )
            )
            continue
        except Ali1688Error as exc:
            source_resolutions.append(
                asdict(
                    SourceResolution(
                        hot_item_id=hot_item.hot_item_id,
                        resolved=False,
                        source_item_ids=[],
                        resolution_reason="ali1688_parse_error",
                        source_query=source_query,
                        metadata={"candidate_count": 0, "error": str(exc), **extra_metadata},
                    )
                )
            )
            continue

        filtered_items, rejected_items, filter_metadata = filter_ali1688_source_items_by_relevance(hot_item, raw_items)
        source_resolutions.append(
            asdict(_build_resolution(hot_item, source_query, raw_items, filtered_items, filter_metadata))
        )
        for raw_item in filtered_items:
            source_items.append(
                _serialize_source_item(
                    raw_item,
                    hot_item.hot_item_id,
                    source_query,
                    candidate_status="accepted",
                    filter_reason="",
                )
            )
        for raw_item in rejected_items:
            source_items.append(
                _serialize_source_item(
                    raw_item,
                    hot_item.hot_item_id,
                    source_query,
                    candidate_status="filtered",
                    filter_reason="title_irrelevant",
                )
            )

    return {
        "source_items": source_items,
        "source_resolution": source_resolutions,
    }


def _build_resolution(
    hot_item: HotItem,
    source_query: str,
    raw_items: list[RawSourceItem],
    filtered_items: list[RawSourceItem] | None = None,
    filter_metadata: dict[str, Any] | None = None,
) -> SourceResolution:
    filtered_items = raw_items if filtered_items is None else filtered_items
    filter_metadata = dict(filter_metadata or {})
    if filtered_items:
        return SourceResolution(
            hot_item_id=hot_item.hot_item_id,
            resolved=True,
            source_item_ids=[item.source_item_id for item in filtered_items],
            resolution_reason="matched_source_items",
            source_query=source_query,
            metadata={"candidate_count": len(filtered_items), **filter_metadata},
        )
    if raw_items:
        return SourceResolution(
            hot_item_id=hot_item.hot_item_id,
            resolved=False,
            source_item_ids=[],
            resolution_reason="all_source_items_irrelevant",
            source_query=source_query,
            metadata={
                "candidate_count": 0,
                "raw_candidate_count": len(raw_items),
                **filter_metadata,
            },
        )
    return SourceResolution(
        hot_item_id=hot_item.hot_item_id,
        resolved=False,
        source_item_ids=[],
        resolution_reason="no_source_items_found",
        source_query=source_query,
        metadata={"candidate_count": 0, **filter_metadata},
    )


def filter_ali1688_source_items_by_relevance(
    hot_item: HotItem,
    raw_items: list[RawSourceItem],
) -> tuple[list[RawSourceItem], list[RawSourceItem], dict[str, Any]]:
    required_terms = _build_hot_item_relevance_terms(hot_item)
    if not required_terms:
        return raw_items, [], {
            "required_terms": [],
            "filtered_out_count": 0,
            "raw_candidate_count": len(raw_items),
        }

    kept: list[RawSourceItem] = []
    rejected: list[RawSourceItem] = []
    dropped: list[str] = []
    for item in raw_items:
        if _source_item_matches_hot_item_terms(item, required_terms):
            kept.append(item)
        else:
            rejected.append(item)
            dropped.append(item.source_item_id or item.title)
    return kept, rejected, {
        "required_terms": required_terms,
        "filtered_out_count": len(raw_items) - len(kept),
        "raw_candidate_count": len(raw_items),
        "dropped_candidates": dropped[:10],
    }


def _build_hot_item_relevance_terms(hot_item: HotItem) -> list[str]:
    metadata = dict(hot_item.metadata or {})
    category_keyword = str(metadata.get("category_keyword") or "").strip().lower()
    terms: list[str] = []
    if category_keyword:
        terms.append(category_keyword)
        terms.extend(extract_title_tokens(category_keyword))
    high_signal_phrase = _extract_high_signal_phrase(hot_item.title)
    if high_signal_phrase:
        terms.append(high_signal_phrase.lower())
    model_hint = extract_model_hint(hot_item.title)
    if model_hint and _is_source_query_token(model_hint):
        terms.append(model_hint.lower())
    for token in extract_title_tokens(hot_item.title):
        lowered = token.lower()
        if _is_source_query_token(lowered):
            terms.append(lowered)
    deduped: list[str] = []
    for term in terms:
        if not term or term in deduped:
            continue
        deduped.append(term)
    if category_keyword:
        category_terms = [term for term in deduped if category_keyword in term or term in category_keyword]
        if category_terms:
            return category_terms
    return deduped[:6]


def _source_item_matches_hot_item_terms(item: RawSourceItem, required_terms: list[str]) -> bool:
    title = (item.title or "").lower()
    if not title:
        return False
    title_tokens = set(extract_title_tokens(title))
    for term in required_terms:
        if term in title:
            return True
        if term in title_tokens:
            return True
    return False


def _serialize_source_item(
    item: RawSourceItem,
    hot_item_id: str,
    source_query: str,
    *,
    candidate_status: str = "accepted",
    filter_reason: str = "",
) -> dict[str, Any]:
    image_url = item.images[0] if item.images else None
    return {
        "hot_item_id": hot_item_id,
        "source_item_id": item.source_item_id,
        "source_platform": item.source_platform,
        "title": item.title,
        "price": item.price,
        "item_url": item.item_url,
        "shop_name": item.shop_name,
        "sales": item.sales,
        "image_url": image_url,
        "shipping_fee": item.shipping_fee,
        "candidate_status": candidate_status,
        "filter_reason": filter_reason,
    }
