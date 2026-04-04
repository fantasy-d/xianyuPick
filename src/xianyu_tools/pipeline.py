from __future__ import annotations

from dataclasses import asdict

from xianyu_tools.candidate_ranker import rank_candidates
from xianyu_tools.models import PricingConfig, RawSourceItem
from xianyu_tools.source_adapter import MaishouAdapter
from xianyu_tools.source_adapter.base import SourceAdapter
from xianyu_tools.source_normalizer import normalize_source_item
from xianyu_tools.xianyu_filter import dedupe_candidates, filter_candidates_for_xianyu, summarize_candidate


def _source_to_code(platform: str) -> int:
    mapping = {
        "all": 0,
        "taobao": 1,
        "tmall": 1,
        "jd": 2,
        "pinduoduo": 3,
        "suning": 4,
        "vip": 5,
        "kaola": 6,
        "douyin": 7,
        "kuaishou": 8,
        "1688": 10,
    }
    return mapping.get(platform, 0)


def enrich_source_items(
    items: list[RawSourceItem],
    *,
    adapter: SourceAdapter,
    top_n: int = 3,
) -> list[RawSourceItem]:
    enriched: list[RawSourceItem] = []
    for index, item in enumerate(items):
        if index >= top_n:
            enriched.append(item)
            continue
        source = _source_to_code(item.source_platform)
        try:
            detail_item = adapter.detail(item.source_item_id, source=source)
        except Exception as exc:
            fallback = RawSourceItem(
                source_platform=item.source_platform,
                source_item_id=item.source_item_id,
                title=item.title,
                price=item.price,
                item_url=item.item_url,
                original_price=item.original_price,
                images=item.images,
                specs=item.specs,
                shop_name=item.shop_name,
                sales=item.sales,
                shipping_fee=item.shipping_fee,
                metadata={**item.metadata, "detail_error": str(exc)},
            )
            enriched.append(fallback)
            continue
        enriched.append(
            RawSourceItem(
                source_platform=detail_item.source_platform or item.source_platform,
                source_item_id=detail_item.source_item_id or item.source_item_id,
                title=detail_item.title or item.title,
                price=detail_item.price or item.price,
                item_url=detail_item.item_url or item.item_url,
                original_price=detail_item.original_price or item.original_price,
                images=detail_item.images or item.images,
                specs=detail_item.specs or item.specs,
                shop_name=detail_item.shop_name or item.shop_name,
                sales=detail_item.sales if detail_item.sales is not None else item.sales,
                shipping_fee=detail_item.shipping_fee if detail_item.shipping_fee is not None else item.shipping_fee,
                metadata={**item.metadata, **detail_item.metadata},
            )
        )
    return enriched


def build_candidate_report(
    keyword: str,
    *,
    limit: int = 20,
    source: int = 0,
    page: int = 1,
    enrich_top_n: int = 3,
    dedupe: bool = True,
    xianyu_only: bool = True,
    adapter: SourceAdapter | None = None,
    pricing: PricingConfig | None = None,
) -> list[dict]:
    adapter = adapter or MaishouAdapter()
    raw_items = adapter.search(keyword, limit=limit, source=source, page=page)
    if enrich_top_n > 0:
        raw_items = enrich_source_items(raw_items, adapter=adapter, top_n=enrich_top_n)
    normalized_items = [normalize_source_item(item) for item in raw_items]
    ranked_candidates = rank_candidates(normalized_items, pricing=pricing)
    if dedupe:
        ranked_candidates = dedupe_candidates(ranked_candidates)
    if xianyu_only:
        ranked_candidates = filter_candidates_for_xianyu(ranked_candidates)
    return [summarize_candidate(candidate) for candidate in ranked_candidates]
