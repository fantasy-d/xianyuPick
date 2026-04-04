from __future__ import annotations

from collections import Counter
from typing import Any


def build_pipeline_summary(
    *,
    keyword: str,
    hot_payload: dict[str, Any],
    source_bundle: dict[str, Any],
    profit_payload: dict[str, Any],
    listing_payload: dict[str, Any],
) -> dict[str, Any]:
    hot_items = list(hot_payload.get("hot_items") or source_bundle.get("hot_items") or [])
    xianyu_market = dict(hot_payload.get("xianyu_market") or {})
    source_resolution = list(source_bundle.get("source_resolution") or [])
    source_items = list(source_bundle.get("source_items") or [])
    profit_analysis = list(profit_payload.get("profit_analysis") or [])
    listing_candidates = list(listing_payload.get("listing_candidates") or [])

    accepted_source_items = [row for row in source_items if str(row.get("candidate_status") or "accepted") == "accepted"]
    filtered_source_items = [row for row in source_items if str(row.get("candidate_status") or "") == "filtered"]
    resolution_reason_counts = Counter(str(row.get("resolution_reason") or "unknown") for row in source_resolution)
    blocked_reason_counts = Counter()
    for row in listing_candidates:
        for reason in row.get("blocked_by") or []:
            blocked_reason_counts[str(reason)] += 1

    recommended_items = [
        {
            "hot_item_id": row.get("hot_item_id"),
            "source_item_id": row.get("source_item_id"),
            "estimated_margin": row.get("estimated_margin"),
            "gross_margin_rate": row.get("gross_margin_rate"),
            "cost_profit_rate": row.get("cost_profit_rate"),
            "reasons": row.get("reasons") or [],
        }
        for row in listing_candidates
        if bool(row.get("is_recommended"))
    ]

    return {
        "keyword": keyword,
        "xianyu_market": {
            "category_keyword": xianyu_market.get("category_keyword") or keyword,
            "result_count": xianyu_market.get("result_count") or 0,
            "filtered_by": xianyu_market.get("filtered_by") or [],
            "sorted_by": xianyu_market.get("sorted_by") or "",
            "top_n": xianyu_market.get("top_n") or len(hot_items),
            "top10_price_stats": dict(xianyu_market.get("top10_price_stats") or {}),
        },
        "counts": {
            "hot_items": len(hot_items),
            "source_resolution": len(source_resolution),
            "accepted_source_items": len(accepted_source_items),
            "filtered_source_items": len(filtered_source_items),
            "profit_analysis": len(profit_analysis),
            "listing_candidates": len(listing_candidates),
            "recommended_listing_candidates": len(recommended_items),
        },
        "resolution_reason_counts": dict(resolution_reason_counts),
        "blocked_reason_counts": dict(blocked_reason_counts),
        "recommended_items": recommended_items,
    }
