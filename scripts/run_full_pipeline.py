import os, json, asyncio, re, csv, argparse, sys, pymysql
from datetime import datetime
from pathlib import Path

# --- 辅助 ---
async def run_command(cmd):
    process = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()
    # 合并输出用于分析，但优先返回 stdout
    return stdout.decode('utf-8', errors='ignore')

def sanitize_dir_name(name: str) -> str:
    clean = re.sub(r'\s+', '', str(name))
    return re.sub(r'[\\/:*?"<>|]', '_', clean).strip()[:60]

def get_db_conn():
    config = json.load(open("config/database.json"))
    config["cursorclass"] = pymysql.cursors.DictCursor
    return pymysql.connect(**config)

# 提取字符串中真正的业务 JSON 块
def extract_json(text):
    try:
        # 使用正则表达式寻找包含 hot_items 关键词的最长 JSON 块
        import re
        match = re.search(r'(\{.*"hot_items".*\})', text, re.DOTALL)
        if match:
            return match.group(1)
    except: pass
    return text

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--task-id", required=False)
    args = parser.parse_args()
    
    keyword, task_id = args.keyword, args.task_id
    python_path = sys.executable
    
    # 状态初始化
    Task = None
    checkpoint = {}
    root_dir = None

    if task_id:
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
        from web_api.main import Task
        try:
            conn = get_db_conn(); cursor = conn.cursor()
            cursor.execute("SELECT root_dir, checkpoint FROM tasks WHERE id = %s", (task_id,))
            row = cursor.fetchone(); conn.close()
            if row:
                root_dir = Path(row['root_dir'])
                checkpoint = json.loads(row['checkpoint']) if row['checkpoint'] else {}
        except: pass

    if not root_dir:
        root_dir = Path("outputs") / f"{sanitize_dir_name(keyword)}_{datetime.now().strftime('%Y%m%d')}"
    root_dir.mkdir(parents=True, exist_ok=True)

    # --- 1. 闲鱼扫描 (Phase 1) ---
    cur_phase = checkpoint.get("phase", 1)
    xianyu_json_path = root_dir / "xianyu_hot_items.json"
    
    if cur_phase > 1 and xianyu_json_path.exists() and xianyu_json_path.stat().st_size > 100:
        print(f"Checkpoint: Skipping Phase 1 (Xianyu scan completed).", flush=True)
        raw_output = xianyu_json_path.read_text()
    else:
        if Task: Task.update(task_id, msg="闲鱼扫描中...", progress=10)
        # 修复：不再重定向，而是直接捕获输出
        cmd_xianyu = f"export PYTHONPATH=$PYTHONPATH:$(pwd)/src && {python_path} scripts/run_xianyu_hot_items.py --keyword '{keyword}' --state-file xianyu_state.json --max-pages 1 --top-n 10"
        print(f"Executing Phase 1: {cmd_xianyu}", flush=True)
        full_output = await run_command(cmd_xianyu)
        
        # 修复：正则/位置提取纯净 JSON
        raw_output = extract_json(full_output)
        
        # 验证 JSON 有效性后再保存
        try:
            json.loads(raw_output)
            xianyu_json_path.write_text(raw_output)
            if Task: Task.update(task_id, checkpoint=json.dumps({"phase": 2, "processed_rank": 0}))
        except:
            if Task: Task.update(task_id, status="失败", msg="闲鱼扫描结果格式错误（含日志干扰）")
            print(f"Failed to parse JSON from: {full_output}", flush=True)
            return

    try:
        hot_items = json.loads(raw_output).get("hot_items", [])
    except:
        if Task: Task.update(task_id, status="失败", msg="最终解析闲鱼数据失败"); return

    # --- 资产初始化 ---
    db_item_ids = {}
    if task_id:
        conn = get_db_conn(); cursor = conn.cursor()
        cursor.execute("SELECT id, rank_index FROM xianyu_items WHERE task_id = %s", (task_id,))
        db_items = cursor.fetchall()
        if not db_items:
            for i, item in enumerate(hot_items, start=1):
                cursor.execute("INSERT INTO xianyu_items (task_id, rank_index, title, price, image_url, want_count) VALUES (%s, %s, %s, %s, %s, %s)",
                             (task_id, i, item.get('title'), item.get('price'), item.get('image_url'), item.get('want_count')))
                db_item_ids[i] = cursor.lastrowid
            conn.commit()
        else:
            db_item_ids = {row['rank_index']: row['id'] for row in db_items}
        conn.close()

    # --- 2. 1688 深度验证 (Phase 2) ---
    processed_rank = checkpoint.get("processed_rank", 0)
    if Task: Task.update(task_id, msg="1688溯源中...", progress=30)
    
    for i, item in enumerate(hot_items, start=1):
        if i <= processed_rank: continue

        if task_id:
            try:
                _conn = get_db_conn(); _cursor = _conn.cursor(); _cursor.execute("SELECT status FROM tasks WHERE id = %s", (task_id,))
                _status = (_cursor.fetchone() or {}).get('status'); _conn.close()
                if _status == "正在暂停":
                    if Task: Task.update(task_id, status="已暂停", msg=f"在第 {i} 个商品处暂停")
                    return
            except: pass

        if Task: Task.update(task_id, progress=30 + int((i/len(hot_items))*60), msg=f"处理爆款 {i}/{len(hot_items)}...")
        
        item_dir = root_dir / f"Rank_{i}_{sanitize_dir_name(item.get('title', 'item'))}"
        item_dir.mkdir(parents=True, exist_ok=True)
        
        cmd_1688 = f"export PYTHONPATH=$PYTHONPATH:$(pwd)/src && {python_path} scripts/run_ali1688_slow_flow.py --image-url '{item.get('image_url')}' --output-dir '{item_dir}' --detail-top-n 10"
        await run_command(cmd_1688)
        
        if task_id and i in db_item_ids:
            item_db_id = db_item_ids[i]
            conn = get_db_conn(); cursor = conn.cursor()
            cursor.execute("DELETE FROM ali1688_sources WHERE item_id = %s", (item_db_id,))
            from openpyxl import load_workbook
            for f in item_dir.glob("*.xlsx"):
                try:
                    wb = load_workbook(filename=f, read_only=True)
                    ws = wb.active
                    prices = [float(row[1]) for row in ws.iter_rows(min_row=2, max_col=2, values_only=True) if row[1]]
                    if prices:
                        off_id = f.stem.split("_")[-1]
                        cursor.execute("INSERT INTO ali1688_sources (item_id, task_id, title, offer_id, min_price, sku_count, source_url) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                                     (item_db_id, task_id, f.stem.replace(f"_{off_id}", ""), off_id, min(prices), len(prices), f"https://detail.1688.com/offer/{off_id}.html"))
                except: continue
            cursor.execute("UPDATE tasks SET checkpoint = %s WHERE id = %s", (json.dumps({"phase": 2, "processed_rank": i}), task_id))
            conn.commit(); conn.close()

    if Task: Task.update(task_id, status="已完成", progress=100, msg="分析完成")

if __name__ == "__main__":
    asyncio.run(main())
