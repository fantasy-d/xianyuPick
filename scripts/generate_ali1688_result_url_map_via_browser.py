#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from xianyu_tools.models import HotItem
from xianyu_tools.source_resolution import (
    build_source_query_from_hot_item,
    resolve_hot_items_to_ali1688_html,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate hot_item_id -> ali1688 filtered result URL map by running the browser flow with a persistent ali1688 session."
    )
    parser.add_argument("--hot-items-file", required=True, help="Path to a JSON file containing hot_items.")
    parser.add_argument("--output-file", required=True, help="Path to write the generated result-url map.")
    parser.add_argument("--summary-dir", default="./tmp/ali1688_browser_map_runs", help="Directory for per-item run artifacts.")
    parser.add_argument("--browser-channel", default="chrome")
    parser.add_argument("--user-data-dir", help="Override ali1688 persistent user-data-dir.")
    parser.add_argument("--profile-directory", help="Optional Chrome profile directory inside the user-data-dir.")
    parser.add_argument(
        "--launch-arg",
        action="append",
        default=[],
        help="Extra browser launch arg. Repeatable, e.g. --launch-arg=--start-maximized",
    )
    parser.add_argument("--limit", type=int, default=10, help="Maximum hot_items to process.")
    parser.add_argument(
        "--max-subject-switches",
        type=int,
        default=3,
        help="Maximum additional subject regions to try when the current image-search results are all irrelevant.",
    )
    args = parser.parse_args()

    hot_items = _load_hot_items(Path(args.hot_items_file))[: max(args.limit, 0) or None]
    summary_dir = Path(args.summary_dir)
    summary_dir.mkdir(parents=True, exist_ok=True)

    result: dict[str, str] = {}
    runs: list[dict[str, object]] = []
    for hot_item in hot_items:
        query = build_source_query_from_hot_item(hot_item)
        image_url = hot_item.image_url or ""
        slug = _safe_slug(hot_item.hot_item_id)
        output_dir = summary_dir / f"{slug}_artifacts"
        summary_file = summary_dir / f"{slug}_summary.json"

        command = [
            sys.executable,
            "scripts/run_ali1688_slow_flow.py",
            "--browser-channel",
            args.browser_channel,
            "--keep-open-seconds",
            "0",
            "--output-dir",
            str(output_dir),
            "--summary-json-file",
            str(summary_file),
            "--capture-all-subjects",
            "--max-subjects",
            str(max(args.max_subject_switches, 0) + 1),
        ]
        if image_url:
            command.extend(["--image-url", image_url])
        else:
            command.extend(["--keyword", query])
        if args.user_data_dir:
            command.extend(["--user-data-dir", args.user_data_dir])
        if args.profile_directory:
            command.extend(["--profile-directory", args.profile_directory])
        for launch_arg in args.launch_arg:
            command.append(f"--launch-arg={launch_arg}")

        completed = subprocess.run(
            command,
            cwd=Path(__file__).resolve().parents[1],
            env={**os.environ, "PYTHONPATH": "src"},
            capture_output=True,
            text=True,
            check=False,
        )
        summary = _load_summary(summary_file)
        accepted = False
        subject_runs = list((summary.get("subject_runs") or []) if isinstance(summary, dict) else [])
        if not subject_runs:
            subject_runs = [{"subject_index": 0, "html_path": str(_pick_html_path(output_dir) or ""), "final_url": str(summary.get("final_url") or "")}]
        for subject_run in subject_runs[: max(args.max_subject_switches, 0) + 1]:
            subject_index = int(subject_run.get("subject_index") or 0)
            html_path = Path(str(subject_run.get("html_path") or ""))
            resolution = _resolve_run_for_hot_item(hot_item, html_path)
            final_url = str(subject_run.get("final_url") or summary.get("final_url") or "")
            runs.append(
                {
                    "hot_item_id": hot_item.hot_item_id,
                    "query": query,
                    "image_url": image_url,
                    "search_mode": "image_url" if image_url else "keyword",
                    "subject_index": subject_index,
                    "returncode": completed.returncode,
                    "summary_file": str(summary_file),
                    "summary": summary,
                    "resolution": resolution,
                    "stdout": completed.stdout[-2000:],
                    "stderr": completed.stderr[-2000:],
                }
            )
            if final_url and resolution.get("resolved"):
                result[hot_item.hot_item_id] = final_url
                accepted = True
                break
        if not accepted:
            continue

    Path(args.output_file).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output_file": args.output_file,
                "count": len(result),
                "runs": runs,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _load_hot_items(path: Path) -> list[HotItem]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("hot_items") if isinstance(payload, dict) else payload
    category_keyword = ""
    if isinstance(payload, dict):
        category_keyword = str(((payload.get("xianyu_market") or {}).get("category_keyword")) or "")
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
                metadata={**dict(row.get("metadata") or {}), "category_keyword": category_keyword},
            )
        )
    return hot_items


def _load_summary(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_run_for_hot_item(hot_item: HotItem, html_path: Path) -> dict[str, object]:
    if html_path is None:
        return {"resolved": False, "resolution_reason": "missing_browser_html"}
    if str(html_path).strip() in {"", "."}:
        return {"resolved": False, "resolution_reason": "missing_browser_html"}
    if not html_path.exists() or not html_path.is_file():
        return {"resolved": False, "resolution_reason": "missing_browser_html"}
    bundle = resolve_hot_items_to_ali1688_html(
        [hot_item],
        html_by_hot_item_id={hot_item.hot_item_id: html_path.read_text(encoding="utf-8", errors="ignore")},
        metadata_by_hot_item_id={hot_item.hot_item_id: {"html_path": str(html_path)}},
        limit_per_item=5,
    )
    resolutions = bundle.get("source_resolution") or []
    return dict(resolutions[0] or {}) if resolutions else {"resolved": False, "resolution_reason": "missing_resolution"}


def _pick_html_path(artifacts_dir: Path) -> Path | None:
    candidates = [
        artifacts_dir / "08_subject_0_dropship_free_shipping.html",
        artifacts_dir / "07_subject_0_dropship.html",
        artifacts_dir / "08_filter_dropship_free_shipping.html",
        artifacts_dir / "06_subject_0_return_shipping.html",
        artifacts_dir / "07_filter_dropship.html",
        artifacts_dir / "06_filter_return_shipping.html",
        artifacts_dir / "04_after_subject_switch.html",
        artifacts_dir / "03_after_enter.html",
        artifacts_dir / "01_home.html",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _safe_slug(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value) or "item"


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
