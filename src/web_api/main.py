import json, asyncio, os, uuid, pymysql, re, sys, signal, logging
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from xianyu_tools.logging_util import get_unified_logger

# --- 日志配置 ---
logger = get_unified_logger("WebAPI")

app = FastAPI(title="Xianyu-1688 Management System")

# --- 常量 ---
BASE_DIR = Path(__file__).resolve().parents[2]
WEB_DIR = BASE_DIR / "web"
OUTPUTS_DIR = BASE_DIR / "outputs"
CONFIG_PATH = BASE_DIR / "config" / "database.json"

# --- 辅助函数 ---
DB_CONFIG = json.load(open(CONFIG_PATH))
DB_CONFIG["cursorclass"] = pymysql.cursors.DictCursor
def get_db_conn(): return pymysql.connect(**DB_CONFIG)
def sanitize_dir_name(name: str) -> str:
    clean = re.sub(r'\s+', '', str(name))
    return re.sub(r'[\\/:*?"<>|]', '_', clean).strip()[:60]

# --- 任务模型 ---
class Task:
    @staticmethod
    def update(task_id: str, **kwargs):
        if not kwargs: return
        try:
            conn = get_db_conn(); cursor = conn.cursor()
            fields = [f"{k} = %s" for k in kwargs.keys()]
            values = list(kwargs.values()); values.append(task_id)
            cursor.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE id = %s", tuple(values))
            conn.commit(); conn.close()
        except Exception as e:
            logger.error(f"Failed to update task {task_id}: {e}")

    @staticmethod
    def add(keyword: str):
        try:
            task_id, now = str(uuid.uuid4())[:8], datetime.now()
            version = now.strftime("%Y%m%d")
            root_dir = str(OUTPUTS_DIR / f"{sanitize_dir_name(keyword)}_{version}")
            conn = get_db_conn(); cursor = conn.cursor()
            cursor.execute("INSERT INTO tasks (id, keyword, status, progress, msg, created_at, root_dir, version, is_deleted) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0)",
                         (task_id, keyword, "排队中", 0, "等待调度", now, root_dir, version))
            conn.commit(); conn.close()
            logger.info(f"Task added: {keyword} ({task_id})")
            return task_id
        except Exception as e:
            logger.error(f"Failed to add task for {keyword}: {e}")
            return None

# --- 后台 Worker ---
async def pipeline_worker():
    logger.info("Background Worker started.")
    while True:
        task_id, root_dir = None, None
        try:
            conn = get_db_conn(); cursor = conn.cursor()
            cursor.execute("SELECT id, keyword, root_dir FROM tasks WHERE status = '排队中' AND is_deleted = 0 ORDER BY created_at ASC LIMIT 1")
            t_data = cursor.fetchone()
            if not t_data:
                conn.close(); await asyncio.sleep(5); continue
            
            task_id, keyword, root_dir = t_data["id"], t_data["keyword"], t_data["root_dir"]
            cursor.execute("UPDATE tasks SET status = '执行中' WHERE id = %s", (task_id,))
            conn.commit(); conn.close()
            
            logger.info(f"Worker picked up task: {keyword} ({task_id})")
            
            log_file = Path(root_dir) / "task.log"
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 确保使用正确的 Python 解释器
            python_path = sys.executable
            cmd = f"export PYTHONPATH=$PYTHONPATH:{BASE_DIR}/src && {python_path} scripts/run_full_pipeline.py --keyword '{keyword}' --task-id '{task_id}' > '{log_file}' 2>&1"
            
            process = await asyncio.create_subprocess_shell(cmd, cwd=str(BASE_DIR), preexec_fn=os.setsid)
            Task.update(task_id, pgid=os.getpgid(process.pid))
            
            exit_code = await process.wait()
            logger.info(f"Task {task_id} process exited with code {exit_code}")
            
            conn = get_db_conn(); cursor = conn.cursor()
            cursor.execute("SELECT status FROM tasks WHERE id = %s", (task_id,))
            db_status = (cursor.fetchone() or {}).get('status')
            conn.close()

            if db_status == "正在暂停" or exit_code != 0:
                Task.update(task_id, status="已暂停", msg="任务已停止(强制)", pgid=None)
                logger.info(f"Task {task_id} marked as Paused.")
            elif db_status == "执行中" and exit_code == 0:
                Task.update(task_id, status="已完成", progress=100, msg="分析完成", pgid=None)
                logger.info(f"Task {task_id} completed successfully.")
            else:
                Task.update(task_id, pgid=None)

        except Exception as e:
            logger.error(f"Pipeline Worker Error: {e}")
            if task_id: Task.update(task_id, status="失败", msg=str(e), pgid=None)
            await asyncio.sleep(10)
        finally:
            if task_id: running_processes.pop(task_id, None)

running_processes = {} 
@app.on_event("startup")
async def startup():
    asyncio.create_task(pipeline_worker())

# --- 路由 ---
@app.get("/api/tasks")
def list_tasks():
    try:
        conn = get_db_conn(); cursor = conn.cursor()
        cursor.execute("SELECT id, keyword, status, progress, msg, created_at, version FROM tasks WHERE is_deleted = 0 ORDER BY created_at DESC")
        rows = cursor.fetchall(); conn.close()
        for r in rows:
            if isinstance(r['created_at'], datetime): r['created_at'] = r['created_at'].strftime("%Y-%m-%d %H:%M")
        return rows
    except Exception as e:
        logger.error(f"Failed to list tasks: {e}")
        return []

@app.post("/api/tasks")
def create_task(req: dict): 
    tid = Task.add(req["keyword"])
    return {"id": tid} if tid else {"error": "Failed to create task"}

@app.post("/api/tasks/{task_id}/pause")
def pause_task(task_id: str):
    logger.info(f"Pause requested for task: {task_id}")
    conn = get_db_conn(); cursor = conn.cursor()
    cursor.execute("SELECT pgid FROM tasks WHERE id = %s", (task_id,))
    row = cursor.fetchone(); conn.close()
    if row and row['pgid']:
        try:
            os.killpg(int(row['pgid']), signal.SIGKILL)
            Task.update(task_id, status="已暂停", msg="任务已停止", pgid=None)
            logger.info(f"Sent SIGKILL to process group {row['pgid']} for task {task_id}")
        except Exception as e:
            logger.warning(f"Failed to kill process group for task {task_id}: {e}")
            Task.update(task_id, status="已暂停", msg="进程已不存在", pgid=None)
    else:
        Task.update(task_id, status="已暂停", msg="任务取消", pgid=None)
    return {"status": "ok"}

@app.post("/api/tasks/{task_id}/retry")
def retry_task(task_id: str):
    logger.info(f"Retry/Resume requested for task: {task_id}")
    conn = get_db_conn(); cursor = conn.cursor()
    cursor.execute("SELECT keyword, status, created_at FROM tasks WHERE id = %s", (task_id,))
    row = cursor.fetchone()
    if not row: conn.close(); return {"error": "Not found"}
    is_today = row['created_at'].date() == datetime.now().date()
    if row['status'] == '已完成':
        if is_today:
            logger.info(f"Performing same-day overwrite for task {task_id}")
            cursor.execute("DELETE FROM xianyu_items WHERE task_id = %s", (task_id,))
            cursor.execute("DELETE FROM ali1688_sources WHERE task_id = %s", (task_id,))
            cursor.execute("UPDATE tasks SET status = '排队中', msg = '同日重扫中...', progress = 0, pgid = NULL, checkpoint = NULL WHERE id = %s", (task_id,))
            conn.commit(); conn.close()
            return {"status": "ok", "action": "overwritten_today"}
        else:
            logger.info(f"Creating new version for legacy task {task_id}")
            conn.close(); new_id = Task.add(row['keyword'])
            return {"status": "ok", "new_id": new_id, "action": "created_new_day"}
    else:
        logger.info(f"Resuming task {task_id} from checkpoint")
        cursor.execute("UPDATE tasks SET status = '排队中', msg = '准备恢复...', pgid = NULL WHERE id = %s", (task_id,))
        conn.commit(); conn.close(); return {"status": "ok", "action": "resumed"}

@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: str):
    logger.info(f"Logical delete requested for task: {task_id}")
    pause_task(task_id)
    Task.update(task_id, is_deleted=1, pgid=None)
    return {"status": "ok"}

@app.get("/api/task_details/{task_id}")
def get_task_details(task_id: str):
    try:
        conn = get_db_conn(); cursor = conn.cursor()
        cursor.execute("SELECT * FROM xianyu_items WHERE task_id = %s ORDER BY rank_index ASC", (task_id,))
        db_items = cursor.fetchall()
        if db_items:
            details = []
            for item in db_items:
                cursor.execute("SELECT * FROM ali1688_sources WHERE item_id = %s ORDER BY min_price ASC", (item['id'],))
                sources = cursor.fetchall()
                details.append({
                    "rank": item['rank_index'],
                    "xianyu_item": {"db_id": item['id'], "title": item['title'], "price": float(item['price']), "image_url": item['image_url'], "want_count": item['want_count'], "item_url": item['item_url']},
                    "sources": [{
                        "db_id": s['id'], 
                        "title": s['title'], 
                        "min_price": float(s['min_price']), 
                        "sku_count": s['sku_count'], 
                        "url": s['source_url'], 
                        "images": json.loads(s['images'] or "[]"),
                        "drop_reason": s['drop_reason']
                    } for s in sources]
                })
            conn.close(); return {"task_id": task_id, "details": details}
        conn.close(); return {"details": []}
    except Exception as e:
        logger.error(f"Failed to fetch details for task {task_id}: {e}")
        return {"error": str(e)}

@app.get("/api/tasks/{task_id}/logs", response_class=PlainTextResponse)
def get_logs(task_id: str):
    try:
        conn = get_db_conn(); cursor = conn.cursor()
        cursor.execute("SELECT root_dir FROM tasks WHERE id = %s", (task_id,))
        res = cursor.fetchone(); conn.close()
        if not res: return "Task not found"
        log_path = Path(res['root_dir']) / "task.log"
        return log_path.read_text(encoding='utf-8', errors='ignore') if log_path.exists() else "No logs yet"
    except Exception as e:
        logger.error(f"Failed to fetch logs for task {task_id}: {e}")
        return f"Error reading logs: {e}"

@app.get("/api/sys/status")
def system_status(): 
    try:
        conn = get_db_conn(); cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM tasks WHERE status = '执行中' AND is_deleted = 0")
        active_count = cursor.fetchone()['count']; conn.close()
        return {"1688_login": "有效", "active_workers": active_count, "db_type": "MySQL"}
    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        return {"error": str(e)}

app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
