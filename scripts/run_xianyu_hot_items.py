#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from xianyu_tools.xianyu_adapter import PlaywrightBrowserConfig, PlaywrightXianyuAdapter
from xianyu_tools.xianyu_market_scan import scan_xianyu_market


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Search a Xianyu category, apply 超赞鱼小铺, and return Top N hot items sorted by want_count."
    )
    parser.add_argument("--keyword", required=True, help="Category keyword to search on Xianyu.")
    parser.add_argument("--state-file", required=True, help="Path to Xianyu browser state JSON.")
    parser.add_argument("--browser-channel", default="chrome", help="Browser channel, e.g. chrome or msedge.")
    parser.add_argument("--headful", action="store_true", help="Run browser with UI.")
    parser.add_argument(
        "--launch-arg",
        action="append",
        default=[],
        help="Extra browser launch arg. Repeatable, e.g. --launch-arg=--start-maximized",
    )
    parser.add_argument("--max-pages", type=int, default=5, help="Maximum number of search pages to fetch.")
    parser.add_argument("--top-n", type=int, default=10, help="How many hot items to keep after sorting by want_count.")
    parser.add_argument(
        "--skip-fish-shop-filter",
        action="store_true",
        help="Skip the 超赞鱼小铺 filter. Default keeps it enabled.",
    )
    args = parser.parse_args()

    adapter = PlaywrightXianyuAdapter.from_browser(
        config=PlaywrightBrowserConfig(
            state_file=args.state_file,
            headless=not args.headful,
            browser_channel=args.browser_channel,
            launch_args=list(args.launch_arg),
        )
    )
    bundle = scan_xianyu_market(
        args.keyword,
        xianyu_adapter=adapter,
        top_n=args.top_n,
        max_pages=args.max_pages,
        require_chaozan_fish_shop=not args.skip_fish_shop_filter,
    )
    print(json.dumps(bundle, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
