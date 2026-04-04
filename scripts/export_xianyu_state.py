#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from xianyu_tools.xianyu_adapter.state_exporter import PlaywrightStateExporter, StateExportConfig


def main() -> int:
    parser = argparse.ArgumentParser(description="Export xianyu_state.json using Playwright, mirroring the Chrome extension snapshot logic.")
    parser.add_argument("--output-file", required=True, help="Where to write xianyu_state.json.")
    parser.add_argument("--state-file", help="Optional existing state JSON to preload before export.")
    parser.add_argument("--browser-channel", default="chrome", help="Browser channel, e.g. chrome or msedge.")
    parser.add_argument("--headless", action="store_true", help="Run headless. Default is headful for manual login.")
    parser.add_argument(
        "--launch-arg",
        action="append",
        default=[],
        help="Extra browser launch arg. Repeatable, e.g. --launch-arg=--start-maximized",
    )
    parser.add_argument("--cdp-url", help="Attach to an already-open Chrome/Chromium instance over CDP, e.g. http://127.0.0.1:9222.")
    parser.add_argument("--user-data-dir", help="Launch Chrome against an existing user data dir to reuse a real profile.")
    parser.add_argument("--profile-directory", help="Chrome profile directory inside the user data dir, e.g. Default or Profile 1.")
    parser.add_argument("--page-url", default="https://www.goofish.com/", help="Page to open before exporting.")
    parser.add_argument("--wait-after-login-seconds", type=float, default=0.0, help="Extra wait after login before capture.")
    parser.add_argument("--prompt-for-login", action="store_true", help="Pause for manual login, then export after Enter.")
    args = parser.parse_args()

    exporter = PlaywrightStateExporter(
        config=StateExportConfig(
            output_file=args.output_file,
            state_file=args.state_file,
            browser_channel=args.browser_channel,
            headless=args.headless,
            launch_args=list(args.launch_arg),
            cdp_url=args.cdp_url,
            user_data_dir=args.user_data_dir,
            profile_directory=args.profile_directory,
            page_url=args.page_url,
            wait_after_login_seconds=args.wait_after_login_seconds,
            prompt_for_login=args.prompt_for_login,
        )
    )
    snapshot = exporter.export()
    print(f"exported xianyu state to {args.output_file}")
    print(f"cookies: {len(snapshot.get('cookies', []))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
