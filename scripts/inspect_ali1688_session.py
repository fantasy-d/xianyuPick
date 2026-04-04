#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from xianyu_tools.ali1688_session import Ali1688SessionConfig, inspect_ali1688_session


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect whether a dedicated ali1688 Chrome profile is ready for search.")
    parser.add_argument("--user-data-dir", required=True)
    parser.add_argument("--browser-channel", default="chrome")
    parser.add_argument("--profile-directory")
    parser.add_argument(
        "--launch-arg",
        action="append",
        default=[],
        help="Extra browser launch arg. Repeatable, e.g. --launch-arg=--start-maximized",
    )
    parser.add_argument("--strict", action="store_true", help="Exit non-zero unless the session state is search.")
    args = parser.parse_args()

    payload = asyncio.run(
        inspect_ali1688_session(
            Ali1688SessionConfig(
                user_data_dir=args.user_data_dir,
                browser_channel=args.browser_channel,
                profile_directory=args.profile_directory,
                launch_args=list(args.launch_arg),
            )
        )
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.strict and payload.get("state") != "search":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
