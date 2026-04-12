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

def _clean_image_url(url: str) -> str:
    """
    1688 专用清洗逻辑：
    1. 必须包含 .jpg_.webp 格式，否则丢弃
    2. 将 .jpg_.webp 及其后续后缀清洗为 .jpg
    """
    if not url or not isinstance(url, str): return ""
    
    # 转换为小写进行匹配，但保留原大小写用于最终 URL
    url_lower = url.lower()
    
    # 核心准则：非 .jpg_.webp 的直接丢弃
    if ".jpg_.webp" not in url_lower:
        return ""

    # 补全协议
    if url.startswith("//"): url = "https:" + url

    # 精准清洗：将 .jpg_.webp 开始直到末尾的部分替换为 .jpg
    # 例如：...image.jpg_.webp_300x300.jpg -> ...image.jpg
    url = re.sub(r'\.jpg_\.webp.*$', '.jpg', url, flags=re.IGNORECASE)
    
    return url

def _sanitize_cookies(cookies):
    """清洗 Cookie 字段，防止 Playwright 报错"""
    allowed_fields = {"name", "value", "url", "domain", "path", "expires", "httpOnly", "secure", "sameSite"}
    clean_list = []
    for c in cookies:
        item = {k: v for k, v in c.items() if k in allowed_fields}
        if "sameSite" in item and item["sameSite"] not in ["Strict", "Lax", "None"]:
            del item["sameSite"]
        clean_list.append(item)
    return clean_list

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

def _parse_captured_api_data(captured_responses: list[dict], logger):
    parsed_result = {"sku_details": [], "images": []}
    for resp in captured_responses:
        data = resp.get("data", {})
        # SKU
        for key in ["skuInfoMap", "skuProps"]:
            info_map = _find_key_recursive(data, key)
            if info_map and not parsed_result["sku_details"] and isinstance(info_map, dict):
                for attr_name, info in info_map.items():
                    parsed_result["sku_details"].append({
                        "attributes": html.unescape(str(attr_name)).replace(">", " - "),
                        "price": info.get("discountPrice") or info.get("price"),
                        "stock": info.get("canBookCount"),
                        "spec_id": info.get("specId")
                    })
        # Images
        for key in ["imageList", "images", "mainImages"]:
            image_list = _find_key_recursive(data, key)
            if image_list and isinstance(image_list, list) and not parsed_result["images"]:
                for img in image_list:
                    u = None
                    if isinstance(img, str): u = img
                    elif isinstance(img, dict): u = img.get("fullPathImageURI") or img.get("originalImageUri") or img.get("url")
                    if u:
                        cleaned = _clean_image_url(str(u))
                        if cleaned: parsed_result["images"].append(cleaned)
                if parsed_result["images"]: break
    return parsed_result

async def _export_sku_from_detail_page(context, item: dict, output_dir: Path, index: int, logger):
    safe_title = _sanitize_filename(item.get("title") or "item")
    offer_id = item.get("offer_id")
    
    captured = []
    async def on_resp(res):
        try:
            if "mtop" in res.url.lower():
                text = await res.text()
                if "(" in text: text = re.search(r"\((.*)\)", text, re.DOTALL).group(1)
                captured.append({"url": res.url, "data": json.loads(text)})
        except: pass

    page = await context.new_page(); page.on("response", on_resp)
    try:
        url = f"https://detail.1688.com/offer/{offer_id}.html"
        logger.info(f"    [Step 2/4] Browser opening: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.evaluate("window.scrollTo(0, 500)"); await asyncio.sleep(5)

        # 精准 DOM 提取
        final_images = await page.evaluate("""
            () => {
                const list = [];
                const gallery = document.querySelector('.module-od-picture-gallery, .detail-gallery, .od-gallery-list-wapper');
                if (gallery) {
                    gallery.querySelectorAll('img').forEach(img => {
                        let src = img.getAttribute('data-lazyload-src') || img.getAttribute('src') || img.src;
                        if (src && src.includes('alicdn.com')) list.push(src);
                    });
                }
                try {
                    const ctx = window.context?.result?.data || {};
                    const imgs = ctx.offerDetail?.imageList || [];
                    imgs.forEach(i => list.push(i.fullPathImageURI || i.originalImageUri || i.imageURI));
                } catch(e) {}
                return [...new Set(list)];
            }
        """)
        
        parsed = _parse_captured_api_data(captured, logger)
        all_found = final_images + parsed["images"]
        clean_final = list(dict.fromkeys([_clean_image_url(u) for u in all_found if u]))
        clean_final = list(filter(None, clean_final))[:9]

        if parsed["sku_details"] or clean_final:
            logger.info(f"    [Step 4/4] Success! Images: {len(clean_final)}")
            if parsed["sku_details"]:
                _generate_sku_excel_file(parsed, output_dir / f"{safe_title}_{offer_id}.xlsx")
            return {"status": "success", "images": clean_final}
    except Exception as e: logger.error(f"    [Browser Error] Rank {index}: {e}")
    finally: await page.close()
    return {"status": "failed", "images": []}

async def _run(args):
    output_dir = Path(args.output_dir); output_dir.mkdir(parents=True, exist_ok=True)
    logger = get_unified_logger("1688Worker", log_file=args.log_file)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=default_launch_args())
        context = await browser.new_context(**default_desktop_context_options())
        state_path = Path(args.state_file)
        if state_path.exists():
            state = json.loads(state_path.read_text())
            # 核心修复：直接使用本地的清洗逻辑，不再引用外部模块
            clean_cookies = _sanitize_cookies(state.get("cookies", []))
            await context.add_cookies(clean_cookies)
            logger.info(f"[Auth] Injected {len(clean_cookies)} sanitized cookies.")

        from urllib.parse import quote
        search_url = f"https://s.1688.com/youyuan/index.htm?tab=imageSearch&imageAddress={quote(args.image_url)}"
        page = await context.new_page(); await page.goto(search_url, wait_until="domcontentloaded", timeout=60000); await asyncio.sleep(8)
        adapter = Ali1688SourceAdapter(); html_content = await page.content()
        candidates = adapter.search_from_html(html_content, limit=60)
        
        sku_results = []
        for i, c in enumerate(candidates[:args.detail_top_n * 2], start=1):
            if len(sku_results) >= args.detail_top_n: break

            # 核心增强：Candidate 之间的硬冷却日志
            if i > 1:
                inter_wait = random.uniform(5.0, 10.0)
                logger.info(f"    [Cooling] Safety pause for {inter_wait:.1f}s before next candidate...")
                await asyncio.sleep(inter_wait)

            item_data = {"offer_id": c.source_item_id, "title": c.title, "item_url": c.item_url, "min_price": c.price, "sku_count": 0, "status": "pending", "drop_reason": None, "images": []}

            res = await _export_sku_from_detail_page(context, item_data, output_dir, i, logger)
            item_data["status"] = res["status"]; item_data["images"] = res.get("images", [])
            sku_results.append(item_data)
            
        (output_dir / "summary.json").write_text(json.dumps(sku_results, ensure_ascii=False, indent=2))
        await browser.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-url", required=True); parser.add_argument("--output-dir", required=True)
    parser.add_argument("--state-file", default="state/ali1688/storage_state.json")
    parser.add_argument("--detail-top-n", type=int, default=10); parser.add_argument("--target-keyword", required=False); parser.add_argument("--log-file", required=False)
    args = parser.parse_args(); asyncio.run(_run(args))

if __name__ == "__main__":
    main()
