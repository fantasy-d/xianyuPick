#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import sys

from xianyu_tools.xianyu_adapter import PlaywrightBrowserConfig, PlaywrightXianyuAdapter


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a live Xianyu search via Playwright transport.")
    parser.add_argument("--keyword", required=True, help="Search keyword.")
    parser.add_argument("--state-file", required=True, help="Path to Playwright storage_state or extension-exported JSON.")
    parser.add_argument("--page", type=int, default=1, help="Search result page number.")
    parser.add_argument("--browser-channel", default="chrome", help="Browser channel, e.g. chrome or msedge.")
    parser.add_argument("--headful", action="store_true", help="Run browser with UI.")
    parser.add_argument(
        "--launch-arg",
        action="append",
        default=[],
        help="Extra browser launch arg. Repeatable, e.g. --launch-arg=--start-maximized",
    )
    parser.add_argument("--include-metadata", action="store_true", help="Include raw metadata payloads in the JSON output.")
    parser.add_argument("--format", choices=("json", "table"), default="json", help="Output format. Default keeps machine-friendly JSON.")
    args = parser.parse_args()

    adapter = PlaywrightXianyuAdapter.from_browser(
        config=PlaywrightBrowserConfig(
            state_file=args.state_file,
            headless=not args.headful,
            browser_channel=args.browser_channel,
            launch_args=list(args.launch_arg),
        )
    )
    items = adapter.search(args.keyword, page=args.page)
    search_items = []
    for item in items:
        row = asdict(item)
        if not args.include_metadata:
            row.pop("metadata", None)
        search_items.append(row)
    output = {
        "search_returned_count": len(search_items),
        "search_items": search_items,
    }
    if args.format == "table":
        print(_render_table(search_items))
    else:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


def _render_table(items: list[dict[str, object]]) -> str:
    headers = ["标题", "价格", "地区", "链接"]
    rows = [headers]
    for item in items:
        rows.append(
            [
                _truncate(str(item.get("title") or ""), 48),
                str(item.get("price") or ""),
                str(item.get("area") or ""),
                str(item.get("item_url") or ""),
            ]
        )

    widths = [max(len(row[i]) for row in rows) for i in range(len(headers))]
    body = "\n".join(" | ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)) for row in rows)
    return f"returned_count: {len(items)}\n{body}"


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


if __name__ == "__main__":
    sys.exit(main())
