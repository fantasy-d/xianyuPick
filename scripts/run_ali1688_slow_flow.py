#!/usr/bin/env python3
import argparse, asyncio, json, html, random, re, sys, logging
from pathlib import Path
from playwright.async_api import async_playwright

# --- 导入统一日志工具 ---
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR / "src"))
from xianyu_tools.logging_util import get_unified_logger
from xianyu_tools.source_adapter import Ali1688SourceAdapter
from xianyu_tools.xianyu_adapter.browser_transport import (
    default_desktop_context_options, default_launch_args
)

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
    if not source_title: return False, "标题为空"
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

async def _try_official_plugin_export(page, logger) -> list[str]:
    """模拟插件点击导出高清图 (您发现的路径)"""
    try:
        btn = page.locator(".download-btn").first
        if await btn.is_visible():
            logger.info("    [Plugin-Export] Plugin button found. Triggering...")
            await btn.click(); await asyncio.sleep(2)
            # 勾选主图
            main_opt = page.get_by_text("主图", exact=False).first
            if await main_opt.is_visible(): await main_opt.click()
            # 导出
            export_btn = page.get_by_text("导出", exact=False).or_(page.get_by_text("生成", exact=False)).first
            if await export_btn.is_visible():
                await export_btn.click(); await asyncio.sleep(2)
                # 从文本框拿链接
                links = await page.evaluate("""
                    () => {
                        const allText = Array.from(document.querySelectorAll('textarea, input')).map(el => el.value).join('\\n');
                        const urls = allText.match(/https?:\\/\\/[^\\s\"']+/g) || [];
                        return [...new Set(urls)].filter(u => u.includes('alicdn.com'));
                    }
                """)
                return [u if u.startswith("http") else "https:" + u for u in links]
    except: pass
    return []

def _parse_captured_api_data(captured_responses: list[dict], logger):
    parsed_result = {"sku_details": [], "images": []}
    for resp in captured_responses:
        data = resp.get("data", {})
        # SKU 提取
        for key in ["skuInfoMap", "skuProps"]:
            info_map = _find_key_recursive(data, key)
            if info_map and not parsed_result["sku_details"] and isinstance(info_map, dict):
                for attr_name, info in info_map.items():
                    parsed_result["sku_details"].append({
                        "attributes": html.unescape(str(attr_name)).replace(">", " - "),
                        "price": info.get("discountPrice") or info.get("price"),
                        "stock": info.get("canBookCount") or info.get("amountOnSale"),
                        "spec_id": info.get("specId") or info.get("skuId"),
                        "source": f"api_{key}"
                    })
        # 图片提取 (API 多路径兼容)
        for key in ["imageList", "images", "mainImages"]:
            image_list = _find_key_recursive(data, key)
            if image_list and isinstance(image_list, list) and not parsed_result["images"]:
                for img in image_list:
                    url = None
                    if isinstance(img, str): url = img
                    elif isinstance(img, dict): url = img.get("originalImageUri") or img.get("fullName") or img.get("url")
                    if url:
                        if url.startswith("//"): url = "https:" + url
                        parsed_result["images"].append(url)
                if parsed_result["images"]: break
    return parsed_result

async def _export_sku_from_detail_page(context, item: dict, output_dir: Path, index: int, logger):
    safe_title = _sanitize_filename(item.get("title") or "item")
    offer_id = item.get("offer_id")
    
    captured = []
    async def on_resp(res):
        try:
            url = res.url.lower()
            if any(k in url for k in ["detail", "sku", "price", "offer", "mtop"]):
                ctype = res.headers.get("content-type", "")
                if "json" in ctype or "javascript" in ctype:
                    text = await res.text()
                    if "(" in text and ")" in text:
                        m = re.search(r"\((.*)\)", text, re.DOTALL); text = m.group(1) if m else text
                    captured.append({"url": res.url, "data": json.loads(text)})
        except: pass

    page = await context.new_page(); page.on("response", on_resp)
    try:
        url = f"https://detail.1688.com/offer/{offer_id}.html"
        logger.info(f"    [Step 2/4] Browser opening: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.evaluate("window.scrollTo(0, 800)"); await asyncio.sleep(3)
        
        # 1. 优先尝试插件路径
        final_images = await _try_official_plugin_export(page, logger)
        
        # 2. API 路径
        parsed = _parse_captured_api_data(captured, logger)
        if not final_images: final_images = parsed["images"]
        
        # 3. DOM 兜底
        if not final_images:
            final_images = await page.evaluate("""
                () => Array.from(document.querySelectorAll('.detail-gallery img'))
                    .map(img => img.src).filter(src => src.includes('alicdn.com'))
                    .map(s => s.startsWith('//') ? 'https:' + s : s).slice(0, 5)
            """)

        if parsed["sku_details"] or final_images:
            logger.info(f"    [Step 4/4] Success! Captured {len(final_images)} images.")
            if parsed["sku_details"]:
                _generate_sku_excel_file(parsed, output_dir / f"{safe_title}_{offer_id}.xlsx")
            return {"status": "success", "images": final_images}
    except Exception as e: logger.error(f"    [Browser Error] Rank {index}: {e}")
    finally: await page.close()
    return {"status": "failed", "images": []}

async def _run(args):
    output_dir = Path(args.output_dir); output_dir.mkdir(parents=True, exist_ok=True)
    logger = get_unified_logger("1688Worker", log_file=args.log_file)
    logger.info("="*60); logger.info(f"1688 SOURCING START")
    
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False, args=default_launch_args())
        context = await browser.new_context(**default_desktop_context_options())
        state_path = Path(args.state_file)
        if state_path.exists():
            state = json.loads(state_path.read_text()); await context.add_cookies(state.get("cookies", []))
        
        from urllib.parse import quote
        search_url = f"https://s.1688.com/youyuan/index.htm?tab=imageSearch&imageAddress={quote(args.image_url)}"
        page = await context.new_page(); await page.goto(search_url, wait_until="domcontentloaded", timeout=60000); await asyncio.sleep(8)
        adapter = Ali1688SourceAdapter(); html_content = await page.content()
        candidates = adapter.search_from_html(html_content, limit=60)
        
        sku_results = []
        for i, c in enumerate(candidates[:args.detail_top_n * 2], start=1):
            if len(sku_results) >= args.detail_top_n: break
            logger.info(f"--- Processing Candidate {i}: {c.title} ---")
            ok, reason = is_relevant(c.title, args.target_keyword)
            item_data = {"offer_id": c.source_item_id, "title": c.title, "item_url": c.item_url, "min_price": c.price, "sku_count": 0, "status": "pending", "drop_reason": reason, "images": []}
            if ok:
                res = await _export_sku_from_detail_page(context, item_data, output_dir, i, logger)
                item_data["status"] = res["status"]; item_data["images"] = res.get("images", [])
                sku_results.append(item_data)
            else:
                logger.info(f"  [Rule Reject] Asking AI...")
                from xianyu_tools.llm_util import ask_llm_relevance
                if ask_llm_relevance(c.title, args.target_keyword, external_logger=logger):
                    res = await _export_sku_from_detail_page(context, item_data, output_dir, i, logger)
                    item_data["status"] = res["status"]; item_data["images"] = res.get("images", []); item_data["drop_reason"] = None
                    sku_results.append(item_data)
                else:
                    item_data["status"] = "dropped"; sku_results.append(item_data)
            
        (output_dir / "summary.json").write_text(json.dumps(sku_results, ensure_ascii=False, indent=2))
        logger.info(f"1688 sourcing finished.")
        await browser.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-url", required=True); parser.add_argument("--output-dir", required=True)
    parser.add_argument("--state-file", default="state/ali1688/storage_state.json")
    parser.add_argument("--detail-top-n", type=int, default=10); parser.add_argument("--target-keyword", required=False); parser.add_argument("--log-file", required=False)
    args = parser.parse_args(); asyncio.run(_run(args))

if __name__ == "__main__":
    main()
