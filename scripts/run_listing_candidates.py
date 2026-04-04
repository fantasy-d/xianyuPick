#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from xianyu_tools.listing_decision import ListingDecisionConfig, build_listing_candidates


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build listing_candidates from a source bundle and a profit_analysis file."
    )
    parser.add_argument(
        "--source-bundle-file",
        required=True,
        help="Path to a JSON file containing hot_items and source_items.",
    )
    parser.add_argument(
        "--profit-analysis-file",
        required=True,
        help="Path to a JSON file containing profit_analysis.",
    )
    parser.add_argument("--min-margin", type=float, default=8.0)
    parser.add_argument("--min-margin-rate", type=float, default=0.18)
    parser.add_argument("--max-risk-flags", type=int, default=2)
    parser.add_argument("--block-on-unknown-shipping-fee", action="store_true")
    parser.add_argument("--block-on-low-sales", action="store_true")
    args = parser.parse_args()

    source_bundle = json.loads(Path(args.source_bundle_file).read_text(encoding="utf-8"))
    profit_payload = json.loads(Path(args.profit_analysis_file).read_text(encoding="utf-8"))
    candidates = build_listing_candidates(
        source_bundle.get("hot_items") or [],
        source_bundle.get("source_items") or [],
        profit_payload.get("profit_analysis") or [],
        config=ListingDecisionConfig(
            min_margin=args.min_margin,
            min_margin_rate=args.min_margin_rate,
            max_risk_flags=args.max_risk_flags,
            block_on_unknown_shipping_fee=args.block_on_unknown_shipping_fee,
            block_on_low_sales=args.block_on_low_sales,
        ),
    )
    print(json.dumps({"listing_candidates": candidates}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
