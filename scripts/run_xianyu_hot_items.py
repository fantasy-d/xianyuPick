#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import logging
from pathlib import Path

# --- 核心：导入统一日志工具 ---
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR / "src"))
from xianyu_tools.logging_util import get_unified_logger
from xianyu_tools.xianyu_adapter import PlaywrightBrowserConfig, PlaywrightXianyuAdapter
from xianyu_tools.xianyu_market_scan import scan_xianyu_market

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Search a Xianyu category, apply 超赞鱼小铺, and return Top N hot items."
    )
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--state-file", required=True)
    parser.add_argument("--browser-channel", default="chrome")
    parser.add_argument("--headful", action="store_true")
    parser.add_argument("--launch-arg", action="append", default=[])
    parser.add_argument("--max-pages", type=int, default=5)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--skip-fish-shop-filter", action="store_true")
    parser.add_argument("--log-file", required=False) # 补全参数
    args = parser.parse_args()

    # 接入统一日志
    logger = get_unified_logger("XianyuScan", log_file=args.log_file)
    logger.info(f"Starting Xianyu scan for: {args.keyword}")
    
    try:
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
        
        # 核心：将 JSON 结果打印到 stdout，且不带任何 logger 前缀
        sys.stdout.write(json.dumps(bundle, ensure_ascii=False, indent=2))
        sys.stdout.flush()
        
        logger.info(f"Scan finished for {args.keyword}")
        return 0
    except Exception as e:
        logger.error(f"Critical error during scan: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
