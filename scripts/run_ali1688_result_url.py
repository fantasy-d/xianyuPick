#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from xianyu_tools.source_adapter import Ali1688SourceAdapter


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse a 1688 search-result URL into normalized source_items."
    )
    parser.add_argument("--result-url", required=True, help="A 1688 result page URL.")
    parser.add_argument("--limit", type=int, default=20, help="Maximum number of source items to return.")
    args = parser.parse_args()

    adapter = Ali1688SourceAdapter()
    items = adapter.search_from_result_url(args.result_url, limit=args.limit)
    output = {
        "result_url": args.result_url,
        "source_items": [
            {
                "source_item_id": item.source_item_id,
                "source_platform": item.source_platform,
                "title": item.title,
                "price": item.price,
                "shipping_fee": item.shipping_fee,
                "item_url": item.item_url,
                "shop_name": item.shop_name,
                "sales": item.sales,
                "metadata": item.metadata,
            }
            for item in items
        ],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
