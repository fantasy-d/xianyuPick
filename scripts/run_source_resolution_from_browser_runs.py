#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from xianyu_tools.models import HotItem
from xianyu_tools.source_resolution import resolve_hot_items_to_ali1688_html


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resolve hot_items to ali1688 source_items from browser-captured result pages."
    )
    parser.add_argument("--hot-items-file", required=True)
    parser.add_argument("--browser-runs-dir", required=True, help="Directory containing *_summary.json and *_artifacts/")
    parser.add_argument("--limit-per-item", type=int, default=10)
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()

    hot_items = _load_hot_items(Path(args.hot_items_file))
    browser_run_candidates = _load_browser_runs(Path(args.browser_runs_dir))
    bundle = _resolve_from_browser_run_candidates(
        hot_items,
        browser_run_candidates=browser_run_candidates,
        limit_per_item=args.limit_per_item,
    )
    output = (
        _build_summary_output(hot_items, bundle)
        if args.summary_only
        else {
            "hot_items": [_serialize_hot_item(item) for item in hot_items],
            "source_resolution": [_serialize_source_resolution(item) for item in bundle.get("source_resolution", [])],
            "source_items": bundle.get("source_items", []),
        }
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


def _load_hot_items(path: Path) -> list[HotItem]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("hot_items") if isinstance(payload, dict) else payload
    category_keyword = ""
    if isinstance(payload, dict):
        category_keyword = str(((payload.get("xianyu_market") or {}).get("category_keyword")) or "")
    if not isinstance(rows, list):
        raise ValueError("hot_items file must contain a list or an object with hot_items")
    result: list[HotItem] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        result.append(
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
                metadata={**dict(row.get("metadata") or {}), "category_keyword": category_keyword},
            )
        )
    return result


def _load_browser_runs(path: Path) -> dict[str, list[dict[str, Any]]]:
    candidates_by_hot_item_id: dict[str, list[dict[str, Any]]] = {}
    for summary_file in sorted(path.glob("*_summary.json")):
        stem = summary_file.stem.removesuffix("_summary")
        hot_item_id = stem.split("_subject_")[0]
        summary = json.loads(summary_file.read_text(encoding="utf-8"))
        artifacts_dir = path / f"{hot_item_id}_artifacts"
        subject_runs = list(summary.get("subject_runs") or []) if isinstance(summary, dict) else []
        if subject_runs:
            for run in subject_runs:
                html_path = Path(str(run.get("html_path") or ""))
                if not html_path.exists():
                    continue
                candidates_by_hot_item_id.setdefault(hot_item_id, []).append(
                    {
                        "html": html_path.read_text(encoding="utf-8", errors="ignore"),
                        "metadata": {
                            "summary_file": str(summary_file),
                            "artifacts_dir": str(artifacts_dir),
                            "final_url": str(run.get("final_url") or ""),
                            "status": str(summary.get("status") or ""),
                            "ok": bool(summary.get("ok")),
                            "subject_count": int(summary.get("subject_count") or 0),
                            "selected_subject_index": int(run.get("subject_index") or 0),
                            "html_path": str(html_path),
                        },
                    }
                )
            continue

        html_path = _pick_html_path(artifacts_dir)
        if html_path and html_path.exists():
            candidates_by_hot_item_id.setdefault(hot_item_id, []).append(
                {
                    "html": html_path.read_text(encoding="utf-8", errors="ignore"),
                    "metadata": {
                        "summary_file": str(summary_file),
                        "artifacts_dir": str(artifacts_dir),
                        "final_url": str(summary.get("final_url") or ""),
                        "status": str(summary.get("status") or ""),
                        "ok": bool(summary.get("ok")),
                        "subject_count": int(summary.get("subject_count") or 0),
                        "selected_subject_index": int(summary.get("selected_subject_index") or 0),
                        "html_path": str(html_path),
                    },
                }
            )
    return candidates_by_hot_item_id


def _resolve_from_browser_run_candidates(
    hot_items: list[HotItem],
    *,
    browser_run_candidates: dict[str, list[dict[str, Any]]],
    limit_per_item: int,
) -> dict[str, Any]:
    hot_items_output = [_serialize_hot_item(item) for item in hot_items]
    source_resolution: list[dict[str, Any]] = []
    source_items: list[dict[str, Any]] = []

    for hot_item in hot_items:
        candidates = browser_run_candidates.get(hot_item.hot_item_id) or []
        if not candidates:
            bundle = resolve_hot_items_to_ali1688_html(
                [hot_item],
                html_by_hot_item_id={},
                metadata_by_hot_item_id={},
                limit_per_item=limit_per_item,
            )
            source_resolution.extend(bundle.get("source_resolution") or [])
            source_items.extend(bundle.get("source_items") or [])
            continue

        selected_bundle = None
        fallback_bundle = None
        for candidate in candidates:
            bundle = resolve_hot_items_to_ali1688_html(
                [hot_item],
                html_by_hot_item_id={hot_item.hot_item_id: candidate["html"]},
                metadata_by_hot_item_id={hot_item.hot_item_id: dict(candidate["metadata"] or {})},
                limit_per_item=limit_per_item,
            )
            resolution = (bundle.get("source_resolution") or [{}])[0]
            if fallback_bundle is None:
                fallback_bundle = bundle
            if resolution.get("resolved"):
                selected_bundle = bundle
                break
        final_bundle = selected_bundle or fallback_bundle or {"source_resolution": [], "source_items": []}
        source_resolution.extend(final_bundle.get("source_resolution") or [])
        source_items.extend(final_bundle.get("source_items") or [])

    return {
        "hot_items": hot_items_output,
        "source_resolution": source_resolution,
        "source_items": source_items,
    }


def _pick_html_path(artifacts_dir: Path) -> Path | None:
    candidates = [
        artifacts_dir / "08_subject_0_dropship_free_shipping.html",
        artifacts_dir / "08_subject_1_dropship_free_shipping.html",
        artifacts_dir / "08_subject_2_dropship_free_shipping.html",
        artifacts_dir / "07_subject_0_dropship.html",
        artifacts_dir / "07_subject_1_dropship.html",
        artifacts_dir / "07_subject_2_dropship.html",
        artifacts_dir / "08_filter_dropship_free_shipping.html",
        artifacts_dir / "07_filter_dropship.html",
        artifacts_dir / "06_filter_return_shipping.html",
        artifacts_dir / "03_after_enter.html",
        artifacts_dir / "01_home.html",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _build_summary_output(hot_items: list[HotItem], bundle: dict[str, Any]) -> dict[str, Any]:
    source_items_by_hot_item_id: dict[str, list[dict[str, Any]]] = {}
    for item in bundle.get("source_items", []):
        hot_item_id = str(item.get("hot_item_id") or "")
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
                "seller_name": hot_item.seller_name,
                "area": hot_item.area,
                "item_url": hot_item.item_url,
                "image_url": hot_item.image_url,
                "publish_time": (hot_item.metadata or {}).get("publish_time"),
                "tags": (hot_item.metadata or {}).get("tags") or [],
                "source_resolution": resolution_by_hot_item_id.get(hot_item.hot_item_id),
                "source_items": source_items_by_hot_item_id.get(hot_item.hot_item_id, []),
            }
            for hot_item in hot_items
        ]
    }


def _serialize_hot_item(item: HotItem) -> dict[str, Any]:
    return {
        "hot_item_id": item.hot_item_id,
        "platform": item.platform,
        "title": item.title,
        "price": item.price,
        "want_count": item.want_count,
        "seller_name": item.seller_name,
        "area": item.area,
        "item_url": item.item_url,
        "image_url": item.image_url,
        "publish_time": (item.metadata or {}).get("publish_time"),
        "tags": (item.metadata or {}).get("tags") or [],
    }


def _serialize_source_resolution(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "hot_item_id": row.get("hot_item_id"),
        "resolved": row.get("resolved"),
        "source_item_ids": row.get("source_item_ids") or [],
        "resolution_reason": row.get("resolution_reason"),
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
