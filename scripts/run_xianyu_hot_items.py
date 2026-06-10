#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import logging
import re
import os
import requests
from pathlib import Path

# --- 核心：导入统一日志工具 ---
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR / "src"))
from xianyu_tools.logging_util import get_unified_logger
from xianyu_tools.xianyu_adapter import PlaywrightBrowserConfig, PlaywrightXianyuAdapter
from xianyu_tools.xianyu_market_scan import scan_xianyu_market

def detect_input_type(input_str: str) -> str:
    input_str = input_str.strip()
    
    # 1. 识别图片 URL 或本地图片路径
    image_pattern = re.compile(r'\.(jpg|jpeg|png|webp|gif|bmp)(\?.*)?$', re.IGNORECASE)
    if input_str.startswith(('http://', 'https://')) and image_pattern.search(input_str):
        return 'image'
    if input_str.startswith('data:image/'):
        return 'image'
    if os.path.exists(input_str) and image_pattern.search(input_str):
        return 'image'
        
    # 2. 识别闲鱼或淘宝商品链接，或者口令
    url_pattern = re.compile(r'https?://[^\s]+')
    urls = url_pattern.findall(input_str)
    if urls:
        for url in urls:
            if any(domain in url for domain in ('goofish.com', 'tb.cn', 'taobao.com', 'tmall.com', 'goofish')):
                return 'url'
    if re.search(r'【.*】|￥.*￥', input_str):
        return 'url'
        
    return 'keyword'

def extract_item_url_or_id(input_str: str, logger) -> str:
    input_str = input_str.strip()
    url_pattern = re.compile(r'https?://[^\s]+')
    urls = url_pattern.findall(input_str)
    if not urls:
        logger.info(f"[Input-Parser] No URL found in input, treating as ID: {input_str}")
        return input_str
    
    url = urls[0]
    # 处理短网址重定向
    if 'tb.cn' in url or 'm.tb.cn' in url:
        logger.info(f"[Input-Parser] Resolving short link redirect: {url}")
        try:
            resp = requests.head(url, allow_redirects=True, timeout=5)
            url = resp.url
            logger.info(f"[Input-Parser] Short link resolved to: {url}")
        except Exception as e:
            logger.warning(f"[Input-Parser] Failed to resolve redirect for {url}: {e}")
            
    # 从 URL 中提取商品 ID
    match = re.search(r'id=(\d+)', url)
    if match:
        logger.info(f"[Input-Parser] Extracted Item ID {match.group(1)} from URL parameters")
        return match.group(1)
        
    match_path = re.search(r'goofish\.com/item/(\d+)', url)
    if match_path:
        logger.info(f"[Input-Parser] Extracted Item ID {match_path.group(1)} from URL path")
        return match_path.group(1)
        
    logger.info(f"[Input-Parser] Could not extract ID, using resolved URL directly: {url}")
    return url

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
    parser.add_argument("--log-file", required=False)
    args = parser.parse_args()

    # 接入统一日志
    logger = get_unified_logger("XianyuScan", log_file=args.log_file)
    logger.info(f"Starting Xianyu scan for raw input: {args.keyword}")
    
    input_type = detect_input_type(args.keyword)
    logger.info(f"Detected input type: {input_type}")
    
    # --- IMAGE 模式：以图搜图虚拟资产 ---
    if input_type == 'image':
        fn = args.keyword.split('/')[-1].split('?')[0] if '/' in args.keyword else 'image'
        bundle = {
            "hot_items": [
                {
                    "hot_item_id": "img_search",
                    "title": f"以图搜图: 调研任务 ({fn})",
                    "price": 0.0,
                    "want_count": 0,
                    "item_url": "",
                    "image_url": args.keyword
                }
            ]
        }
        sys.stdout.write(json.dumps(bundle, ensure_ascii=False, indent=2))
        sys.stdout.flush()
        logger.info("Image input: mocked single item details emitted successfully")
        return 0

    # --- URL 模式：单品链接抓取 ---
    if input_type == 'url':
        target_id_or_url = extract_item_url_or_id(args.keyword, logger)
        logger.info(f"Resolved single item ID/URL: {target_id_or_url}")
        
        # 链接合法性校验
        if not target_id_or_url or (not target_id_or_url.isdigit() and not target_id_or_url.startswith(('http://', 'https://'))):
            sys.stdout.write(json.dumps({"error": "INVALID_URL", "msg": "解析闲鱼链接失败，未提取到有效宝贝ID"}, ensure_ascii=False))
            sys.stdout.flush()
            logger.error(f"Invalid resolved URL/ID: {target_id_or_url}")
            return 1
        
        scan_success = False
        detail_item = None
        last_exception = None
        
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
                detail_item = adapter.detail(target_id_or_url)
                scan_success = True
                break
            except Exception as e:
                last_exception = e
                if attempt == 0:
                    logger.warning(f"Detail fetch failed on attempt 1: {e}. Opening headful login window for recovery...")
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
                    logger.error(f"Critical error during single item detail fetch: {e}")

        if scan_success and detail_item is not None:
            img_url = detail_item.images[0] if detail_item.images else ""
            bundle = {
                "hot_items": [
                    {
                        "hot_item_id": detail_item.item_id,
                        "title": detail_item.title,
                        "price": detail_item.price,
                        "want_count": detail_item.want_count or 0,
                        "item_url": detail_item.item_url or f"https://www.goofish.com/item?id={detail_item.item_id}",
                        "image_url": img_url
                    }
                ]
            }
            sys.stdout.write(json.dumps(bundle, ensure_ascii=False, indent=2))
            sys.stdout.flush()
            logger.info(f"Single item scan finished successfully for {target_id_or_url}")
            return 0
        
        # 异常细化
        exc_str = str(last_exception) if last_exception else ""
        if "timeout" in exc_str.lower():
            msg = "获取宝贝详情超时，该宝贝可能已下架或需要滑动验证"
        elif "playwright" in exc_str.lower():
            msg = "浏览器驱动初始化失败，请确认 Playwright 环境"
        else:
            msg = f"抓取宝贝详情失败: {exc_str or '宝贝不存在或已被屏蔽'}"
        sys.stdout.write(json.dumps({"error": "DETAIL_FETCH_FAILED", "msg": msg}, ensure_ascii=False))
        sys.stdout.flush()
        return 1

    # --- KEYWORD 模式：原有的分类搜索 ---
    scan_success = False
    bundle = None
    last_exception = None
    
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
            last_exception = e
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

    if scan_success and bundle is not None:
        sys.stdout.write(json.dumps(bundle, ensure_ascii=False, indent=2))
        sys.stdout.flush()
        logger.info(f"Scan finished for {args.keyword}")
        return 0

    exc_str = str(last_exception) if last_exception else ""
    if "timeout" in exc_str.lower():
        msg = "闲鱼市场搜索超时，可能触发滑块验证或网络受限"
    elif "playwright" in exc_str.lower():
        msg = "浏览器驱动初始化失败，请确认 Playwright 环境"
    else:
        msg = f"闲鱼市场扫描失败: {exc_str or '未知异常'}"
    sys.stdout.write(json.dumps({"error": "SCAN_FAILED", "msg": msg}, ensure_ascii=False))
    sys.stdout.flush()
    return 1

if __name__ == "__main__":
    sys.exit(main())
