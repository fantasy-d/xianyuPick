import json, pymysql, re, sys, os
from pathlib import Path

# --- 配置加载 ---
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR / "src"))
from xianyu_tools.llm_util import ask_llm_relevance
from xianyu_tools.config import settings

db_config = settings.get_database_config()
db_config["cursorclass"] = pymysql.cursors.DictCursor

def get_db_conn(): return pymysql.connect(**db_config)

def is_relevant_v3(source_title, search_keyword):
    """三级漏斗判定逻辑"""
    if not search_keyword: return True, ""
    s_title = str(source_title).lower()
    clean_keyword = re.sub(r'\s+', '', str(search_keyword)).lower()
    
    # 1. 规则初筛
    if clean_keyword in s_title: return True, ""
    core_parts = [clean_keyword[:2], clean_keyword[-2:], clean_keyword[1:3]]
    for part in core_parts:
        if len(part) >= 2 and part in s_title: return True, ""
            
    # 2. AI 仲裁
    print(f"    [AI Arbitrating] {source_title} vs {search_keyword}...")
    ai_ok = ask_llm_relevance(source_title, search_keyword)
    if ai_ok is True:
        return True, ""
    elif ai_ok is False:
        return False, "AI判定不相关"
    
    return False, f"不含关键词 '{clean_keyword}'"

def audit_v3():
    conn = get_db_conn()
    cursor = conn.cursor()
    
    # 获取所有货源
    cursor.execute("""
        SELECT s.id, s.title as s_title, t.keyword as search_kw, s.drop_reason
        FROM ali1688_sources s
        JOIN xianyu_items i ON s.item_id = i.id
        JOIN tasks t ON i.task_id = t.id
    """)
    sources = cursor.fetchall()
    print(f"Total {len(sources)} sources to audit with AI Arbitration.")

    reclaimed = 0 # 救活的
    dropped = 0   # 新丢弃的
    
    for s in sources:
        relevant, reason = is_relevant_v3(s['s_title'], s['search_kw'])
        
        current_dropped = bool(s['drop_reason'])
        
        if relevant and current_dropped:
            # AI 救活了之前规则误杀的
            print(f"  [RECLAIMED] {s['s_title']}")
            cursor.execute("UPDATE ali1688_sources SET drop_reason = NULL WHERE id = %s", (s['id'],))
            reclaimed += 1
        elif not relevant and not current_dropped:
            # AI 发现了之前规则漏掉的
            print(f"  [DROPPED] {s['s_title']} -> {reason}")
            cursor.execute("UPDATE ali1688_sources SET drop_reason = %s WHERE id = %s", (reason, s['id']))
            dropped += 1

    conn.commit()
    conn.close()
    print(f"\nAudit V3 Finished!")
    print(f"  - Reclaimed: {reclaimed}")
    print(f"  - Newly Dropped: {dropped}")

if __name__ == "__main__":
    audit_v3()
