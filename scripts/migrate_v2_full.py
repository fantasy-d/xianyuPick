import json, pymysql, os, re, csv
from pathlib import Path
from openpyxl import load_workbook

import sys
# --- 配置加载 ---
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR / "src"))
from xianyu_tools.config import settings

config = settings.get_database_config()
config["cursorclass"] = pymysql.cursors.DictCursor

def get_db_conn(): return pymysql.connect(**config)

def sanitize_dir_name(name: str) -> str:
    clean = re.sub(r'\s+', '', str(name))
    return re.sub(r'[\\/:*?"<>|]', '_', clean).strip()[:60]

def migrate_all():
    conn = get_db_conn()
    cursor = conn.cursor()
    
    # 获取所有任务
    cursor.execute("SELECT id, keyword, root_dir FROM tasks")
    tasks = cursor.fetchall()
    print(f"Starting FULL migration for {len(tasks)} tasks...")

    for t in tasks:
        task_id = t['id']
        # 路径纠偏逻辑
        root_dir = Path(t['root_dir'])
        if not root_dir.exists():
            # 尝试多种组合：带空格的、不带空格的、相对的、绝对的
            clean_name = sanitize_dir_name(t['keyword']) + "_" + root_dir.name.split('_')[-1]
            options = [BASE_DIR / "outputs" / clean_name, Path(f"outputs/{clean_name}")]
            for opt in options:
                if opt.exists(): root_dir = opt; break
        
        xianyu_json = root_dir / "xianyu_hot_items.json"
        if not xianyu_json.exists():
            print(f"  [Skip] Task {task_id} ({t['keyword']}): data not found at {root_dir}")
            continue

        print(f"\n>>> Processing: {t['keyword']} ({task_id})")
        
        try:
            hot_items = json.loads(xianyu_json.read_text()).get("hot_items", [])
            
            # 1. 清理旧资产
            cursor.execute("DELETE FROM xianyu_items WHERE task_id = %s", (task_id,))
            cursor.execute("DELETE FROM ali1688_sources WHERE task_id = %s", (task_id,))
            
            for i, item in enumerate(hot_items, start=1):
                # 2. 插入闲鱼商品 (带上 item_url)
                cursor.execute("""
                    INSERT INTO xianyu_items (task_id, rank_index, title, price, image_url, want_count, item_url)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (task_id, i, item.get('title'), item.get('price'), item.get('image_url'), item.get('want_count'), item.get('item_url')))
                item_db_id = cursor.lastrowid
                
                # 3. 扫描货源 (xlsx + csv)
                item_dir_options = list(root_dir.glob(f"Rank_{i}_*"))
                if not item_dir_options: continue
                item_dir = item_dir_options[0]
                
                # XLSX 逻辑
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
                
                # CSV 逻辑
                for f in item_dir.glob("*.csv"):
                    if f.name == 'summary.csv': continue
                    try:
                        prices = []
                        with open(f, 'r', encoding='utf-8-sig') as csvfile:
                            reader = csv.DictReader(csvfile)
                            for row in reader:
                                if row.get('价格'): prices.append(float(row['价格']))
                        if prices:
                            off_id = f.stem.split("_")[-1]
                            cursor.execute("INSERT INTO ali1688_sources (item_id, task_id, title, offer_id, min_price, sku_count, source_url) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                                         (item_db_id, task_id, f.stem.replace(f"_{off_id}", ""), off_id, min(prices), len(prices), f"https://detail.1688.com/offer/{off_id}.html"))
                    except: continue
            
            print(f"  - Done: Synced items and sources for {t['keyword']}")
            conn.commit()
        except Exception as e:
            print(f"  [Error]: {e}")
            conn.rollback()

    conn.close()
    print("\nFULL migration completed! All assets are now in DB with URLs.")

if __name__ == "__main__":
    migrate_all()
