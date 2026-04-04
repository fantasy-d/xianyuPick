#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from xianyu_tools.listing_decision import ListingDecisionConfig, build_listing_candidates
from xianyu_tools.models import HotItem, PricingConfig, RawSourceItem
from xianyu_tools.profit_analysis import build_profit_analysis
from xianyu_tools.source_resolution import resolve_hot_items_to_ali1688_urls


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run source resolution, profit analysis, and listing decision from hot_items + ali1688 result URLs."
    )
    parser.add_argument("--hot-items-file", required=True)
    parser.add_argument("--result-url-map-file", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--limit-per-item", type=int, default=10)
    parser.add_argument("--packaging-cost", type=float, default=1.5)
    parser.add_argument("--platform-fee-rate", type=float, default=0.03)
    parser.add_argument("--payment-fee-rate", type=float, default=0.006)
    parser.add_argument("--aftersale-reserve-rate", type=float, default=0.02)
    parser.add_argument("--min-margin", type=float, default=8.0)
    parser.add_argument("--min-margin-rate", type=float, default=0.18)
    parser.add_argument("--max-risk-flags", type=int, default=2)
    args = parser.parse_args()

    hot_items = _load_hot_items(Path(args.hot_items_file))
    result_url_map = json.loads(Path(args.result_url_map_file).read_text(encoding="utf-8"))
    source_bundle = resolve_hot_items_to_ali1688_urls(
        hot_items,
        result_urls_by_hot_item_id=result_url_map,
        limit_per_item=args.limit_per_item,
    )
    source_bundle["hot_items"] = [_serialize_hot_item(item) for item in hot_items]

    pricing = PricingConfig(
        packaging_cost=args.packaging_cost,
        platform_fee_rate=args.platform_fee_rate,
        payment_fee_rate=args.payment_fee_rate,
        aftersale_reserve_rate=args.aftersale_reserve_rate,
        min_margin=args.min_margin,
        min_margin_rate=args.min_margin_rate,
    )
    source_items = _load_source_items(source_bundle.get("source_items") or [])
    profit_payload = {
        "profit_analysis": build_profit_analysis(hot_items, source_items, pricing=pricing),
    }
    listing_payload = {
        "listing_candidates": build_listing_candidates(
            source_bundle.get("hot_items") or [],
            source_bundle.get("source_items") or [],
            profit_payload["profit_analysis"],
            config=ListingDecisionConfig(
                min_margin=args.min_margin,
                min_margin_rate=args.min_margin_rate,
                max_risk_flags=args.max_risk_flags,
            ),
        )
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    source_bundle_file = output_dir / "source_bundle.json"
    profit_file = output_dir / "profit_analysis.json"
    listing_file = output_dir / "listing_candidates.json"
    source_bundle_file.write_text(json.dumps(source_bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    profit_file.write_text(json.dumps(profit_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    listing_file.write_text(json.dumps(listing_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "source_bundle_file": str(source_bundle_file),
                "profit_analysis_file": str(profit_file),
                "listing_candidates_file": str(listing_file),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _load_hot_items(path: Path) -> list[HotItem]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("hot_items") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError("hot_items file must contain a list or an object with hot_items")
    hot_items: list[HotItem] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        hot_items.append(
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
        )
    return hot_items


def _load_source_items(rows: list[dict]) -> list[RawSourceItem]:
    result: list[RawSourceItem] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        result.append(
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
                metadata=dict(row.get("metadata") or {}),
            )
        )
    return result


def _serialize_hot_item(item: HotItem) -> dict:
    return {
        "hot_item_id": item.hot_item_id,
        "platform": item.platform,
        "title": item.title,
        "price": item.price,
        "want_count": item.want_count,
        "seller_name": item.seller_name,
        "area": item.area,
        "item_url": item.item_url,
        "metadata": item.metadata,
    }


def _to_optional_int(value):
    if value in (None, ""):
        return None
    return int(value)


def _to_optional_float(value):
    if value in (None, ""):
        return None
    return float(value)


def _to_optional_str(value):
    if value in (None, ""):
        return None
    return str(value)


if __name__ == "__main__":
    sys.exit(main())
