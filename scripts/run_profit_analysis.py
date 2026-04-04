#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from xianyu_tools.models import HotItem, PricingConfig, RawSourceItem
from xianyu_tools.profit_analysis import build_profit_analysis


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build profit_analysis from a source-resolution bundle."
    )
    parser.add_argument(
        "--source-bundle-file",
        required=True,
        help="Path to a JSON file containing hot_items and source_items.",
    )
    parser.add_argument("--packaging-cost", type=float, default=1.5)
    parser.add_argument("--platform-fee-rate", type=float, default=0.03)
    parser.add_argument("--payment-fee-rate", type=float, default=0.006)
    parser.add_argument("--aftersale-reserve-rate", type=float, default=0.02)
    parser.add_argument("--min-margin", type=float, default=8.0)
    parser.add_argument("--min-margin-rate", type=float, default=0.18)
    args = parser.parse_args()

    bundle = json.loads(Path(args.source_bundle_file).read_text(encoding="utf-8"))
    hot_items = _load_hot_items(bundle.get("hot_items") or [])
    source_items = _load_source_items(bundle.get("source_items") or [])
    pricing = PricingConfig(
        packaging_cost=args.packaging_cost,
        platform_fee_rate=args.platform_fee_rate,
        payment_fee_rate=args.payment_fee_rate,
        aftersale_reserve_rate=args.aftersale_reserve_rate,
        min_margin=args.min_margin,
        min_margin_rate=args.min_margin_rate,
    )
    rows = build_profit_analysis(hot_items, source_items, pricing=pricing)
    print(json.dumps({"profit_analysis": rows}, ensure_ascii=False, indent=2))
    return 0


def _load_hot_items(rows: list[dict[str, Any]]) -> list[HotItem]:
    return [
        HotItem(
            hot_item_id=str(row.get("hot_item_id") or ""),
            platform=str(row.get("platform") or "xianyu"),
            title=str(row.get("title") or ""),
            price=float(row.get("price") or 0.0),
            want_count=_to_optional_int(row.get("want_count")),
            seller_name=_to_optional_str(row.get("seller_name")),
            area=_to_optional_str(row.get("area")),
            sales_volume=_to_optional_int(row.get("sales_volume")),
            hot_score=_to_optional_float(row.get("hot_score")),
            item_url=str(row.get("item_url") or ""),
            image_url=_to_optional_str(row.get("image_url")),
            metadata=dict(row.get("metadata") or {}),
        )
        for row in rows
        if isinstance(row, dict)
    ]


def _load_source_items(rows: list[dict[str, Any]]) -> list[RawSourceItem]:
    items: list[RawSourceItem] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("candidate_status") or "accepted") != "accepted":
            continue
        metadata = dict(row.get("metadata") or {})
        hot_item_id = str(row.get("hot_item_id") or "")
        if hot_item_id:
            metadata["hot_item_id"] = hot_item_id
        items.append(
            RawSourceItem(
                source_platform=str(row.get("source_platform") or ""),
                source_item_id=str(row.get("source_item_id") or ""),
                title=str(row.get("title") or ""),
                price=float(row.get("price") or 0.0),
                item_url=str(row.get("item_url") or ""),
                original_price=_to_optional_float(row.get("original_price")),
                images=list(row.get("images") or []),
                specs=dict(row.get("specs") or {}),
                shop_name=_to_optional_str(row.get("shop_name")),
                sales=_to_optional_int(row.get("sales")),
                shipping_fee=_to_optional_float(row.get("shipping_fee")),
                metadata=metadata,
            )
        )
    return items


def _to_optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _to_optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _to_optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


if __name__ == "__main__":
    sys.exit(main())
