#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from xianyu_tools.reporting import build_xianyu_sourcing_summary
from xianyu_tools.source_adapter import MaishouAdapter
from xianyu_tools.xianyu_adapter import PlaywrightBrowserConfig, PlaywrightXianyuAdapter
from xianyu_tools.xianyu_sourcing import build_xianyu_sourcing_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Xianyu search and source matching in one command.")
    parser.add_argument("--keyword", required=True, help="Search keyword on Xianyu.")
    parser.add_argument("--state-file", required=True, help="Path to Playwright storage_state or extension-exported JSON.")
    parser.add_argument("--xianyu-page", type=int, default=1, help="Xianyu search result page number.")
    parser.add_argument("--xianyu-limit", type=int, default=5, help="Number of Xianyu items to compare.")
    parser.add_argument("--source-limit", type=int, default=10, help="Number of source candidates per Xianyu item.")
    parser.add_argument("--enrich-top-n", type=int, default=3, help="How many source candidates to enrich with detail.")
    parser.add_argument("--browser-channel", default="chrome", help="Browser channel, e.g. chrome or msedge.")
    parser.add_argument("--headful", action="store_true", help="Run browser with UI.")
    parser.add_argument(
        "--launch-arg",
        action="append",
        default=[],
        help="Extra browser launch arg. Repeatable, e.g. --launch-arg=--start-maximized",
    )
    parser.add_argument("--format", choices=("json", "summary"), default="json", help="Output format. Default keeps machine-friendly JSON.")
    args = parser.parse_args()

    xianyu_adapter = PlaywrightXianyuAdapter.from_browser(
        config=PlaywrightBrowserConfig(
            state_file=args.state_file,
            headless=not args.headful,
            browser_channel=args.browser_channel,
            launch_args=list(args.launch_arg),
        )
    )
    bundle = build_xianyu_sourcing_bundle(
        args.keyword,
        xianyu_adapter=xianyu_adapter,
        source_adapter=MaishouAdapter(),
        xianyu_page=args.xianyu_page,
        xianyu_limit=args.xianyu_limit,
        source_limit=args.source_limit,
        enrich_top_n=args.enrich_top_n,
    )
    if args.format == "summary":
        print(json.dumps(build_xianyu_sourcing_summary(bundle), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(bundle, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
