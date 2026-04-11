#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import html
from pathlib import Path
import random
import re
from urllib.parse import urlparse
from urllib.request import urlopen

from playwright.async_api import async_playwright
try:
    import pyautogui
except ImportError:
    pyautogui = None

from xianyu_tools.source_adapter import Ali1688SourceAdapter
from xianyu_tools.xianyu_adapter.browser_transport import (
    PlaywrightBrowserTransport,
    default_desktop_context_options,
    default_launch_args,
)

# --- 常量定义 ---
REPO_ROOT = Path(__file__).resolve().parents[1]
DETAIL_URL_PATTERN = re.compile(r"https?://detail\.1688\.com/offer/(?P<offer_id>\d+)\.html")
SUPPORTED_IMAGE_SEARCH_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
REJECTED_IMAGE_SEARCH_SUFFIXES = {".heic", ".heif"}

# --- 核心工具函数 ---

async def _dump_page(page, output_dir: Path, name: str) -> None:
    html_content = await page.content()
    (output_dir / f"{name}.html").write_text(html_content, encoding="utf-8")
    try:
        await page.screenshot(path=str((output_dir / f"{name}.png").resolve()), full_page=False)
    except: pass

def _sanitize_filename(name: str) -> str:
    # 先处理 HTML 实体
    name = html.unescape(name)
    # 替换特殊符号为正常连字符
    name = name.replace(">", "-").replace("&", "and")
    # 移除非法字符
    res = re.sub(r'[\\/:*?"<>|]', '_', name).strip()
    return res[:60]

def _find_key_recursive(obj, target_key):
    if isinstance(obj, dict):
        if target_key in obj: return obj[target_key]
        for v in obj.values():
            res = _find_key_recursive(v, target_key)
            if res: return res
    elif isinstance(obj, list):
        for item in obj:
            res = _find_key_recursive(item, target_key)
            if res: return res
    return None

def _generate_sku_excel_file(parsed_data: dict, output_path: Path):
    try:
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "SKU详情"
        ws.append(["规格名称", "价格", "库存", "SpecId", "数据来源"])
        for sku in parsed_data.get("sku_details", []):
            ws.append([sku.get("attributes"), sku.get("price"), sku.get("stock"), sku.get("spec_id"), sku.get("source")])
        wb.save(output_path)
    except ImportError:
        import csv
        csv_path = output_path.with_suffix(".csv")
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["规格名称", "价格", "库存", "SpecId", "数据来源"])
            for sku in parsed_data.get("sku_details", []):
                writer.writerow([sku.get("attributes"), sku.get("price"), sku.get("stock"), sku.get("spec_id"), sku.get("source")])

def _parse_captured_api_data(captured_responses: list[dict]) -> dict[str, object]:
    parsed_result = {"sku_details": [], "overall_stats": {}, "price_summary": None}
    for resp in captured_responses:
        data = resp.get("data", {})
        
        info_map = _find_key_recursive(data, "skuInfoMap")
        if info_map:
            for attr_name, info in info_map.items():
                # 处理 HTML 实体并格式化
                clean_attr = html.unescape(str(attr_name)).replace(">", " - ")
                parsed_result["sku_details"].append({
                    "attributes": clean_attr,
                    "price": info.get("discountPrice") or info.get("price"),
                    "stock": info.get("canBookCount") or info.get("amountOnSale"),
                    "spec_id": info.get("specId") or info.get("skuId"),
                    "source": "api_skuInfoMap"
                })
            if parsed_result["sku_details"]: break

        spec_list = _find_key_recursive(data, "specList")
        if spec_list and isinstance(spec_list, list) and not parsed_result["sku_details"]:
            for spec in spec_list:
                clean_attr = html.unescape(spec.get("specName") or spec.get("name") or "")
                parsed_result["sku_details"].append({
                    "attributes": clean_attr.replace(">", " - "),
                    "price": spec.get("price") or spec.get("discountPrice"),
                    "stock": spec.get("stock") or spec.get("canBookCount"),
                    "spec_id": spec.get("specId"),
                    "source": "api_specList"
                })
    return parsed_result

def _normalize_image_search_url(image_url: str | None) -> str | None:
    text = str(image_url or "").strip()
    if not text: return None
    if ".heic" in text.lower() and "alicdn.com" in text:
        text = text.split(".heic")[0] + ".heic_640x640.jpg"
    return text

async def _export_sku_from_detail_page(context, item: dict, output_dir: Path, index: int) -> dict:
    wait_time = random.uniform(5.0, 10.0)
    print(f"Anti-risk: Sleeping {wait_time:.2f}s before item {index}...")
    await asyncio.sleep(wait_time)

    result = {"offer_id": item.get("offer_id"), "title": item.get("title"), "status": "failed"}
    captured = []
    
    async def on_resp(res):
        try:
            url = res.url.lower()
            if any(k in url for k in ["detail", "sku", "price", "mtop", "offer"]):
                ctype = res.headers.get("content-type", "")
                if "json" in ctype or "javascript" in ctype:
                    text = await res.text()
                    if "(" in text and ")" in text:
                        m = re.search(r"\((.*)\)", text, re.DOTALL)
                        if m: text = m.group(1)
                    captured.append({"url": res.url, "data": json.loads(text)})
        except: pass

    page = await context.new_page()
    page.on("response", on_resp)
    try:
        print(f"Opening detail {index}: {item.get('item_url')}")
        await page.goto(item.get("item_url"), wait_until="domcontentloaded", timeout=60000)
        await page.mouse.wheel(0, random.randint(200, 500))
        await asyncio.sleep(random.uniform(10.0, 15.0))

        if captured:
            parsed = _parse_captured_api_data(captured)
            safe_title = _sanitize_filename(str(item.get("title") or "item"))
            excel_path = output_dir / f"{safe_title}_{item.get('offer_id')}.xlsx"
            _generate_sku_excel_file(parsed, excel_path)
            
            result["excel_path"] = str(excel_path.resolve())
            result["status"] = "success" if parsed["sku_details"] else "success_no_skus"
            print(f"DONE: {safe_title} ({len(parsed['sku_details'])} SKUs)")
            return result
    except Exception as e:
        result["error"] = str(e)
    finally:
        await page.close()
    return result

async def _run(args):
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False, args=default_launch_args())
        context = await browser.new_context(**default_desktop_context_options())
        
        state_path = Path(args.state_file)
        if state_path.exists():
            state = json.loads(state_path.read_text())
            await context.add_cookies(state.get("cookies", []))

        # 执行图搜
        img_url = _normalize_image_search_url(args.image_url)
        from urllib.parse import quote
        search_url = f"https://s.1688.com/youyuan/index.htm?tab=imageSearch&imageAddress={quote(img_url)}"
        
        print(f"Navigating to image search: {search_url}")
        page = await context.new_page()
        await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
        
        try:
            await page.wait_for_selector(".common-offer-card, [class*='offer-card']", timeout=30000)
        except: pass
        await asyncio.sleep(8)
        
        adapter = Ali1688SourceAdapter()
        html_content = await page.content()
        candidates = adapter.search_from_html(html_content, limit=60)
        top_candidates = candidates[:args.detail_top_n]
        
        print(f"Found {len(candidates)} candidates, processing top {len(top_candidates)}")
        
        sku_results = []
        for i, c in enumerate(top_candidates, start=1):
            res = await _export_sku_from_detail_page(context, {"offer_id": c.source_item_id, "title": c.title, "item_url": c.item_url}, output_dir, i)
            sku_results.append(res)
            
        (output_dir / "summary.json").write_text(json.dumps(sku_results, ensure_ascii=False, indent=2))
        print(f"Pipeline finished. Results in {output_dir}")
        await browser.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-url", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--state-file", default="state/ali1688/storage_state.json")
    parser.add_argument("--detail-top-n", type=int, default=10)
    args = parser.parse_args()
    asyncio.run(_run(args))

if __name__ == "__main__":
    main()
