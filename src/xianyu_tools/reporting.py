from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any


def dataclass_to_dict(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return dict(value)
    raise TypeError(f"Unsupported value for serialization: {type(value)!r}")


def simplify_xianyu_item(item: Any) -> dict[str, Any]:
    row = dataclass_to_dict(item)
    return {
        "item_id": row.get("item_id"),
        "title": row.get("title"),
        "price": row.get("price"),
        "original_price": row.get("original_price"),
        "seller_name": row.get("seller_name"),
        "area": row.get("area"),
        "publish_time": row.get("publish_time"),
        "item_url": row.get("item_url"),
        "image_url": row.get("image_url"),
        "tags": row.get("tags"),
    }


def build_xianyu_sourcing_summary(bundle: dict[str, Any], *, top_n: int = 3) -> dict[str, Any]:
    summary_items: list[dict[str, Any]] = []
    for item in bundle.get("search_items", []):
        summary_item = simplify_xianyu_item(item)
        if item.get("source_keyword"):
            summary_item["source_keyword"] = item.get("source_keyword")
        if item.get("matched_candidates"):
            summary_item["top_candidates"] = [
                summarize_matched_candidate(candidate)
                for candidate in item.get("matched_candidates", [])[:top_n]
            ]
        summary_items.append(summary_item)
    return {
        "search_returned_count": bundle.get("search_returned_count", 0),
        "search_items": summary_items,
    }


def summarize_matched_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    candidate_item = candidate.get("item", {})
    return {
        "platform": candidate_item.get("source_platform"),
        "title": candidate_item.get("title"),
        "price": candidate_item.get("price"),
        "item_url": candidate_item.get("item_url"),
        "match_score": candidate.get("match_score"),
        "estimated_margin": candidate.get("estimated_margin"),
        "xianyu_resale_margin": candidate.get("xianyu_resale_margin"),
        "is_profitable_vs_xianyu": candidate.get("is_profitable_vs_xianyu"),
    }
