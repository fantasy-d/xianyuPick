#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a blank ali1688 result-url mapping template from a hot_items JSON file."
    )
    parser.add_argument("--hot-items-file", required=True, help="Path to a JSON file containing hot_items.")
    parser.add_argument(
        "--output-file",
        required=True,
        help="Path to write the hot_item_id -> result_url mapping template.",
    )
    args = parser.parse_args()

    hot_items = _load_hot_items(Path(args.hot_items_file))
    template = {
        row["hot_item_id"]: ""
        for row in hot_items
        if row.get("hot_item_id")
    }
    Path(args.output_file).write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output_file": args.output_file, "count": len(template)}, ensure_ascii=False, indent=2))
    return 0


def _load_hot_items(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        rows = payload.get("hot_items")
    else:
        rows = payload
    if not isinstance(rows, list):
        raise ValueError("hot_items file must contain a list or an object with hot_items")
    return [row for row in rows if isinstance(row, dict)]


if __name__ == "__main__":
    sys.exit(main())
