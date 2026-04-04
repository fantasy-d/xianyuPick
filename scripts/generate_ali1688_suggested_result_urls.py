#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from xianyu_tools.models import HotItem
from xianyu_tools.source_adapter import Ali1688SourceAdapter
from xianyu_tools.source_resolution import build_source_query_from_hot_item


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate suggested ali1688 result URLs from hot_items using normalized source queries."
    )
    parser.add_argument("--hot-items-file", required=True, help="Path to a JSON file containing hot_items.")
    parser.add_argument(
        "--output-file",
        required=True,
        help="Path to write the hot_item_id -> suggested ali1688 result_url mapping.",
    )
    args = parser.parse_args()

    hot_items = _load_hot_items(Path(args.hot_items_file))
    adapter = Ali1688SourceAdapter()
    result = {}
    for hot_item in hot_items:
        source_query = build_source_query_from_hot_item(hot_item)
        result[hot_item.hot_item_id] = adapter.build_search_url(source_query, page=1)
    Path(args.output_file).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {"output_file": args.output_file, "count": len(result)},
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
    items: list[HotItem] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        items.append(
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
    return items


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
