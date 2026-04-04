#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from xianyu_tools.reporting import build_xianyu_sourcing_summary
from xianyu_tools.source_adapter import MaishouAdapter
from xianyu_tools.xianyu_adapter import PlaywrightBrowserConfig, PlaywrightXianyuAdapter
from xianyu_tools.xianyu_adapter.state_exporter import PlaywrightStateExporter, StateExportConfig
from xianyu_tools.xianyu_adapter.state_inspector import inspect_state_file
from xianyu_tools.xianyu_sourcing import build_xianyu_sourcing_bundle


def main() -> int:
    parser = argparse.ArgumentParser(
        description="End-to-end Xianyu workflow: export state, inspect state, search Xianyu, and match upstream sources."
    )
    parser.add_argument("--keyword", required=True, help="Search keyword on Xianyu.")
    parser.add_argument("--state-file", default="./xianyu_state.json", help="Path to state JSON.")
    parser.add_argument("--browser-channel", default="chrome", help="Browser channel, e.g. chrome or msedge.")
    parser.add_argument("--headless", action="store_true", help="Run browser headless.")
    parser.add_argument(
        "--launch-arg",
        action="append",
        default=[],
        help="Extra browser launch arg. Repeatable, e.g. --launch-arg=--start-maximized",
    )
    parser.add_argument("--cdp-url", help="Attach export step to an already-open Chrome instance over CDP.")
    parser.add_argument("--user-data-dir", help="Chrome user data dir to reuse an existing profile during export.")
    parser.add_argument("--profile-directory", help="Chrome profile directory inside the user data dir, e.g. Default.")
    parser.add_argument("--prompt-for-login", action="store_true", help="Pause for manual login before exporting state.")
    parser.add_argument("--skip-export", action="store_true", help="Use existing state file and skip export.")
    parser.add_argument("--wait-after-login-seconds", type=float, default=0.0, help="Extra wait after login before export.")
    parser.add_argument("--xianyu-page", type=int, default=1, help="Xianyu result page.")
    parser.add_argument("--xianyu-limit", type=int, default=5, help="How many Xianyu items to inspect.")
    parser.add_argument("--source-limit", type=int, default=10, help="How many source candidates per Xianyu item.")
    parser.add_argument("--enrich-top-n", type=int, default=3, help="How many source candidates to enrich with detail.")
    parser.add_argument("--output-file", help="Optional JSON file path for the final sourcing report.")
    parser.add_argument("--summary-output-file", help="Optional JSON file path for the concise summary view.")
    parser.add_argument("--format", choices=("json", "summary"), default="json", help="Console output format. Output file still stores full JSON.")
    args = parser.parse_args()

    state_path = Path(args.state_file)
    if not args.skip_export:
        exporter = PlaywrightStateExporter(
            config=StateExportConfig(
                output_file=str(state_path),
                browser_channel=args.browser_channel,
                headless=args.headless,
                cdp_url=args.cdp_url,
                user_data_dir=args.user_data_dir,
                profile_directory=args.profile_directory,
                prompt_for_login=args.prompt_for_login,
                wait_after_login_seconds=args.wait_after_login_seconds,
            )
        )
        snapshot = exporter.export()
        print(json.dumps({"step": "export", "cookies": len(snapshot.get("cookies", [])), "state_file": str(state_path)}, ensure_ascii=False))
    elif not state_path.exists():
        raise SystemExit(f"state file not found: {state_path}")

    inspection = inspect_state_file(state_path)
    print(json.dumps({"step": "inspect", "inspection": inspection}, ensure_ascii=False))

    xianyu_adapter = PlaywrightXianyuAdapter.from_browser(
        config=PlaywrightBrowserConfig(
            state_file=str(state_path),
            headless=args.headless,
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
    if args.output_file:
        output_path = Path(args.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"step": "write_report", "output_file": args.output_file}, ensure_ascii=False))
    summary = build_xianyu_sourcing_summary(bundle)
    if args.summary_output_file:
        summary_output_path = Path(args.summary_output_file)
        summary_output_path.parent.mkdir(parents=True, exist_ok=True)
        summary_output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"step": "write_summary", "summary_output_file": args.summary_output_file}, ensure_ascii=False))
    processed_count = sum(1 for item in bundle.get("search_items", []) if item.get("source_keyword") or item.get("matched_candidates"))
    print(json.dumps({"step": "done", "processed_items": processed_count, "search_returned_count": bundle["search_returned_count"]}, ensure_ascii=False))
    if args.format == "summary":
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(bundle, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
