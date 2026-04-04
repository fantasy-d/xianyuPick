#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from xianyu_tools.xianyu_adapter.state_inspector import inspect_state_file_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a Xianyu login-state JSON file.")
    parser.add_argument("--state-file", required=True, help="Path to Playwright storage_state or extension-exported JSON.")
    parser.add_argument("--strict", action="store_true", help="Exit with code 1 when the state file is not usable.")
    args = parser.parse_args()
    report_json = inspect_state_file_json(args.state_file)
    print(report_json)
    if args.strict:
        from xianyu_tools.xianyu_adapter.state_inspector import inspect_state_file

        report = inspect_state_file(args.state_file)
        return 0 if report.get("is_usable") else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
