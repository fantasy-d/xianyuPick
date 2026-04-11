import os
import json
import asyncio
import re
import csv
from datetime import datetime
from pathlib import Path

async def run_command(cmd):
    print(f"Executing: {cmd}")
    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return stdout.decode()

def sanitize_dir_name(name: str) -> str:
    clean = re.sub(r'[\\/:*?"<>|]', '_', name).strip()
    return clean[:30]

def generate_summary_report(root_dir: Path, keyword: str):
    """
    聚合所有子目录数据，找出每个 Rank 的最优货源并生成结论报表。
    """
    print("\n--- Phase 3: Generating Final Conclusion Report ---")
    xianyu_path = root_dir / "xianyu_hot_items.json"
    if not xianyu_path.exists():
        return

    hot_items = json.loads(xianyu_path.read_text()).get("hot_items", [])
    summary_data = []

    for i, item in enumerate(hot_items, start=1):
        safe_title = sanitize_dir_name(item.get("title", "item"))
        item_dir = root_dir / f"Rank_{i}_{safe_title}"
        
        best_price = 999999.0
        best_source_url = "N/A"
        
        if item_dir.exists():
            # 寻找该目录下所有的解析结果 JSON 或 CSV
            for result_file in item_dir.glob("parsed_*.json"):
                try:
                    data = json.loads(result_file.read_text())
                    p_min = 999999.0
                    if data.get("sku_details"):
                        prices = [float(s["price"]) for s in data["sku_details"] if s.get("price")]
                        if prices: p_min = min(prices)
                    elif data.get("price_summary"):
                        p_min = float(data["price_summary"].get("min_price") or 999999.0)
                    
                    if p_min < best_price:
                        best_price = p_min
                        best_source_url = f"https://detail.1688.com/offer/{result_file.stem.split('_')[-1]}.html"
                except: continue
            
            # 如果没找到 JSON，尝试从 CSV 汇总
            if best_price == 999999.0:
                for csv_file in item_dir.glob("*.csv"):
                    if "结论分析表" in csv_file.name: continue
                    try:
                        with open(csv_file, newline='', encoding='utf-8-sig') as f:
                            reader = csv.DictReader(f)
                            for row in reader:
                                price = float(row.get("价格", 999999.0))
                                if price < best_price:
                                    best_price = price
                                    # 从文件名提取 OfferID: 标题_ID.csv
                                    offer_id = csv_file.stem.split("_")[-1]
                                    best_source_url = f"https://detail.1688.com/offer/{offer_id}.html"
                    except: continue

        if best_price == 999999.0:
            best_price = None

        # 计算利润
        margin = 0
        if best_price:
            margin = item["price"] - best_price - 20 - (item["price"] * 0.006)

        summary_data.append({
            "排名": i,
            "想要人数": item["want_count"],
            "闲鱼售价": item["price"],
            "1688最低成本": best_price if best_price else "未找到",
            "预估利润": round(margin, 2) if best_price else "N/A",
            "建议": "推荐上架" if margin > 50 else "利润一般" if margin > 0 else "亏损/无货源",
            "闲鱼链接": item.get("item_url"),
            "最优货源链接": best_source_url
        })

    # 输出 CSV
    csv_path = root_dir / f"{keyword}_最终结论分析表.csv"
    if summary_data:
        keys = summary_data[0].keys()
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(summary_data)
        print(f"Conclusion report generated: {csv_path.name}")

async def main():
    keyword = "人体工学椅"
    date_str = datetime.now().strftime("%Y%m%d")
    root_dir = Path(f"outputs/{keyword}_{date_str}")
    root_dir.mkdir(parents=True, exist_ok=True)
    
    python_path = "/opt/anaconda3/envs/mytools/bin/python"

    # 1. 闲鱼扫描
    print(f"--- Phase 1: Xianyu Market Scan for '{keyword}' ---")
    xianyu_json = root_dir / "xianyu_hot_items.json"
    cmd_xianyu = f"export PYTHONPATH=$PYTHONPATH:$(pwd)/src && {python_path} scripts/run_xianyu_hot_items.py --keyword '{keyword}' --state-file xianyu_state.json --max-pages 1 --top-n 10"
    output = await run_command(cmd_xianyu)
    xianyu_json.write_text(output)
    
    try:
        hot_items = json.loads(output).get("hot_items", [])
    except:
        print("Failed to parse Xianyu output.")
        return

    # 2. 1688 深度验证
    print(f"--- Phase 2: 1688 Deep Sourcing (Top 10 per item) ---")
    for i, item in enumerate(hot_items, start=1):
        img_url = item.get("image_url")
        safe_title = sanitize_dir_name(item.get("title", "item"))
        item_dir = root_dir / f"Rank_{i}_{safe_title}"
        item_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\nProcessing Xianyu Item {i}/10: {item.get('title')[:50]}...")
        cmd_1688 = (
            f"export PYTHONPATH=$PYTHONPATH:$(pwd)/src && {python_path} scripts/run_ali1688_slow_flow.py "
            f"--image-url '{img_url}' "
            f"--state-file state/ali1688/storage_state.json "
            f"--output-dir '{item_dir}' "
            f"--detail-top-n 10"
        )
        await run_command(cmd_1688)

    # 3. 生成结论报表
    generate_summary_report(root_dir, keyword)
    print(f"\nFull pipeline finished! Root folder: {root_dir.resolve()}")

if __name__ == "__main__":
    asyncio.run(main())
