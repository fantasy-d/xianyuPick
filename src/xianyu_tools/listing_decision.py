from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ListingDecisionConfig:
    min_margin: float = 8.0
    min_margin_rate: float = 0.18
    max_risk_flags: int = 2
    block_on_unknown_shipping_fee: bool = False
    block_on_low_sales: bool = False


def build_listing_candidates(
    hot_items: list[dict[str, Any]],
    source_items: list[dict[str, Any]],
    profit_analysis: list[dict[str, Any]],
    *,
    config: ListingDecisionConfig | None = None,
) -> list[dict[str, Any]]:
    config = config or ListingDecisionConfig()
    hot_items_by_id = {
        str(row.get("hot_item_id") or ""): row
        for row in hot_items
        if row.get("hot_item_id")
    }
    source_items_by_id = {
        str(row.get("source_item_id") or ""): row
        for row in source_items
        if row.get("source_item_id")
    }

    best_by_hot_item_id: dict[str, dict[str, Any]] = {}
    for row in profit_analysis:
        hot_item_id = str(row.get("hot_item_id") or "")
        if not hot_item_id:
            continue
        current = best_by_hot_item_id.get(hot_item_id)
        if current is None or _profit_sort_key(row) > _profit_sort_key(current):
            best_by_hot_item_id[hot_item_id] = row

    results: list[dict[str, Any]] = []
    for hot_item_id, row in best_by_hot_item_id.items():
        source_item_id = str(row.get("source_item_id") or "")
        decision = _build_decision(row, config)
        results.append(
            {
                "hot_item_id": hot_item_id,
                "source_item_id": source_item_id,
                "estimated_margin": row.get("estimated_margin", 0.0),
                "gross_margin_rate": row.get("gross_margin_rate", 0.0),
                "cost_profit_rate": row.get("cost_profit_rate", 0.0),
                "is_recommended": decision["is_recommended"],
                "reasons": decision["reasons"],
                "blocked_by": decision["blocked_by"],
            }
        )

    return sorted(
        results,
        key=lambda row: (
            bool(row["is_recommended"]),
            row.get("estimated_margin", 0.0),
            row.get("gross_margin_rate", 0.0),
            row.get("cost_profit_rate", 0.0),
        ),
        reverse=True,
    )


def _profit_sort_key(row: dict[str, Any]) -> tuple[float, float, float]:
    return (
        float(row.get("estimated_margin") or 0.0),
        float(row.get("gross_margin_rate") or 0.0),
        float(row.get("cost_profit_rate") or 0.0),
        -len(row.get("risk_flags") or []),
    )


def _build_decision(
    row: dict[str, Any],
    config: ListingDecisionConfig,
) -> dict[str, Any]:
    estimated_margin = float(row.get("estimated_margin") or 0.0)
    gross_margin_rate = float(row.get("gross_margin_rate") or 0.0)
    risk_flags = list(row.get("risk_flags") or [])

    blocked_by: list[str] = []
    reasons: list[str] = []

    if estimated_margin < config.min_margin:
        blocked_by.append("low_margin")
    else:
        reasons.append("margin_ok")

    if gross_margin_rate < config.min_margin_rate:
        blocked_by.append("low_gross_margin_rate")
    else:
        reasons.append("gross_margin_rate_ok")

    if len(risk_flags) > config.max_risk_flags:
        blocked_by.append("too_many_risk_flags")

    if config.block_on_unknown_shipping_fee and "unknown_shipping_fee" in risk_flags:
        blocked_by.append("unknown_shipping_fee")
    elif "unknown_shipping_fee" not in risk_flags:
        reasons.append("shipping_fee_known")

    if config.block_on_low_sales and "low_sales" in risk_flags:
        blocked_by.append("low_sales")
    elif "low_sales" not in risk_flags:
        reasons.append("sales_ok")

    if "missing_buy_url" in risk_flags:
        blocked_by.append("missing_buy_url")

    return {
        "is_recommended": not blocked_by,
        "reasons": sorted(set(reasons)),
        "blocked_by": sorted(set(blocked_by)),
    }
