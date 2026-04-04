from __future__ import annotations

from xianyu_tools.models import Candidate, NormalizedSourceItem, PricingConfig


def estimate_resale_price(item: NormalizedSourceItem, pricing: PricingConfig) -> float:
    return round(item.price * (1 + pricing.markup_rate), 2)


def rank_candidates(
    items: list[NormalizedSourceItem],
    *,
    pricing: PricingConfig | None = None,
) -> list[Candidate]:
    pricing = pricing or PricingConfig()
    ranked: list[Candidate] = []
    for item in items:
        estimated_resale_price = estimate_resale_price(item, pricing)
        platform_fee = estimated_resale_price * pricing.platform_fee_rate
        payment_fee = estimated_resale_price * pricing.payment_fee_rate
        aftersale_reserve = estimated_resale_price * pricing.aftersale_reserve_rate
        estimated_cost = round(
            item.price
            + item.shipping_fee
            + pricing.packaging_cost
            + platform_fee
            + payment_fee
            + aftersale_reserve,
            2,
        )
        estimated_margin = round(estimated_resale_price - estimated_cost, 2)
        estimated_margin_rate = round(
            estimated_margin / estimated_resale_price,
            4,
        ) if estimated_resale_price else 0.0

        risk_flags: list[str] = []
        if (item.sales or 0) < 20:
            risk_flags.append("low_sales")
        if item.shipping_fee > 10:
            risk_flags.append("high_shipping_fee")
        if not item.item_url:
            risk_flags.append("missing_buy_url")
        if estimated_margin < pricing.min_margin:
            risk_flags.append("low_margin")
        if estimated_margin_rate < pricing.min_margin_rate:
            risk_flags.append("low_margin_rate")

        score = estimated_margin + min((item.sales or 0) / 100, 8)
        score += min(estimated_margin_rate * 20, 5)
        if risk_flags:
            score -= len(risk_flags) * 2

        ranked.append(
            Candidate(
                item=item,
                estimated_cost=estimated_cost,
                estimated_resale_price=estimated_resale_price,
                estimated_margin=estimated_margin,
                estimated_margin_rate=estimated_margin_rate,
                score=round(score, 2),
                risk_flags=risk_flags,
            )
        )

    return sorted(ranked, key=lambda candidate: candidate.score, reverse=True)
