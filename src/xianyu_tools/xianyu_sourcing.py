from __future__ import annotations

from xianyu_tools.models import PricingConfig, XianyuSearchItem
from xianyu_tools.pipeline import build_candidate_report
from xianyu_tools.reporting import simplify_xianyu_item
from xianyu_tools.source_adapter.base import SourceAdapter
from xianyu_tools.source_normalizer import extract_model_hint, extract_title_tokens, normalize_brand_hint
from xianyu_tools.xianyu_adapter.base import XianyuAdapter


def build_xianyu_sourcing_report(
    keyword: str,
    *,
    xianyu_adapter: XianyuAdapter,
    source_adapter: SourceAdapter,
    xianyu_page: int = 1,
    xianyu_limit: int = 5,
    source_limit: int = 10,
    enrich_top_n: int = 3,
    pricing: PricingConfig | None = None,
) -> list[dict]:
    bundle = build_xianyu_sourcing_bundle(
        keyword,
        xianyu_adapter=xianyu_adapter,
        source_adapter=source_adapter,
        xianyu_page=xianyu_page,
        xianyu_limit=xianyu_limit,
        source_limit=source_limit,
        enrich_top_n=enrich_top_n,
        pricing=pricing,
    )
    return _extract_processed_items(bundle)


def build_xianyu_sourcing_bundle(
    keyword: str,
    *,
    xianyu_adapter: XianyuAdapter,
    source_adapter: SourceAdapter,
    xianyu_page: int = 1,
    xianyu_limit: int = 5,
    source_limit: int = 10,
    enrich_top_n: int = 3,
    pricing: PricingConfig | None = None,
) -> dict:
    pricing = pricing or PricingConfig()
    xianyu_items_all = xianyu_adapter.search(keyword, page=xianyu_page)
    xianyu_items = xianyu_items_all[:xianyu_limit]
    search_items = [simplify_xianyu_item(item) for item in xianyu_items_all]
    search_item_by_id = {
        str(item.get("item_id") or ""): item for item in search_items
    }
    for xianyu_item in xianyu_items:
        source_keyword = build_source_keyword_from_xianyu(xianyu_item)
        source_candidates = build_candidate_report(
            source_keyword,
            limit=source_limit,
            enrich_top_n=enrich_top_n,
            adapter=source_adapter,
            pricing=pricing,
        )
        matched_candidates = match_source_candidates(xianyu_item, source_candidates)
        item_id = str(xianyu_item.item_id or "")
        if item_id in search_item_by_id:
            search_item_by_id[item_id]["source_keyword"] = source_keyword
            search_item_by_id[item_id]["matched_candidates"] = matched_candidates
    return {
        "search_returned_count": len(xianyu_items_all),
        "search_items": search_items,
    }


def _extract_processed_items(bundle: dict) -> list[dict]:
    processed_items: list[dict] = []
    for item in bundle.get("search_items", []):
        if "source_keyword" not in item and "matched_candidates" not in item:
            continue
        processed_items.append(
            {
                "xianyu_item": simplify_xianyu_item(item),
                "source_keyword": item.get("source_keyword"),
                "matched_candidates": item.get("matched_candidates") or [],
            }
        )
    return processed_items


def build_source_keyword_from_xianyu(xianyu_item: XianyuSearchItem) -> str:
    model_hint = extract_model_hint(xianyu_item.title)
    tokens = extract_title_tokens(xianyu_item.title)
    high_signal_tokens = []
    for token in tokens:
        if token not in {"全新", "国行", "二手", "闲置", "自用", "99新", "95新"}:
            high_signal_tokens.append(token)
    compact_model = "".join(
        token for token in high_signal_tokens[:4] if all(char.isascii() and char.isalnum() for char in token)
    )
    parts = [part for part in [model_hint, compact_model, *high_signal_tokens[:4]] if part]
    if not parts:
        return xianyu_item.title
    return " ".join(dict.fromkeys(parts))


def match_source_candidates(
    xianyu_item: XianyuSearchItem,
    source_candidates: list[dict],
) -> list[dict]:
    xianyu_tokens = set(extract_title_tokens(xianyu_item.title))
    xianyu_model = extract_model_hint(xianyu_item.title)
    xianyu_brand = normalize_brand_hint(xianyu_item.seller_name or "")

    ranked_matches: list[dict] = []
    for candidate in source_candidates:
        item = candidate["item"]
        source_tokens = set(item["metadata"].get("normalized_tokens") or [])
        source_model = item["metadata"].get("model_hint") or ""
        source_brand = item["metadata"].get("brand_hint") or ""

        overlap = len(xianyu_tokens & source_tokens)
        union = len(xianyu_tokens | source_tokens) or 1
        token_score = overlap / union
        model_score = 1.0 if xianyu_model and xianyu_model == source_model else 0.0
        brand_score = 1.0 if xianyu_brand and xianyu_brand == source_brand else 0.0
        price_gap = round(xianyu_item.price - item["price"], 2)
        resale_margin = round(xianyu_item.price - candidate["estimated_cost"], 2)

        match_score = round(token_score * 0.6 + model_score * 0.3 + brand_score * 0.1, 4)
        ranked_matches.append(
            {
                **candidate,
                "match_score": match_score,
                "price_gap_vs_xianyu": price_gap,
                "xianyu_resale_margin": resale_margin,
                "is_profitable_vs_xianyu": resale_margin > 0,
            }
        )

    return sorted(
        ranked_matches,
        key=lambda candidate: (candidate["match_score"], candidate["xianyu_resale_margin"]),
        reverse=True,
    )
