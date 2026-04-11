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

# --- 加载 MySQL 配置 ---
def load_db_config():
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"MySQL 配置文件缺失")
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
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Init Error: {e}")

init_db()

# --- 任务模型 ---
class Task:
    @staticmethod
    def add(keyword: str, status="排队中", msg="等待调度", progress=0, root_dir=None):
        task_id = str(uuid.uuid4())[:8]
        created_at = datetime.now()
        if not root_dir:
            date_folder = datetime.now().strftime("%Y%m%d")
            root_dir = str(OUTPUTS_DIR / f"{keyword}_{date_folder}")
        
        conn = get_db_conn()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO tasks (id, keyword, status, progress, msg, created_at, root_dir) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (task_id, keyword, status, progress, msg, created_at, root_dir)
        )
        conn.commit()
        conn.close()
        return task_id

    @staticmethod
    def update(task_id: str, **kwargs):
        conn = get_db_conn()
        cursor = conn.cursor()
        for key, value in kwargs.items():
            if key in ["status", "progress", "msg", "root_dir"]:
                cursor.execute(f"UPDATE tasks SET {key} = %s WHERE id = %s", (value, task_id))
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
            if isinstance(r['created_at'], datetime):
                r['created_at'] = r['created_at'].strftime("%Y-%m-%d %H:%M")
        return rows

    @staticmethod
    def delete(task_id: str):
        conn = get_db_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
        conn.commit()
        conn.close()

# --- 后台工作进程 ---
running_processes = {}

async def pipeline_worker():
    while True:
        try:
            all_tasks = Task.get_all()
            pending = [t for t in all_tasks if t["status"] == "排队中"]
            if not pending:
                await asyncio.sleep(3)
                continue
            
            t_data = pending[-1]
            task_id, keyword = t_data["id"], t_data["keyword"]
            Task.update(task_id, status="执行中", msg="初始化...")
            
            python_path = "/opt/anaconda3/envs/mytools/bin/python"
            cmd = f"export PYTHONPATH=$PYTHONPATH:{BASE_DIR}/src && {python_path} scripts/run_full_pipeline.py"
            process = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, cwd=str(BASE_DIR)
            )
            running_processes[task_id] = process
            while True:
                line = await process.stdout.readline()
                if not line: break
                text = line.decode().strip()
                if "Phase 1" in text: Task.update(task_id, msg="扫描热点...", progress=10)
                elif "Phase 2" in text: Task.update(task_id, msg="货源匹配...", progress=30)
                elif "Phase 3" in text: Task.update(task_id, msg="生成报表...", progress=90)
            await process.wait()
            Task.update(task_id, status="已完成", progress=100, msg="分析完成")
        except: await asyncio.sleep(5)
        finally: running_processes.pop(task_id, None)

@app.on_event("startup")
async def startup():
    asyncio.create_task(pipeline_worker())

# --- API ---

@app.get("/api/tasks")
def list_tasks(): return Task.get_all()

@app.post("/api/tasks")
def create_task(req: dict): return {"id": Task.add(req["keyword"])}

@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: str):
    Task.delete(task_id)
    return {"status": "deleted"}

@app.get("/api/results/{task_id}")
def get_results(task_id: str):
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
    task = cursor.fetchone()
    conn.close()
    if not task: return {"results": []}
    
    root_dir = Path(task["root_dir"])
    keyword = task["keyword"]
    xianyu_json = root_dir / "xianyu_hot_items.json"
    conclusion_csv = root_dir / f"{keyword}_最终结论分析表.csv"
    
    if not xianyu_json.exists(): return {"results": []}
    
    import csv
    xianyu_data = json.loads(xianyu_json.read_text())
    hot_items_map = {str(item["hot_item_id"]): item for item in xianyu_data.get("hot_items", [])}
    
    results = []
    if conclusion_csv.exists():
        with open(conclusion_csv, encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                item_id = row["闲鱼链接"].split("id=")[1].split("&")[0] if "id=" in row["闲鱼链接"] else None
                source_item = hot_items_map.get(item_id, {})
                results.append({**row, "image_url": source_item.get("image_url")})
    return {"results": results, "keyword": keyword}

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
    return FileResponse(path=excel_path, filename=excel_path.name) if excel_path.exists() else {"error": "File not found"}

def sanitize_dir_name(name: str) -> str:
    import re
    clean = re.sub(r'[\\/:*?"<>|]', '_', name).strip()
    return clean[:30]

@app.get("/api/task_details/{task_id}")
def get_task_details(task_id: str):
    """ 穿透式接口：获取闲鱼商品及其对应的所有 1688 货源详情 """
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
    task = cursor.fetchone()
    conn.close()
    if not task: return {"error": "Task not found"}

    root_dir = Path(task["root_dir"])
    xianyu_json = root_dir / "xianyu_hot_items.json"
    if not xianyu_json.exists(): return {"error": "Xianyu data missing"}

    xianyu_data = json.loads(xianyu_json.read_text())
    hot_items = xianyu_data.get("hot_items", [])

    detailed_data = []
    import csv as csv_mod
    
    for i, item in enumerate(hot_items, start=1):
        safe_title = sanitize_dir_name(item.get("title", "item"))
        item_dir = root_dir / f"Rank_{i}_{safe_title}"
        
        sources = []
        if item_dir.exists():
            # 扫描该闲鱼商品对应的 10 个 CSV 货源文件
            for csv_file in item_dir.glob("*.csv"):
                if "结论分析表" in csv_file.name: continue
                
                # 提取货源基础信息
                offer_id = csv_file.stem.split("_")[-1]
                source_title = csv_file.stem.rsplit("_", 1)[0]
                
                try:
                    with open(csv_file, newline='', encoding='utf-8-sig') as f:
                        reader = csv_mod.DictReader(f)
                        skus = [row for row in reader]
                        if skus:
                            # 计算该货源的最低价
                            prices = [float(s.get("价格", 999999)) for s in skus if s.get("价格")]
                            min_p = min(prices) if prices else 0
                            sources.append({
                                "title": source_title,
                                "offer_id": offer_id,
                                "min_price": min_p,
                                "sku_count": len(skus),
                                "url": f"https://detail.1688.com/offer/{offer_id}.html"
                            })
                except: continue
        
        # 按价格从低到高排序
        sources.sort(key=lambda x: x["min_price"])

        detailed_data.append({
            "rank": i,
            "xianyu_item": item,
            "sources": sources
        })

    return {"task": task, "details": detailed_data}

@app.get("/api/sys/status")
def system_status():
    state_file = BASE_DIR / "state" / "ali1688" / "storage_state.json"
    return {
        "1688_login": "有效" if state_file.exists() else "缺失",
        "db_type": "MySQL",
        "active_workers": len(running_processes),
        "storage_usage": "2.4GB"
    }

app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
