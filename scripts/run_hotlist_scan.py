#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import sys

from xianyu_tools.hotlist_adapter import FixtureHotlistAdapter


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan hot-selling items from the configured hotlist source.")
    parser.add_argument("--fixture-file", required=True, help="Path to a fixture JSON file for hot_items.")
    parser.add_argument("--platform", help="Optional platform filter.")
    parser.add_argument("--limit", type=int, default=20, help="Maximum number of hot items to return.")
    args = parser.parse_args()

    adapter = FixtureHotlistAdapter.from_file(args.fixture_file)
    hot_items = adapter.list_hot_items(platform=args.platform, limit=args.limit)
    print(
        json.dumps(
            {"hot_items": [asdict(item) for item in hot_items]},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
