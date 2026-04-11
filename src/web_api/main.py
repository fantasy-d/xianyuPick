import json
import asyncio
import os
import uuid
import pymysql
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Xianyu-1688 Management System")

BASE_DIR = Path(__file__).resolve().parents[2]
WEB_DIR = BASE_DIR / "web"
OUTPUTS_DIR = BASE_DIR / "outputs"
CONFIG_PATH = BASE_DIR / "config" / "database.json"

# --- DB 基础 ---
def load_db_config():
    with open(CONFIG_PATH, "r") as f:
        conf = json.load(f)
    conf["cursorclass"] = pymysql.cursors.DictCursor
    return conf

try:
    DB_CONFIG = load_db_config()
except:
    DB_CONFIG = {}

def get_db_conn(use_db=True):
    config = DB_CONFIG.copy()
    if not use_db: config.pop("database", None)
    return pymysql.connect(**config)

def init_db():
    try:
        conn = get_db_conn(use_db=False)
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']} CHARACTER SET utf8mb4")
        conn.commit()
        conn.close()
        
        conn = get_db_conn(use_db=True)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id VARCHAR(50) PRIMARY KEY,
                keyword VARCHAR(255),
                status VARCHAR(50),
                progress INT,
                msg TEXT,
                created_at DATETIME,
                root_dir TEXT
            )
        """)
        # 启动自检：正在暂停的任务在重启后恢复为已暂停
        cursor.execute("UPDATE tasks SET status = '已暂停' WHERE status = '正在暂停'")
        cursor.execute("UPDATE tasks SET status = '排队中' WHERE status = '执行中'")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Init Error: {e}")

init_db()

# --- 任务模型 ---
class Task:
    @staticmethod
    def add(keyword: str):
        task_id = str(uuid.uuid4())[:8]
        created_at = datetime.now()
        date_folder = created_at.strftime("%Y%m%d")
        root_dir = str(OUTPUTS_DIR / f"{keyword}_{date_folder}")
        conn = get_db_conn()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO tasks VALUES (%s, %s, %s, %s, %s, %s, %s)",
                     (task_id, keyword, "排队中", 0, "等待调度", created_at, root_dir))
        conn.commit()
        conn.close()
        return task_id

    @staticmethod
    def update(task_id: str, **kwargs):
        conn = get_db_conn()
        cursor = conn.cursor()
        for k, v in kwargs.items():
            if k in ["status", "progress", "msg"]:
                cursor.execute(f"UPDATE tasks SET {k} = %s WHERE id = %s", (v, task_id))
        conn.commit()
        conn.close()

# --- 后台工作进程 ---
running_processes = {}

async def pipeline_worker():
    print(">>> Worker Ready.", flush=True)
    while True:
        task_id = None
        try:
            conn = get_db_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT id, keyword FROM tasks WHERE status = '排队中' ORDER BY created_at ASC LIMIT 1")
            t_data = cursor.fetchone()
            
            if not t_data:
                conn.close()
                await asyncio.sleep(5)
                continue
            
            task_id = t_data["id"]
            affected = cursor.execute("UPDATE tasks SET status = '执行中' WHERE id = %s AND status = '排队中'", (task_id,))
            conn.commit()
            conn.close()
            
            if affected == 0: continue
                
            keyword = t_data["keyword"]
            print(f">>> Executing: {keyword} (ID: {task_id})", flush=True)
            
            python_path = "/opt/anaconda3/envs/mytools/bin/python"
            # 关键：传入 --task-id 供脚本自检暂停指令
            cmd = f"export PYTHONPATH=$PYTHONPATH:{BASE_DIR}/src && {python_path} scripts/run_full_pipeline.py --keyword '{keyword}' --task-id '{task_id}'"
            
            process = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, cwd=str(BASE_DIR))
            running_processes[task_id] = process
            
            while True:
                line = await process.stdout.readline()
                if not line: break
                text = line.decode().strip()
                if text:
                    # 脚本如果检测到暂停并自行退出，会打印该信息
                    if "Graceful exit" in text:
                        Task.update(task_id, status="已暂停", msg="任务已在检查点安全暂停")
                    if "Phase 1" in text: Task.update(task_id, msg="闲鱼扫描中...", progress=10)
                    elif "Phase 2" in text: Task.update(task_id, msg="1688溯源中...", progress=30)
                    elif "Processing" in text and "/" in text: Task.update(task_id, msg=f"抓取详情: {text.split(' ')[-1]}")
                    elif "Phase 3" in text: Task.update(task_id, msg="生成报表...", progress=90)
            
            await process.wait()
            # 只有当不是因为暂停退出时，才标记为已完成
            conn = get_db_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM tasks WHERE id = %s", (task_id,))
            final_status = cursor.fetchone()["status"]
            conn.close()
            if final_status == "执行中":
                Task.update(task_id, status="已完成", progress=100, msg="分析完成")
        except: await asyncio.sleep(5)
        finally:
            if task_id: running_processes.pop(task_id, None)

@app.on_event("startup")
async def startup(): asyncio.create_task(pipeline_worker())

# --- API ---
@app.get("/api/tasks")
def list_tasks():
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    for r in rows:
        if isinstance(r['created_at'], datetime): r['created_at'] = r['created_at'].strftime("%Y-%m-%d %H:%M")
    return rows

@app.post("/api/tasks")
def create_task(req: dict): return {"id": Task.add(req["keyword"])}

@app.post("/api/tasks/{task_id}/retry")
def retry_task(task_id: str):
    Task.update(task_id, status="排队中", msg="重新排队...", progress=0)
    return {"status": "ok"}

@app.post("/api/tasks/{task_id}/pause")
def pause_task(task_id: str):
    """ 下达暂停指令，等待脚本运行至 Checkpoint """
    Task.update(task_id, status="正在暂停", msg="正在等待当前货源抓取结束...")
    return {"status": "pausing"}

@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: str):
    conn = get_db_conn()
    conn.cursor().execute("DELETE FROM tasks WHERE id = %s", (task_id,))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.get("/api/task_details/{task_id}")
def get_task_details(task_id: str):
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
    task = cursor.fetchone()
    conn.close()
    if not task: return {"error": "Not found"}
    root_dir = Path(task["root_dir"])
    xianyu_json = root_dir / "xianyu_hot_items.json"
    if not xianyu_json.exists(): return {"details": []}
    items = json.loads(xianyu_json.read_text()).get("hot_items", [])
    return {"task": task, "details": [{"rank": i, "xianyu_item": item, "sources": []} for i, item in enumerate(items, start=1)]}

@app.get("/api/download/{task_id}")
def download_excel(task_id: str):
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
    task = cursor.fetchone()
    conn.close()
    if not task: return {"error": "Not found"}
    excel_path = Path(task["root_dir"]) / f"{task['keyword']}_深度分析报表_标准多Sheet版.xlsx"
    return FileResponse(path=excel_path, filename=excel_path.name) if excel_path.exists() else {"error": "File not found"}

@app.get("/api/sys/status")
def system_status():
    return {"1688_login": "有效", "active_workers": len(running_processes), "db_type": "MySQL"}

app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
