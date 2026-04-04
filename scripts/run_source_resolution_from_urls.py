#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from xianyu_tools.models import HotItem
from xianyu_tools.source_resolution import resolve_hot_items_to_ali1688_urls


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resolve hot_items to 1688 source_items from a hot_item_id -> result_url mapping."
    )
    parser.add_argument(
        "--hot-items-file",
        required=True,
        help="Path to a JSON file containing hot_items, usually output by run_xianyu_hot_items.py.",
    )
    parser.add_argument(
        "--result-url-map-file",
        required=True,
        help="Path to a JSON object mapping hot_item_id to an ali1688 result page URL.",
    )
    parser.add_argument(
        "--limit-per-item",
        type=int,
        default=10,
        help="Maximum number of source items to keep for each hot item.",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print a reduced output with hot_items, source_resolution, and grouped source_items.",
    )
    args = parser.parse_args()

    hot_items = _load_hot_items(Path(args.hot_items_file))
    result_url_map = _load_result_url_map(Path(args.result_url_map_file))
    bundle = resolve_hot_items_to_ali1688_urls(
        hot_items,
        result_urls_by_hot_item_id=result_url_map,
        limit_per_item=args.limit_per_item,
    )
    output = (
        _build_summary_output(hot_items, bundle)
        if args.summary_only
        else _build_full_output(hot_items, bundle, result_url_map)
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


def _load_hot_items(path: Path) -> list[HotItem]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        rows = payload.get("hot_items")
    else:
        rows = payload
    if not isinstance(rows, list):
        raise ValueError("hot_items file must contain a list or an object with hot_items")
    hot_items: list[HotItem] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("each hot_item must be an object")
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


def _load_result_url_map(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("result url map file must be a JSON object")
    return {
        str(hot_item_id): str(result_url).strip()
        for hot_item_id, result_url in payload.items()
        if str(hot_item_id).strip()
    }


def _build_full_output(
    hot_items: list[HotItem],
    bundle: dict[str, Any],
    result_url_map: dict[str, str],
) -> dict[str, Any]:
    return {
        "hot_items": [_serialize_hot_item(item, result_url_map) for item in hot_items],
        "source_resolution": bundle.get("source_resolution", []),
        "source_items": bundle.get("source_items", []),
    }


def _build_summary_output(
    hot_items: list[HotItem],
    bundle: dict[str, Any],
) -> dict[str, Any]:
    source_items_by_hot_item_id: dict[str, list[dict[str, Any]]] = {}
    for item in bundle.get("source_items", []):
        metadata = item.get("metadata") or {}
        hot_item_id = str(metadata.get("hot_item_id") or "")
        if not hot_item_id:
            continue
        source_items_by_hot_item_id.setdefault(hot_item_id, []).append(
            {
                "source_platform": item.get("source_platform"),
                "source_item_id": item.get("source_item_id"),
                "title": item.get("title"),
                "price": item.get("price"),
                "item_url": item.get("item_url"),
                "shop_name": item.get("shop_name"),
                "sales": item.get("sales"),
            }
        )

    resolution_by_hot_item_id = {
        str(item.get("hot_item_id") or ""): item
        for item in bundle.get("source_resolution", [])
    }

    return {
        "hot_items": [
            {
                "hot_item_id": hot_item.hot_item_id,
                "title": hot_item.title,
                "price": hot_item.price,
                "want_count": hot_item.want_count,
                "item_url": hot_item.item_url,
                "image_url": hot_item.image_url,
                "source_resolution": resolution_by_hot_item_id.get(hot_item.hot_item_id),
                "source_items": source_items_by_hot_item_id.get(hot_item.hot_item_id, []),
            }
            for hot_item in hot_items
        ]
    }


def _serialize_hot_item(hot_item: HotItem, result_url_map: dict[str, str]) -> dict[str, Any]:
    return {
        "hot_item_id": hot_item.hot_item_id,
        "platform": hot_item.platform,
        "title": hot_item.title,
        "price": hot_item.price,
        "want_count": hot_item.want_count,
        "seller_name": hot_item.seller_name,
        "area": hot_item.area,
        "item_url": hot_item.item_url,
        "image_url": hot_item.image_url,
        "result_url": result_url_map.get(hot_item.hot_item_id, ""),
        "metadata": hot_item.metadata,
    }


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
