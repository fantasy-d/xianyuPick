import json, pymysql, re
from pathlib import Path

# --- 配置加载 ---
BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = BASE_DIR / "config" / "database.json"
config = json.load(open(CONFIG_PATH))
config["cursorclass"] = pymysql.cursors.DictCursor

def get_db_conn(): return pymysql.connect(**config)

def is_relevant(source_title, search_keyword):
    """采用最新的关键词比对逻辑"""
    if not search_keyword: return True, ""
    s_title = str(source_title).lower()
    clean_keyword = re.sub(r'\s+', '', str(search_keyword)).lower()
    
    if clean_keyword in s_title: return True, ""
    
    core_parts = [clean_keyword[:2], clean_keyword[-2:], clean_keyword[1:3]]
    for part in core_parts:
        if len(part) >= 2 and part in s_title: return True, ""
            
    return False, f"不含关键词 '{clean_keyword}'"

def clean_v2():
    conn = get_db_conn()
    cursor = conn.cursor()
    
    # 1. 获取所有货源、所属任务的关键词
    cursor.execute("""
        SELECT s.id, s.title as s_title, t.keyword as search_kw
        FROM ali1688_sources s
        JOIN xianyu_items i ON s.item_id = i.id
        JOIN tasks t ON i.task_id = t.id
        WHERE s.drop_reason IS NULL OR s.drop_reason = ""
    """)
    sources = cursor.fetchall()
    print(f"Auditing {len(sources)} sources based on TASK KEYWORDS...")

    drop_count = 0
    for s in sources:
        relevant, reason = is_relevant(s['s_title'], s['search_kw'])
        if not relevant:
            cursor.execute("UPDATE ali1688_sources SET drop_reason = %s WHERE id = %s", (reason, s['id']))
            drop_count += 1

    conn.commit()
    conn.close()
    print(f"\nAudit V2 Completed! Total {drop_count} sources marked as dropped.")

if __name__ == "__main__":
    clean_v2()
