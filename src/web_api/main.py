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
        # 启动自检：修复因重启导致的“执行中”假象
        cursor.execute("UPDATE tasks SET status = '排队中', msg = '系统重启，自动恢复' WHERE status = '执行中'")
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

    @staticmethod
    def get_all():
        conn = get_db_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        for r in rows:
            if isinstance(r['created_at'], datetime): r['created_at'] = r['created_at'].strftime("%Y-%m-%d %H:%M")
        return rows

# --- 后台工作进程 (抢占式逻辑) ---
running_processes = {}

async def pipeline_worker():
    print(">>> Worker Online. Ready for missions.", flush=True)
    while True:
        task_id = None
        try:
            conn = get_db_conn()
            cursor = conn.cursor()
            # 抢占式领取：原子更新状态，防止多 Worker 竞争
            cursor.execute("SELECT id, keyword FROM tasks WHERE status = '排队中' ORDER BY created_at ASC LIMIT 1")
            t_data = cursor.fetchone()
            
            if not t_data:
                conn.close()
                await asyncio.sleep(5)
                continue
            
            task_id = t_data["id"]
            # 立即加锁
            affected = cursor.execute("UPDATE tasks SET status = '执行中', msg = '正在初始化...' WHERE id = %s AND status = '排队中'", (task_id,))
            conn.commit()
            conn.close()
            
            if affected == 0: # 没抢到
                continue
                
            keyword = t_data["keyword"]
            print(f">>> Processing: {keyword} (ID: {task_id})", flush=True)
            
            python_path = "/opt/anaconda3/envs/mytools/bin/python"
            cmd = f"export PYTHONPATH=$PYTHONPATH:{BASE_DIR}/src && {python_path} scripts/run_full_pipeline.py --keyword '{keyword}'"
            
            process = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, cwd=str(BASE_DIR))
            running_processes[task_id] = process
            
            while True:
                line = await process.stdout.readline()
                if not line: break
                text = line.decode().strip()
                if text:
                    if "Phase 1" in text: Task.update(task_id, msg="闲鱼雷达扫描中...", progress=10)
                    elif "Phase 2" in text: Task.update(task_id, msg="1688深度溯源中...", progress=30)
                    elif "Processing" in text and "/" in text: # 捕捉进度
                        Task.update(task_id, msg=f"抓取详情中: {text.split(' ')[-1]}")
                    elif "Phase 3" in text: Task.update(task_id, msg="生成决策报表...", progress=90)
            
            await process.wait()
            Task.update(task_id, status="已完成", progress=100, msg="分析完成")
        except Exception as e:
            print(f"!!! Worker Error: {e}")
            if task_id: Task.update(task_id, status="失败", msg=str(e))
            await asyncio.sleep(5)
        finally:
            if task_id: running_processes.pop(task_id, None)

@app.on_event("startup")
async def startup(): asyncio.create_task(pipeline_worker())

# --- API ---
@app.get("/api/tasks")
def list_tasks(): return Task.get_all()

@app.post("/api/tasks")
def create_task(req: dict): return {"id": Task.add(req["keyword"])}

@app.post("/api/tasks/{task_id}/retry")
def retry_task(task_id: str):
    """ 将任务状态重置为排队中，触发断点续爬 """
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET status = '排队中', msg = '准备恢复任务...', progress = 0 WHERE id = %s", (task_id,))
    conn.commit()
    conn.close()
    return {"status": "retrying"}

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
    conclusion_csv = root_dir / f"{task['keyword']}_最终结论分析表.csv"
    if not xianyu_json.exists(): return {"details": []}
    
    import csv as csv_mod
    items = json.loads(xianyu_json.read_text()).get("hot_items", [])
    details = []
    for i, item in enumerate(items, start=1):
        # 简化版：这里您可以根据需要穿透更多 CSV
        details.append({"rank": i, "xianyu_item": item, "sources": []})
    return {"task": task, "details": details}

@app.get("/api/download/{task_id}")
def download_excel(task_id: str):
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
    task = cursor.fetchone()
    conn.close()
    if not task: return {"error": "Not found"}
    root_dir = Path(task["root_dir"])
    excel_path = root_dir / f"{task['keyword']}_深度分析报表_标准多Sheet版.xlsx"
    if excel_path.exists(): return FileResponse(path=excel_path, filename=excel_path.name)
    return {"error": "File not found"}

@app.get("/api/sys/status")
def system_status():
    return {"1688_login": "有效", "active_workers": len(running_processes), "db_type": "MySQL"}

app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
