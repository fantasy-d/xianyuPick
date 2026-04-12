import os, json, asyncio, re, csv, argparse, sys, pymysql
from datetime import datetime
from pathlib import Path

# --- 辅助 ---
async def run_command(cmd):
    process = await asyncio.create_subprocess_shell(cmd)
    await process.wait()

def sanitize_dir_name(name: str) -> str:
    clean = re.sub(r'\s+', '', str(name))
    return re.sub(r'[\\/:*?"<>|]', '_', clean).strip()[:60]

# --- 数据库操作 ---
def get_db_conn():
    config = json.load(open("config/database.json"))
    config["cursorclass"] = pymysql.cursors.DictCursor
    return pymysql.connect(**config)

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--task-id", required=False)
    args = parser.parse_args()
    
    keyword, task_id = args.keyword, args.task_id
    root_dir = Path("outputs") / f"{sanitize_dir_name(keyword)}_{datetime.now().strftime('%Y%m%d')}"
    root_dir.mkdir(parents=True, exist_ok=True)
    python_path = sys.executable
    
    # 导入 Task
    Task = None
    if task_id:
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
        from web_api.main import Task

    # --- 1. 闲鱼扫描 ---
    if Task: Task.update(task_id, msg="闲鱼扫描中...", progress=10)
    xianyu_json_path = root_dir / "xianyu_hot_items.json"
    if not xianyu_json_path.exists():
        cmd_xianyu = f"export PYTHONPATH=$PYTHONPATH:$(pwd)/src && {python_path} scripts/run_xianyu_hot_items.py --keyword '{keyword}' --max-pages 1 --top-n 10 > '{xianyu_json_path}'"
        await run_command(cmd_xianyu)
    
    try:
        hot_items = json.loads(xianyu_json_path.read_text()).get("hot_items", [])
    except:
        if Task: Task.update(task_id, status="失败", msg="解析闲鱼数据失败"); return

    # --- 资产入库：闲鱼商品 ---
    db_item_ids = {} # 记录数据库生成的 ID，供 sources 使用
    if task_id:
        conn = get_db_conn(); cursor = conn.cursor()
        # 先清空该任务旧数据
        cursor.execute("DELETE FROM xianyu_items WHERE task_id = %s", (task_id,))
        for i, item in enumerate(hot_items, start=1):
            cursor.execute("""
                INSERT INTO xianyu_items (task_id, rank_index, title, price, image_url, want_count)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (task_id, i, item.get('title'), item.get('price'), item.get('image_url'), item.get('want_count')))
            db_item_ids[i] = cursor.lastrowid
        conn.commit(); conn.close()

    # --- 2. 1688 深度验证 ---
    if Task: Task.update(task_id, msg="1688溯源中...", progress=30)
    for i, item in enumerate(hot_items, start=1):
        item_dir = root_dir / f"Rank_{i}_{sanitize_dir_name(item.get('title', 'item'))}"
        if Task: Task.update(task_id, progress=30 + int((i/len(hot_items))*60), msg=f"处理爆款 {i}/{len(hot_items)}...")
        
        # 执行抓取
        if not (item_dir / "summary.json").exists():
            cmd_1688 = f"export PYTHONPATH=$PYTHONPATH:$(pwd)/src && {python_path} scripts/run_ali1688_slow_flow.py --image-url '{item.get('image_url')}' --output-dir '{item_dir}' --detail-top-n 10"
            await run_command(cmd_1688)
        
        # --- 资产入库：1688 货源 ---
        if task_id and i in db_item_ids:
            item_db_id = db_item_ids[i]
            conn = get_db_conn(); cursor = conn.cursor()
            cursor.execute("DELETE FROM ali1688_sources WHERE item_id = %s", (item_db_id,))
            
            # 扫描 xlsx 文件读取价格 (复用 main.py 逻辑)
            from openpyxl import load_workbook
            for f in item_dir.glob("*.xlsx"):
                try:
                    wb = load_workbook(filename=f, read_only=True)
                    ws = wb.active
                    prices = [float(row[1]) for row in ws.iter_rows(min_row=2, max_col=2, values_only=True) if row[1]]
                    if prices:
                        offer_id = f.stem.split("_")[-1]
                        cursor.execute("""
                            INSERT INTO ali1688_sources (item_id, task_id, title, offer_id, min_price, sku_count, source_url)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (item_db_id, task_id, f.stem.replace(f"_{offer_id}", ""), offer_id, min(prices), len(prices), f"https://detail.1688.com/offer/{offer_id}.html"))
                except: continue
            conn.commit(); conn.close()

    # --- 3. 完成 ---
    if Task: Task.update(task_id, status="已完成", progress=100, msg="资产已全数入库")

if __name__ == "__main__":
    asyncio.run(main())
