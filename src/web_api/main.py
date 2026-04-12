import json, asyncio, os, uuid, pymysql, re, sys
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse, FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Xianyu-1688 Management System")

# --- 常量 ---
BASE_DIR = Path(__file__).resolve().parents[2]
WEB_DIR = BASE_DIR / "web"
OUTPUTS_DIR = BASE_DIR / "outputs"
CONFIG_PATH = BASE_DIR / "config" / "database.json"

# --- 辅助函数 ---
def load_db_config():
    with open(CONFIG_PATH, "r") as f: return json.load(f)

DB_CONFIG = load_db_config()
DB_CONFIG["cursorclass"] = pymysql.cursors.DictCursor

def get_db_conn(): return pymysql.connect(**DB_CONFIG)
def sanitize_dir_name(name: str) -> str:
    clean = re.sub(r'\s+', '', str(name))
    clean = re.sub(r'[\\/:*?"<>|]', '_', clean).strip()
    return clean[:60]

# --- 任务模型 ---
class Task:
    @staticmethod
    def update(task_id: str, **kwargs):
        conn = get_db_conn()
        cursor = conn.cursor()
        updates = [f"{k} = %s" for k in kwargs.keys()]
        params = list(kwargs.values())
        params.append(task_id)
        cursor.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = %s", tuple(params))
        conn.commit()
        conn.close()

    @staticmethod
    def add(keyword: str):
        task_id = str(uuid.uuid4())[:8]
        created_at = datetime.now()
        root_dir = str(OUTPUTS_DIR / f"{sanitize_dir_name(keyword)}_{created_at.strftime('%Y%m%d')}")
        conn = get_db_conn()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO tasks (id, keyword, status, progress, msg, created_at, root_dir) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                     (task_id, keyword, "排队中", 0, "等待调度", created_at, root_dir))
        conn.commit()
        conn.close()
        return task_id

# --- 后台 Worker ---
running_processes = {}
async def pipeline_worker():
    while True:
        task_id, root_dir = None, None
        try:
            conn = get_db_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT id, keyword, root_dir FROM tasks WHERE status = '排队中' ORDER BY created_at ASC LIMIT 1")
            t_data = cursor.fetchone()
            if not t_data:
                conn.close()
                await asyncio.sleep(5)
                continue
            
            task_id, keyword, root_dir = t_data["id"], t_data["keyword"], t_data["root_dir"]
            cursor.execute("UPDATE tasks SET status = '执行中' WHERE id = %s", (task_id,))
            conn.commit()
            conn.close()
            
            log_file = Path(root_dir) / "task.log"
            log_file.parent.mkdir(parents=True, exist_ok=True)
            cmd = f"export PYTHONPATH=$PYTHONPATH:{BASE_DIR}/src && {sys.executable} scripts/run_full_pipeline.py --keyword '{keyword}' --task-id '{task_id}' > '{log_file}' 2>&1"
            process = await asyncio.create_subprocess_shell(cmd, cwd=str(BASE_DIR))
            running_processes[task_id] = process
            await process.wait()
        except Exception as e:
            if task_id: Task.update(task_id, status="失败", msg=str(e))
            await asyncio.sleep(10)
        finally:
            if task_id: running_processes.pop(task_id, None)

@app.on_event("startup")
async def startup(): asyncio.create_task(pipeline_worker())

# --- 核心资产接口 (数据库优先) ---
@app.get("/api/task_details/{task_id}")
def get_task_details(task_id: str):
    conn = get_db_conn()
    cursor = conn.cursor()
    
    # 1. 尝试从数据库读取已入库的资产
    cursor.execute("SELECT * FROM xianyu_items WHERE task_id = %s ORDER BY rank_index ASC", (task_id,))
    db_items = cursor.fetchall()
    
    if db_items:
        details = []
        for item in db_items:
            cursor.execute("SELECT * FROM ali1688_sources WHERE item_id = %s ORDER BY min_price ASC", (item['id'],))
            sources = cursor.fetchall()
            # 格式对齐
            details.append({
                "rank": item['rank_index'],
                "xianyu_item": {
                    "title": item['title'], "price": float(item['price']),
                    "image_url": item['image_url'], "want_count": item['want_count']
                },
                "sources": [{
                    "title": s['title'], "min_price": float(s['min_price']),
                    "sku_count": s['sku_count'], "url": s['source_url']
                } for s in sources]
            })
        conn.close()
        return {"task_id": task_id, "details": details, "source": "db"}

    # 2. 兜底逻辑：从硬盘读取 (支持旧任务)
    cursor.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
    task = cursor.fetchone()
    if not task: conn.close(); return {"error": "Task not found"}
    
    root_dir = Path(task["root_dir"])
    if not root_dir.is_absolute(): root_dir = BASE_DIR / root_dir
    xianyu_json = root_dir / "xianyu_hot_items.json"
    if not xianyu_json.exists():
        alt_dir = BASE_DIR / "outputs" / root_dir.name
        if alt_dir.exists(): xianyu_json = alt_dir / "xianyu_hot_items.json"

    if not xianyu_json.exists():
        conn.close(); return {"task": task, "details": [], "msg": "No data found"}
    
    # (此处省略复杂的 Excel 解析逻辑，为了简洁，旧任务建议重新运行以入库)
    conn.close()
    return {"task": task, "details": [], "msg": "Old task format, please re-run to sync to DB."}

# --- 其他接口 ---
@app.get("/api/tasks")
def list_tasks():
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id, keyword, status, progress, msg, created_at FROM tasks ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    for r in rows:
        if isinstance(r['created_at'], datetime): r['created_at'] = r['created_at'].strftime("%Y-%m-%d %H:%M")
    return rows

@app.post("/api/tasks")
def create_task(req: dict): return {"id": Task.add(req["keyword"])}

@app.get("/api/tasks/{task_id}/logs", response_class=PlainTextResponse)
def get_logs(task_id: str):
    conn = get_db_conn(); cursor = conn.cursor()
    cursor.execute("SELECT root_dir FROM tasks WHERE id = %s", (task_id,))
    res = cursor.fetchone(); conn.close()
    if not res: return "Task not found"
    log_path = Path(res['root_dir']) / "task.log"
    return log_path.read_text() if log_path.exists() else "No logs yet"

@app.post("/api/tasks/{task_id}/retry")
def retry_task(task_id: str):
    conn = get_db_conn(); cursor = conn.cursor()
    cursor.execute("DELETE FROM xianyu_items WHERE task_id = %s", (task_id,))
    cursor.execute("DELETE FROM ali1688_sources WHERE task_id = %s", (task_id,)) # 利用 task_id 清理
    cursor.execute("UPDATE tasks SET status = '排队中', msg = '重新排队...', progress = 0 WHERE id = %s", (task_id,))
    conn.commit(); conn.close()
    return {"status": "ok"}

@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: str):
    conn = get_db_conn(); cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
    cursor.execute("DELETE FROM xianyu_items WHERE task_id = %s", (task_id,))
    cursor.execute("DELETE FROM ali1688_sources WHERE task_id = %s", (task_id,)) # 利用 task_id 清理
    conn.commit(); conn.close(); return {"status": "ok"}

app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
