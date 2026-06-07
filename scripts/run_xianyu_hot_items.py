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
    
    scan_success = False
    bundle = None
    
    for attempt in range(2):
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
            scan_success = True
            break
        except Exception as e:
            if attempt == 0:
                logger.warning(f"Scan failed on attempt 1: {e}. Opening headful login window for recovery...")
                print("\n" + "="*80)
                print("【重要提示】您的闲鱼登录态已失效，正在为您拉起有头浏览器窗口...")
                print("请在弹出的 Chrome 窗口中完成登录/扫码。完成后，请回到此处控制台按【回车键】继续...")
                print("="*80 + "\n")
                
                try:
                    from playwright.sync_api import sync_playwright
                    with sync_playwright() as sp:
                        browser = sp.chromium.launch(headless=False, channel=args.browser_channel)
                        context = browser.new_context()
                        if Path(args.state_file).exists():
                            try:
                                state_data = json.loads(Path(args.state_file).read_text())
                                context.add_cookies(state_data.get("cookies", []))
                            except: pass
                        page = context.new_page()
                        page.goto("https://www.goofish.com/")
                        
                        logger.info("Interactive login window is open. Waiting up to 120s for user login...")
                        logged_in = False
                        for _ in range(120):
                            page.wait_for_timeout(1000)
                            try:
                                cookies = context.cookies()
                                has_token = any(c.get("name") in ("_tb_token_", "cookie2", "lgc") for c in cookies)
                                modal_visible = page.locator(".ant-modal-wrap, .loginCon").first.is_visible()
                                if has_token and not modal_visible:
                                    logged_in = True
                                    break
                            except:
                                pass
                        
                        if logged_in:
                            state = context.storage_state()
                            Path(args.state_file).write_text(json.dumps(state, ensure_ascii=False, indent=2))
                            logger.info(f"Successfully exported fresh Xianyu login state to {args.state_file}")
                        else:
                            logger.warning("Login detection timed out or failed.")
                        browser.close()
                except Exception as le:
                    logger.error(f"Failed to run interactive login helper: {le}")
            else:
                logger.error(f"Critical error during scan: {e}")
                return 1

    if scan_success and bundle is not None:
        sys.stdout.write(json.dumps(bundle, ensure_ascii=False, indent=2))
        sys.stdout.flush()
        logger.info(f"Scan finished for {args.keyword}")
        return 0
    return 1

if __name__ == "__main__":
    sys.exit(main())
