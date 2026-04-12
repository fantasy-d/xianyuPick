#!/usr/bin/env python3
import argparse, asyncio, json, html, random, re, sys, logging
from pathlib import Path
from playwright.async_api import async_playwright
from xianyu_tools.source_adapter import Ali1688SourceAdapter
from xianyu_tools.xianyu_adapter.browser_transport import (
    default_desktop_context_options, default_launch_args
)

def get_logger(output_dir, log_file_override=None):
    if log_file_override: log_path = Path(log_file_override)
    else: log_path = Path(output_dir) / "task.log"
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("1688Worker")
    logger.setLevel(logging.INFO)
    if logger.handlers: logger.handlers.clear()
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    fh = logging.FileHandler(log_path, mode='a', encoding='utf-8')
    fh.setFormatter(formatter); logger.addHandler(fh)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(formatter); logger.addHandler(sh)
    return logger

def _sanitize_filename(name: str) -> str:
    name = html.unescape(name).replace(">", "-").replace("&", "and")
    return re.sub(r'[\\/:*?"<>|]', '_', name).strip()[:60]

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

def is_relevant(source_title, search_keyword):
    if not search_keyword: return True, ""
    s_title, t_kw = str(source_title).lower(), str(search_keyword).lower()
    clean_keyword = re.sub(r'\s+', '', t_kw)
    if clean_keyword in s_title: return True, ""
    core_parts = [clean_keyword[:2], clean_keyword[-2:], clean_keyword[1:3]]
    for part in core_parts:
        if len(part) >= 2 and part in s_title: return True, ""
    return False, f"不含关键词 '{clean_keyword}'"

def _generate_sku_excel_file(parsed_data: dict, output_path: Path):
    try:
        from openpyxl import Workbook
        wb = Workbook(); ws = wb.active; ws.title = "SKU详情"
        ws.append(["规格名称", "价格", "库存", "SpecId", "数据来源"])
        for sku in parsed_data.get("sku_details", []):
            ws.append([sku.get("attributes"), sku.get("price"), sku.get("stock"), sku.get("spec_id"), sku.get("source")])
        wb.save(output_path)
    except: pass

def _parse_captured_api_data(captured_responses: list[dict], logger):
    parsed_result = {"sku_details": []}
    for resp in captured_responses:
        url, data = resp.get("url", ""), resp.get("data", {})
        info_map = _find_key_recursive(data, "skuInfoMap")
        if info_map:
            logger.info(f"      [Parser] Hit: 'skuInfoMap' found in API: {url[:60]}...")
            for attr_name, info in info_map.items():
                parsed_result["sku_details"].append({
                    "attributes": html.unescape(str(attr_name)).replace(">", " - "),
                    "price": info.get("discountPrice") or info.get("price"),
                    "stock": info.get("canBookCount") or info.get("amountOnSale"),
                    "spec_id": info.get("specId") or info.get("skuId"),
                    "source": "api_skuInfoMap"
                })
            if parsed_result["sku_details"]: break
    return parsed_result

async def _export_sku_from_detail_page(context, item: dict, output_dir: Path, index: int, logger):
    safe_title = _sanitize_filename(item.get("title") or "item")
    offer_id = item.get("offer_id")
    for ext in [".xlsx", ".csv"]:
        if (output_dir / f"{safe_title}_{offer_id}{ext}").exists():
            logger.info(f"    [Checkpoint] Skip Rank {index}: {offer_id} (Data already exists)")
            return {"status": "success"}
    wait = random.uniform(5.0, 10.0)
    logger.info(f"    [Step 1/4] Rank {index} Cooling down for {wait:.1f}s...")
    await asyncio.sleep(wait)
    captured = []
    async def on_resp(res):
        try:
            url = res.url.lower()
            if any(k in url for k in ["detail", "sku", "price", "offer", "mtop"]):
                ctype = res.headers.get("content-type", "")
                if "json" in ctype or "javascript" in ctype:
                    text = await res.text()
                    if "(" in text and ")" in text:
                        m = re.search(r"\((.*)\)", text, re.DOTALL)
                        if m: text = m.group(1)
                    captured.append({"url": res.url, "data": json.loads(text)})
        except: pass
    page = await context.new_page(); page.on("response", on_resp)
    try:
        url = f"https://detail.1688.com/offer/{offer_id}.html"
        logger.info(f"    [Step 2/4] Browser navigating to detail: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        logger.info(f"    [Step 3/4] Page loaded. Capturing network APIs...")
        await asyncio.sleep(random.uniform(10.0, 14.0))
        parsed = _parse_captured_api_data(captured, logger)
        if parsed["sku_details"]:
            logger.info(f"    [Step 4/4] Success! Extracted {len(parsed['sku_details'])} SKUs.")
            _generate_sku_excel_file(parsed, output_dir / f"{safe_title}_{offer_id}.xlsx")
            return {"status": "success"}
        else:
            logger.warning(f"    [Step 4/4] Failed: No price info found.")
    except Exception as e: logger.error(f"    [Browser Error] Rank {index}: {e}")
    finally: await page.close(); logger.info(f"    [Cleanup] Detail page closed.")
    return {"status": "failed"}

async def _run(args):
    output_dir = Path(args.output_dir); output_dir.mkdir(parents=True, exist_ok=True)
    logger = get_logger(output_dir, args.log_file)
    logger.info("="*60); logger.info(f"1688 SOURCING TASK START"); logger.info(f"Target Keyword: {args.target_keyword}")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False, args=default_launch_args())
        context = await browser.new_context(**default_desktop_context_options())
        state_path = Path(args.state_file)
        if state_path.exists():
            logger.info(f"[Auth] Loading login state from {state_path}")
            state = json.loads(state_path.read_text()); await context.add_cookies(state.get("cookies", []))
        from urllib.parse import quote
        search_url = f"https://s.1688.com/youyuan/index.htm?tab=imageSearch&imageAddress={quote(args.image_url)}"
        logger.info(f"[Search] Navigating to List Page: {search_url}")
        page = await context.new_page(); await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(random.uniform(8.0, 12.0))
        adapter = Ali1688SourceAdapter(); html_content = await page.content()
        candidates = adapter.search_from_html(html_content, limit=60)
        logger.info(f"[Search] HTML Parsing Done. Found {len(candidates)} raw candidates.")
        sku_results = []
        for i, c in enumerate(candidates[:args.detail_top_n * 2], start=1):
            if len(sku_results) >= args.detail_top_n: break
            logger.info(f"--- Processing Candidate {i} ---"); logger.info(f"  Title: {c.title}")
            ok, reason = is_relevant(c.title, args.target_keyword)
            item_data = {"offer_id": c.source_item_id, "title": c.title, "item_url": c.item_url, "min_price": c.price, "sku_count": 0, "status": "pending", "drop_reason": reason}
            if ok:
                res = await _export_sku_from_detail_page(context, item_data, output_dir, i, logger)
                item_data["status"] = res["status"]; sku_results.append(item_data)
            else:
                logger.info(f"  [Rule Reject] Asking AI for mediation...")
                from xianyu_tools.llm_util import ask_llm_relevance
                if ask_llm_relevance(c.title, args.target_keyword, logger=logger): # 透传 logger
                    logger.info("  [AI Rescue] PASS: Semantic match found. Proceeding to detail page.")
                    res = await _export_sku_from_detail_page(context, item_data, output_dir, i, logger)
                    item_data["status"] = res["status"]; item_data["drop_reason"] = None; sku_results.append(item_data)
                else:
                    logger.info(f"  [Final Drop] REJECTED: {reason}"); item_data["status"] = "dropped"; sku_results.append(item_data)
        (output_dir / "summary.json").write_text(json.dumps(sku_results, ensure_ascii=False, indent=2))
        logger.info(f"1688 sourcing sub-task finished."); await browser.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-url", required=True); parser.add_argument("--output-dir", required=True)
    parser.add_argument("--state-file", default="state/ali1688/storage_state.json")
    parser.add_argument("--detail-top-n", type=int, default=10); parser.add_argument("--target-keyword", required=False); parser.add_argument("--log-file", required=False)
    args = parser.parse_args(); asyncio.run(_run(args))

if __name__ == "__main__":
    main()
