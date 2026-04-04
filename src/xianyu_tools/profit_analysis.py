from __future__ import annotations

from typing import Any

from xianyu_tools.models import HotItem, PricingConfig, RawSourceItem


def build_profit_analysis(
    hot_items: list[HotItem],
    source_items: list[RawSourceItem],
    *,
    pricing: PricingConfig | None = None,
) -> list[dict[str, Any]]:
    pricing = pricing or PricingConfig()
    hot_items_by_id = {item.hot_item_id: item for item in hot_items}
    rows: list[dict[str, Any]] = []
    for source_item in source_items:
        metadata = dict(source_item.metadata or {})
        hot_item_id = str(metadata.get("hot_item_id") or "")
        hot_item = hot_items_by_id.get(hot_item_id)
        if hot_item is None:
            continue
        row = _build_profit_row(hot_item, source_item, pricing)
        rows.append(row)
    return sorted(
        rows,
        key=lambda row: (
            row["estimated_margin"],
            row["gross_margin_rate"],
            row["cost_profit_rate"],
            row["target_xianyu_price"],
        ),
        reverse=True,
    )


def _build_profit_row(
    hot_item: HotItem,
    source_item: RawSourceItem,
    pricing: PricingConfig,
) -> dict[str, Any]:
    target_xianyu_price = round(float(hot_item.price or 0.0), 2)
    shipping_fee = round(float(source_item.shipping_fee or 0.0), 2)
    source_cost = round(float(source_item.price or 0.0) + shipping_fee, 2)
    platform_fee = round(target_xianyu_price * pricing.platform_fee_rate, 2)
    payment_fee = round(target_xianyu_price * pricing.payment_fee_rate, 2)
    aftersale_reserve = round(target_xianyu_price * pricing.aftersale_reserve_rate, 2)
    total_cost = round(
        source_cost
        + pricing.packaging_cost
        + platform_fee
        + payment_fee
        + aftersale_reserve,
        2,
    )
    estimated_margin = round(target_xianyu_price - total_cost, 2)
    gross_margin_rate = round(
        estimated_margin / target_xianyu_price,
        4,
    ) if target_xianyu_price else 0.0
    cost_profit_rate = round(
        estimated_margin / total_cost,
        4,
    ) if total_cost else 0.0

    risk_flags: list[str] = []
    if source_item.shipping_fee is None:
        risk_flags.append("unknown_shipping_fee")
    if shipping_fee > 10:
        risk_flags.append("high_shipping_fee")
    if (source_item.sales or 0) < 20:
        risk_flags.append("low_sales")
    if estimated_margin < pricing.min_margin:
        risk_flags.append("low_margin")
    if gross_margin_rate < pricing.min_margin_rate:
        risk_flags.append("low_gross_margin_rate")
    if not source_item.item_url:
        risk_flags.append("missing_buy_url")

    return {
        "hot_item_id": hot_item.hot_item_id,
        "source_item_id": source_item.source_item_id,
        "source_cost": source_cost,
        "target_xianyu_price": target_xianyu_price,
        "estimated_margin": estimated_margin,
        "gross_margin_rate": gross_margin_rate,
        "cost_profit_rate": cost_profit_rate,
        "risk_flags": risk_flags,
    }
