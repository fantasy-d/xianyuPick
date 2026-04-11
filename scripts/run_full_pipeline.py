import os
import json
import asyncio
import re
import csv
import argparse
from datetime import datetime
from pathlib import Path

async def run_command(cmd):
    print(f"Executing: {cmd}", flush=True)
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
    """ 聚合逻辑：确保只扫描当前任务的 root_dir """
    print(f"\n--- Phase 3: Generating Report for {keyword} ---", flush=True)
    xianyu_path = root_dir / "xianyu_hot_items.json"
    if not xianyu_path.exists(): return

    try:
        hot_items = json.loads(xianyu_path.read_text()).get("hot_items", [])
    except: return
    
    summary_data = []
    for i, item in enumerate(hot_items, start=1):
        safe_title = sanitize_dir_name(item.get("title", "item"))
        item_dir = root_dir / f"Rank_{i}_{safe_title}"
        
        best_price = 999999.0
        best_source_url = "N/A"
        
        if item_dir.exists():
            # 扫描解析出的 CSV
            for csv_file in item_dir.glob("*.csv"):
                try:
                    with open(csv_file, newline='', encoding='utf-8-sig') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            p = float(row.get("价格") or 999999.0)
                            if p < best_price:
                                best_price = p
                                offer_id = csv_file.stem.split("_")[-1]
                                best_source_url = f"https://detail.1688.com/offer/{offer_id}.html"
                except: continue

        best_price_val = best_price if best_price != 999999.0 else None
        margin = 0
        if best_price_val:
            margin = item["price"] - best_price_val - 20 - (item["price"] * 0.006)

        summary_data.append({
            "排名": i, "想要人数": item["want_count"], "闲鱼售价": item["price"],
            "1688最低成本": best_price_val if best_price_val else "未找到",
            "预估利润": round(margin, 2) if best_price_val else "N/A",
            "建议": "推荐上架" if margin > 50 else "利润一般" if margin > 0 else "亏损/无货源",
            "闲鱼链接": item.get("item_url"), "最优货源链接": best_source_url
        })

    csv_path = root_dir / f"{keyword}_最终结论分析表.csv"
    if summary_data:
        keys = summary_data[0].keys()
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(summary_data)

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--task-id", required=False) # 新增 task-id 支持
    args = parser.parse_args()
    
    keyword = args.keyword
    task_id = args.task_id
    date_str = datetime.now().strftime("%Y%m%d")
    root_dir = Path(f"outputs/{keyword}_{date_str}")
    root_dir.mkdir(parents=True, exist_ok=True)
    
    python_path = "/opt/anaconda3/envs/mytools/bin/python"

    # 1. 闲鱼扫描
    # ... (Phase 1 保持不变)
    print(f"--- Phase 1: Scanning '{keyword}' ---", flush=True)
    xianyu_json = root_dir / "xianyu_hot_items.json"
    if xianyu_json.exists() and xianyu_json.stat().st_size > 500:
        print(f"Checkpoint: Xianyu data exists. Skipping scan.", flush=True)
        try:
            with open(xianyu_json) as f: output = f.read()
        except: output = ""
    else:
        cmd_xianyu = f"export PYTHONPATH=$PYTHONPATH:$(pwd)/src && {python_path} scripts/run_xianyu_hot_items.py --keyword '{keyword}' --state-file xianyu_state.json --max-pages 1 --top-n 10"
        output = await run_command(cmd_xianyu)
        xianyu_json.write_text(output)
    
    try:
        hot_items = json.loads(output).get("hot_items", [])
    except: return

    # 2. 1688 深度验证
    print(f"--- Phase 2: Sourcing Top 10 for '{keyword}' ---", flush=True)
    import random
    
    for i, item in enumerate(hot_items, start=1):
        # --- 核心：Checkpoint 暂停自检 ---
        if task_id:
            try:
                # 导入 pymysql 动态查询
                import pymysql
                db_config = json.load(open("config/database.json"))
                conn = pymysql.connect(**db_config)
                cursor = conn.cursor()
                cursor.execute("SELECT status FROM tasks WHERE id = %s", (task_id,))
                row = cursor.fetchone()
                conn.close()
                if row and row[0] == "正在暂停":
                    print(f"\n[Checkpoint] Pause signal detected for task {task_id}. Graceful exit.", flush=True)
                    return # 安全退出
            except Exception as e:
                print(f"Pause check failed: {e}", flush=True)
        # -----------------------------

        if i > 1:
            task_gap = random.uniform(5.0, 10.0)
            print(f"Waiting {task_gap:.2f}s before next item task...", flush=True)
            await asyncio.sleep(task_gap)

        img_url = item.get("image_url")
        safe_title = sanitize_dir_name(item.get("title", "item"))
        item_dir = root_dir / f"Rank_{i}_{safe_title}"
        item_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\nProcessing {keyword} Rank {i}/10...", flush=True)
        cmd_1688 = (
            f"export PYTHONPATH=$PYTHONPATH:$(pwd)/src && {python_path} scripts/run_ali1688_slow_flow.py "
            f"--image-url '{img_url}' --state-file state/ali1688/storage_state.json "
            f"--output-dir '{item_dir}' --detail-top-n 10"
        )
        await run_command(cmd_1688)

    # 3. 汇总
    generate_summary_report(root_dir, keyword)
    
    # 额外：生成多 Sheet Excel
    cmd_excel = f"export PYTHONPATH=$PYTHONPATH:$(pwd)/src && {python_path} scripts/export_final_excel_v3.py"
    # 我们需要微调 export_final_excel_v3.py 同样支持传参，目前先这样
    await run_command(cmd_excel)

if __name__ == "__main__":
    asyncio.run(main())
