import json
import asyncio
import os
import uuid
import pymysql
import re
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

# --- 工具函数 ---
def sanitize_dir_name(name: str) -> str:
    # 移除所有空白字符，并清理非法字符
    clean = re.sub(r'\s+', '', str(name))
    clean = re.sub(r'[\\/:*?"<>|]', '_', clean).strip()
    return clean[:30]


# --- DB 基础 ---
def load_db_config():
    with open(CONFIG_PATH, "r") as f:
        conf = json.load(f)
    conf["cursorclass"] = pymysql.cursors.DictCursor
    return conf

try: DB_CONFIG = load_db_config()
except: DB_CONFIG = {}

def get_db_conn(use_db=True):
    config = DB_CONFIG.copy()
    if not use_db: config.pop("database", None)
    return pymysql.connect(**config)

def init_db():
    try:
        conn = get_db_conn(use_db=False)
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG.get('database', 'xianyu_tools')} CHARACTER SET utf8mb4")
        conn.commit()
        conn.close()
        
        conn = get_db_conn()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id VARCHAR(50) PRIMARY KEY, keyword VARCHAR(255), status VARCHAR(50),
                progress INT, msg TEXT, created_at DATETIME, root_dir TEXT
            )
        """)
        cursor.execute("UPDATE tasks SET status = '已暂停' WHERE status = '正在暂停'")
        cursor.execute("UPDATE tasks SET status = '排队中', msg = '系统重启，自动恢复' WHERE status = '执行中'")
        conn.commit()
        conn.close()
    except Exception as e: print(f"DB Init Error: {e}")

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
        cursor.execute("INSERT INTO tasks (id, keyword, status, progress, msg, created_at, root_dir) VALUES (%s, %s, %s, %s, %s, %s, %s)",
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

# --- 后台 Worker ---
running_processes = {}
async def pipeline_worker():
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
            python_path = "/opt/anaconda3/envs/mytools/bin/python"
            cmd = f"export PYTHONPATH=$PYTHONPATH:{BASE_DIR}/src && {python_path} scripts/run_full_pipeline.py --keyword '{keyword}' --task-id '{task_id}'"
            process = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, cwd=str(BASE_DIR))
            running_processes[task_id] = process
            
            while True:
                line = await process.stdout.readline()
                if not line: break
                text = line.decode().strip()
                if "Graceful exit" in text: Task.update(task_id, status="已暂停", msg="已安全暂停")
                elif "Phase 1" in text: Task.update(task_id, msg="闲鱼扫描中...", progress=10)
                elif "Phase 2" in text: Task.update(task_id, msg="1688溯源中...", progress=30)
                elif "Processing" in text and "/" in text: Task.update(task_id, msg=f"抓取详情: {text.split(' ')[-1]}")
                elif "Phase 3" in text: Task.update(task_id, msg="生成报表...", progress=90)
            
            await process.wait()
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

# --- API Endpoints ---
@app.get("/api/tasks")
def list_tasks(): return Task.get_all()

@app.post("/api/tasks")
def create_task(req: dict): return {"id": Task.add(req["keyword"])}

@app.post("/api/tasks/{task_id}/retry")
def retry_task(task_id: str):
    Task.update(task_id, status="排队中", msg="重新排队...", progress=0)
    return {"status": "ok"}

@app.post("/api/tasks/{task_id}/pause")
def pause_task(task_id: str):
    Task.update(task_id, status="正在暂停", msg="等待检查点...")
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
    if not task: return {"error": "Task not found"}
    # 解析 root_dir (处理可能的路径差异)
    raw_path = task["root_dir"]
    if not raw_path: return {"error": "No root_dir defined"}
    
    root_dir = Path(raw_path)
    # 如果是相对路径，则相对于 BASE_DIR
    if not root_dir.is_absolute():
        root_dir = BASE_DIR / raw_path
        
    xianyu_json = root_dir / "xianyu_hot_items.json"
    if not xianyu_json.exists():
        # 尝试备选方案：检查 outputs 下的同名目录
        alt_dir = BASE_DIR / "outputs" / root_dir.name
        if alt_dir.exists():
            root_dir = alt_dir
            xianyu_json = root_dir / "xianyu_hot_items.json"

    if not xianyu_json.exists():
        return {"task": task, "details": [], "msg": f"Missing data file at {xianyu_json}"}
    
    items = json.loads(xianyu_json.read_text()).get("hot_items", [])
    details = []
    
    try:
        from openpyxl import load_workbook
        def read_excel_price(file_path):
            wb = load_workbook(filename=file_path, read_only=True)
            ws = wb.active
            prices = [float(row[1]) for row in ws.iter_rows(min_row=2, max_col=2, values_only=True) if row[1]]
            return prices
    except ImportError:
        import csv
        def read_excel_price(file_path):
            prices = []
            with open(file_path.with_suffix('.csv'), 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('价格'): prices.append(float(row['价格']))
            return prices

    for i, item in enumerate(items, start=1):
        safe_title = sanitize_dir_name(item.get("title", "item"))
        item_dir = root_dir / f"Rank_{i}_{safe_title}"
        sources = []
        if item_dir.exists():
            for f in item_dir.glob("*.xlsx"):
                try:
                    prices = read_excel_price(f)
                    if not prices: continue
                    offer_id = f.stem.split("_")[-1]
                    source_title = f.stem.replace(f"_{offer_id}", "")
                    sources.append({
                        "title": source_title, "offer_id": offer_id,
                        "min_price": min(prices), "sku_count": len(prices),
                        "url": f"https://detail.1688.com/offer/{offer_id}.html"
                    })
                except: continue
        sources.sort(key=lambda x: x["min_price"])
        details.append({"rank": i, "xianyu_item": item, "sources": sources})
        
    return {"task": task, "details": details}

@app.get("/api/sys/status")
def system_status():
    return {"1688_login": "有效", "active_workers": len(running_processes), "db_type": "MySQL"}

app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
