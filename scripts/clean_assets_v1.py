import json, pymysql, re
from pathlib import Path

# --- 配置加载 ---
BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = BASE_DIR / "config" / "database.json"
config = json.load(open(CONFIG_PATH))
config["cursorclass"] = pymysql.cursors.DictCursor

def get_db_conn(): return pymysql.connect(**config)

def is_relevant(source_title, target_keyword):
    if not target_keyword: return True, ""
    s_title, t_kw = str(source_title).lower(), str(target_keyword).lower()
    clean_target = re.sub(r'[【】\[\]（）() ]', '', t_kw)
    core_chars = clean_target[:6] 
    matches = sum(1 for char in core_chars if char in s_title)
    if matches >= 2: return True, ""
    # 品类词兜底
    category_keywords = ["椅", "桌", "蚊帐", "纸", "垫", "柜", "包", "灯", "架", "机"]
    for word in category_keywords:
        if word in clean_target and word in s_title: return True, ""
    return False, "标题不匹配"

def clean_all():
    conn = get_db_conn()
    cursor = conn.cursor()
    
    # 1. 获取所有货源及其对应的商品标题
    cursor.execute("""
        SELECT s.id, s.title as s_title, i.title as t_title 
        FROM ali1688_sources s
        JOIN xianyu_items i ON s.item_id = i.id
        WHERE s.drop_reason IS NULL OR s.drop_reason = ""
    """)
    sources = cursor.fetchall()
    print(f"Checking {len(sources)} sources for relevance...")

    count = 0
    for s in sources:
        relevant, reason = is_relevant(s['s_title'], s['t_title'])
        if not relevant:
            # 标记为已丢弃
            cursor.execute("UPDATE ali1688_sources SET drop_reason = %s WHERE id = %s", (reason, s['id']))
            count += 1
            if count % 10 == 0: print(f"  Processed {count} drops...")

    conn.commit()
    conn.close()
    print(f"\nAudit completed! Total {count} sources marked as 'dropped'.")

if __name__ == "__main__":
    clean_all()
