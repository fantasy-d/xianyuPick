#!/usr/bin/env python3
import argparse, asyncio, json, html, random, re, sys
from pathlib import Path
from playwright.async_api import async_playwright
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

def is_relevant(source_title, target_keyword):
    if not target_keyword: return True, ""
    s_title, t_kw = str(source_title).lower(), str(target_keyword).lower()
    clean_target = re.sub(r'[【】\[\]（）() ]', '', t_kw)
    core_chars = clean_target[:6] 
    matches = sum(1 for char in core_chars if char in s_title)
    if matches >= 2: return True, ""
    category_keywords = ["椅", "桌", "蚊帐", "纸", "垫", "柜", "包", "灯", "架", "机"]
    for word in category_keywords:
        if word in clean_target and word in s_title: return True, ""
    return False, "标题不匹配"

def _generate_sku_excel_file(parsed_data: dict, output_path: Path):
    try:
        from openpyxl import Workbook
        wb = Workbook(); ws = wb.active; ws.title = "SKU详情"
        ws.append(["规格名称", "价格", "库存", "SpecId", "数据来源"])
        for sku in parsed_data.get("sku_details", []):
            ws.append([sku.get("attributes"), sku.get("price"), sku.get("stock"), sku.get("spec_id"), sku.get("source")])
        wb.save(output_path)
    except: pass

def _parse_captured_api_data(captured_responses: list[dict]):
    parsed_result = {"sku_details": []}
    for resp in captured_responses:
        data = resp.get("data", {})
        info_map = _find_key_recursive(data, "skuInfoMap")
        if info_map:
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

async def _export_sku_from_detail_page(context, item: dict, output_dir: Path, index: int):
    safe_title = _sanitize_filename(item.get("title") or "item")
    offer_id = item.get("offer_id")
    for ext in [".xlsx", ".csv"]:
        if (output_dir / f"{safe_title}_{offer_id}{ext}").exists():
            return {"status": "success", "msg": "Checkpoint found"}

    await asyncio.sleep(random.uniform(5.0, 10.0))
    captured = []
    async def on_resp(res):
        try:
            url = res.url.lower()
            if any(k in url for k in ["detail", "sku", "price", "offer"]):
                ctype = res.headers.get("content-type", "")
                if "json" in ctype or "javascript" in ctype:
                    text = await res.text()
                    if "(" in text and ")" in text:
                        m = re.search(r"\((.*)\)", text, re.DOTALL)
                        if m: text = m.group(1)
                    captured.append({"data": json.loads(text)})
        except: pass

    page = await context.new_page(); page.on("response", on_resp)
    try:
        print(f"  - Opening detail {index}: {item.get('item_url')}")
        await page.goto(item.get('item_url'), wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(random.uniform(10.0, 15.0))
        parsed = _parse_captured_api_data(captured)
        if parsed["sku_details"]:
            _generate_sku_excel_file(parsed, output_dir / f"{safe_title}_{offer_id}.xlsx")
            return {"status": "success"}
    except Exception as e: print(f"  [Error] {offer_id}: {e}")
    finally: await page.close()
    return {"status": "failed"}

async def _run(args):
    output_dir = Path(args.output_dir); output_dir.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False, args=default_launch_args())
        context = await browser.new_context(**default_desktop_context_options())
        state_path = Path(args.state_file)
        if state_path.exists():
            state = json.loads(state_path.read_text())
            await context.add_cookies(state.get("cookies", []))

        from urllib.parse import quote
        search_url = f"https://s.1688.com/youyuan/index.htm?tab=imageSearch&imageAddress={quote(args.image_url)}"
        page = await context.new_page(); await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(random.uniform(10.0, 15.0))
        
        adapter = Ali1688SourceAdapter()
        candidates = adapter.search_from_html(await page.content(), limit=60)
        
        sku_results = []
        # 处理前 N 个结果
        for i, c in enumerate(candidates[:args.detail_top_n * 2], start=1):
            if len(sku_results) >= args.detail_top_n: break
            
            # 相关性判断
            ok, reason = is_relevant(c.title, args.target_keyword)
            
            item_data = {
                "offer_id": c.source_item_id, 
                "title": c.title, 
                "item_url": c.item_url, 
                "min_price": c.price, # 列表页的参考价
                "sku_count": 0,
                "status": "pending",
                "drop_reason": reason
            }

            if ok:
                # 相关性高，抓取详情
                res = await _export_sku_from_detail_page(context, item_data, output_dir, i)
                item_data["status"] = res["status"]
                sku_results.append(item_data)
            else:
                # 相关性低，直接记录基本信息并注明原因
                print(f"  [Drop] Skipping detail for {c.title}: {reason}")
                item_data["status"] = "dropped"
                sku_results.append(item_data)
            
        (output_dir / "summary.json").write_text(json.dumps(sku_results, ensure_ascii=False, indent=2))
        await browser.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-url", required=True); parser.add_argument("--output-dir", required=True)
    parser.add_argument("--state-file", default="state/ali1688/storage_state.json")
    parser.add_argument("--detail-top-n", type=int, default=10); parser.add_argument("--target-keyword", required=False)
    args = parser.parse_args(); asyncio.run(_run(args))

if __name__ == "__main__":
    main()
