#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
import random

from playwright.async_api import async_playwright

from xianyu_tools.models import HotItem
from xianyu_tools.xianyu_adapter.browser_transport import (
    default_desktop_context_options,
    default_launch_args,
)

from run_ali1688_slow_flow import DEFAULT_ALI1688_USER_DATA_DIR, _run_flow_on_page
from run_source_resolution_from_browser_runs import _load_hot_items


async def _close_extra_pages(context, keep_page) -> object:
    latest = keep_page
    for page in list(context.pages):
        if page is keep_page:
            continue
        latest = page
    for page in list(context.pages):
        if page is latest:
            continue
        try:
            await page.close()
        except Exception:
            pass
    return latest


async def _run(args) -> None:
    hot_items = _load_hot_items(Path(args.hot_items_file))[: max(args.limit, 0) or None]
    summary_dir = Path(args.summary_dir)
    summary_dir.mkdir(parents=True, exist_ok=True)
    launch_args = [*default_launch_args(), *args.launch_arg]

    async with async_playwright() as playwright:
        persistent_args = list(launch_args)
        if args.profile_directory:
            persistent_args.append(f"--profile-directory={args.profile_directory}")
        context = await playwright.chromium.launch_persistent_context(
            args.user_data_dir,
            channel=args.browser_channel,
            headless=False,
            slow_mo=args.slow_mo_ms,
            args=persistent_args,
            **default_desktop_context_options(),
        )
        try:
            page = context.pages[0] if context.pages else await context.new_page()
            runs: list[dict[str, object]] = []
            result: dict[str, str] = {}

            for hot_item in hot_items:
                slug = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in hot_item.hot_item_id) or "item"
                output_dir = summary_dir / f"{slug}_artifacts"
                output_dir.mkdir(parents=True, exist_ok=True)
                summary_file = summary_dir / f"{slug}_summary.json"
                summary: dict[str, object] = {
                    "ok": False,
                    "status": "starting",
                    "keyword": hot_item.metadata.get("category_keyword") or "",
                    "image_url": hot_item.image_url,
                    "final_url": "",
                    "output_dir": str(output_dir.resolve()),
                    "user_data_dir": args.user_data_dir,
                    "profile_directory": args.profile_directory,
                    "subject_count": 0,
                    "selected_subject_index": 0,
                    "subject_runs": [],
                }
                page = await _close_extra_pages(context, page)
                page = await _run_flow_on_page(
                    context=context,
                    page=page,
                    keyword=str(hot_item.metadata.get("category_keyword") or hot_item.title),
                    image_url=hot_item.image_url,
                    output_dir=output_dir,
                    summary=summary,
                    summary_json_file=str(summary_file),
                    pause_for_login_seconds=0.0,
                    subject_index=0,
                    capture_all_subjects=True,
                    max_subjects=args.max_subjects,
                    keep_open_seconds=0.0,
                )
                page = await _close_extra_pages(context, page)
                subject_runs = list(summary.get("subject_runs") or [])
                picked_url = ""
                for subject_run in subject_runs[: max(args.max_subjects, 0)]:
                    html_path = str(subject_run.get("html_path") or "")
                    if html_path:
                        picked_url = str(subject_run.get("final_url") or "")
                    if picked_url:
                        break
                if picked_url:
                    result[hot_item.hot_item_id] = picked_url
                runs.append(
                    {
                        "hot_item_id": hot_item.hot_item_id,
                        "summary_file": str(summary_file),
                        "status": summary.get("status"),
                        "subject_count": summary.get("subject_count"),
                        "subject_runs_count": len(subject_runs),
                        "final_url": summary.get("final_url"),
                    }
                )
                if hot_item is not hot_items[-1]:
                    wait_seconds = random.uniform(args.min_wait_seconds, args.max_wait_seconds)
                    print(
                        json.dumps(
                            {
                                "step": "between_item_wait",
                                "hot_item_id": hot_item.hot_item_id,
                                "wait_seconds": round(wait_seconds, 2),
                            },
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )
                    await asyncio.sleep(wait_seconds)

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
        finally:
            await context.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run ali1688 image search for multiple hot_items in one persistent browser session."
    )
    parser.add_argument("--hot-items-file", required=True)
    parser.add_argument("--output-file", required=True)
    parser.add_argument("--summary-dir", default="./tmp/ali1688_browser_session_runs")
    parser.add_argument("--browser-channel", default="chrome")
    parser.add_argument("--user-data-dir", default=DEFAULT_ALI1688_USER_DATA_DIR)
    parser.add_argument("--profile-directory")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--max-subjects", type=int, default=3)
    parser.add_argument("--slow-mo-ms", type=int, default=0)
    parser.add_argument("--min-wait-seconds", type=float, default=30.0)
    parser.add_argument("--max-wait-seconds", type=float, default=60.0)
    parser.add_argument(
        "--launch-arg",
        action="append",
        default=[],
        help="Extra browser launch arg. Repeatable, e.g. --launch-arg=--start-maximized",
    )
    args = parser.parse_args()
    asyncio.run(_run(args))
    return 0


if __name__ == "__main__":
    sys.exit(main())
