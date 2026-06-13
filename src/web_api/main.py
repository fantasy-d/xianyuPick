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

from xianyu_tools.config import settings

# --- 常量 ---
BASE_DIR = Path(__file__).resolve().parents[2]
WEB_DIR = BASE_DIR / "web"
OUTPUTS_DIR = BASE_DIR / "outputs"

# --- 辅助函数 ---
DB_CONFIG = settings.get_database_config()
DB_CONFIG["cursorclass"] = pymysql.cursors.DictCursor
def get_db_conn(): return pymysql.connect(**DB_CONFIG)

def init_db_schema():
    try:
        conn = get_db_conn()
        cursor = conn.cursor()
        
        # 1. 创建 ali1688_skus 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ali1688_skus (
                id INT AUTO_INCREMENT PRIMARY KEY,
                source_id INT NOT NULL,
                sku_text VARCHAR(255) NOT NULL,
                price DECIMAL(10,2) NOT NULL,
                stock INT NOT NULL,
                spec_id VARCHAR(50) DEFAULT '',
                image VARCHAR(1024) DEFAULT '',
                FOREIGN KEY (source_id) REFERENCES ali1688_sources(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        
        # 1.5 创建 llm_token_logs 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS llm_token_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                task_id VARCHAR(50) DEFAULT NULL,
                feature VARCHAR(50) NOT NULL,
                model VARCHAR(100) NOT NULL,
                prompt_tokens INT DEFAULT 0,
                completion_tokens INT DEFAULT 0,
                total_tokens INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        
        # 2. 丢弃不需要的库内 HTML 表 ali1688_source_htmls
        cursor.execute("DROP TABLE IF EXISTS ali1688_source_htmls;")
        
        # 3. 自愈添加 html_path 字段以关联本地 HTML 物理文件
        try:
            cursor.execute("ALTER TABLE ali1688_sources ADD COLUMN html_path VARCHAR(1024) DEFAULT '';")
        except Exception:
            pass  # 如果列已经存在则会报错，直接忽略即可
            
        # 4. 自愈修改 publish_status 的 ENUM 增加 'depublished' 和 'deleted' 值以支持下架/删除状态记录
        try:
            cursor.execute("ALTER TABLE xianyu_published_items MODIFY COLUMN publish_status ENUM('pending','success','failed','depublished','deleted') DEFAULT 'pending';")
        except Exception as alter_err:
            logger.warning(f"[DB] Failed to modify publish_status enum: {alter_err}")
            
        # 5. 自愈添加 input_type 字段以支持任务类型的细化展示
        try:
            cursor.execute("ALTER TABLE tasks ADD COLUMN input_type VARCHAR(20) DEFAULT 'keyword';")
        except Exception:
            pass
        # 6. 自愈添加 total_tokens 字段以支持 Token 的计量
        try:
            cursor.execute("ALTER TABLE tasks ADD COLUMN total_tokens INT DEFAULT 0;")
        except Exception:
            pass
        # 7. 物理刷新历史数据，防止 NULL 导致前端 React 渲染 crash
        try:
            cursor.execute("UPDATE tasks SET total_tokens = 0 WHERE total_tokens IS NULL;")
            cursor.execute("UPDATE tasks SET input_type = 'keyword' WHERE input_type IS NULL;")
        except Exception as update_err:
            logger.warning(f"[DB] Failed to refresh historical tasks null values: {update_err}")
            
        # 8. 自愈创建 system_configs 配置表，并进行旧配置数据的零感自动入库
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_configs (
                    cfg_key VARCHAR(50) PRIMARY KEY,
                    cfg_value TEXT NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            cursor.execute("SELECT COUNT(*) AS total FROM system_configs")
            row = cursor.fetchone()
            total = row["total"] if isinstance(row, dict) else row[0]
            if total == 0:
                # 首次运行，将本地 config.json 的配置同步到 DB 里
                from xianyu_tools.config import settings
                llm_data = settings.get("llm")
                if llm_data:
                    cursor.execute("INSERT INTO system_configs (cfg_key, cfg_value) VALUES (%s, %s)", ("llm", json.dumps(llm_data)))
                openapi_data = settings.get("openapi")
                if openapi_data:
                    cursor.execute("INSERT INTO system_configs (cfg_key, cfg_value) VALUES (%s, %s)", ("openapi", json.dumps(openapi_data)))
                logger.info("[DB] Initial configurations successfully synchronized to system_configs table.")
        except Exception as config_db_err:
            logger.error(f"[DB] Failed to initialize system_configs table or sync initial data: {config_db_err}")
            
        conn.commit()
        conn.close()
        logger.info("[DB] Schema initialization complete (ensured tasks.input_type, total_tokens, and fixed NULL values).")
    except Exception as e:
        logger.error(f"[DB] Schema initialization failed: {e}")

# 执行自动建表自愈
init_db_schema()

def sanitize_dir_name(name: str) -> str:
    clean = re.sub(r'\s+', '', str(name))
    return re.sub(r'[\\/:*?"<>|]', '_', clean).strip()[:60]

def _clean_html_span(text: str) -> str:
    if not text: return ""
    text = re.sub(r'<span[^>]*?>.*?</span>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    import html
    text = html.unescape(text)
    text = text.replace(">", ";")
    parts = [p.strip() for p in text.split(";") if p.strip()]
    return ";".join(parts)

DEFAULT_OPENAPI_ACCOUNT = {
    "id": "account-1",
    "name": "闲鱼账号 1",
    "base_url": "https://open.goofish.pro",
    "appid": "",
    "app_secret": "",
    "state_file": "xianyu_state_account-1.json",
    "default_config": {
        "user_name": "",
        "province": 110000,
        "city": 110100,
        "district": 110101,
        "item_biz_type": 2,
        "sp_biz_type": 2,
        "channel_cat_id": "",
        "stuff_status": 100,
        "express_fee": 0,
    },
}

def normalize_openapi_multi_account(raw_cfg: dict | None) -> dict:
    raw_cfg = dict(raw_cfg or {})
    accounts = raw_cfg.get("accounts")
    if isinstance(accounts, list) and accounts:
        normalized_accounts = []
        for index, account in enumerate(accounts, start=1):
            merged = json.loads(json.dumps(DEFAULT_OPENAPI_ACCOUNT, ensure_ascii=False))
            incoming = dict(account or {})
            merged.update({k: v for k, v in incoming.items() if k != "default_config"})
            merged_default = dict(DEFAULT_OPENAPI_ACCOUNT["default_config"])
            merged_default.update(dict(incoming.get("default_config") or {}))
            merged["default_config"] = merged_default
            merged["id"] = merged.get("id") or f"account-{index}"
            merged["name"] = merged.get("name") or f"闲鱼账号 {index}"
            merged["state_file"] = merged.get("state_file") or f"xianyu_state_{merged['id']}.json"
            normalized_accounts.append(merged)
        active_account_id = raw_cfg.get("active_account_id") or normalized_accounts[0]["id"]
        if not any(item["id"] == active_account_id for item in normalized_accounts):
            active_account_id = normalized_accounts[0]["id"]
        return {"active_account_id": active_account_id, "accounts": normalized_accounts}

    merged = json.loads(json.dumps(DEFAULT_OPENAPI_ACCOUNT, ensure_ascii=False))
    merged.update({k: v for k, v in raw_cfg.items() if k != "default_config"})
    merged_default = dict(DEFAULT_OPENAPI_ACCOUNT["default_config"])
    merged_default.update(dict(raw_cfg.get("default_config") or {}))
    merged["default_config"] = merged_default
    merged["state_file"] = raw_cfg.get("state_file") or "xianyu_state.json"
    return {"active_account_id": merged["id"], "accounts": [merged]}

def get_openapi_account(raw_cfg: dict | None, account_id: str | None = None) -> dict:
    normalized = normalize_openapi_multi_account(raw_cfg)
    target_id = account_id or normalized.get("active_account_id")
    selected = next((item for item in normalized["accounts"] if item["id"] == target_id), None)
    return selected or normalized["accounts"][0]


def get_request_openapi_account_id(payload: dict | None = None) -> str | None:
    if not isinstance(payload, dict):
        return None
    account_id = payload.get("account_id")
    return str(account_id).strip() if account_id else None

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
            from scripts.run_xianyu_hot_items import detect_input_type
            input_type = detect_input_type(keyword)
            
            task_id, now = str(uuid.uuid4())[:8], datetime.now()
            version = now.strftime("%Y%m%d")
            root_dir = str(OUTPUTS_DIR / f"{sanitize_dir_name(keyword)}_{version}")
            conn = get_db_conn(); cursor = conn.cursor()
            cursor.execute("INSERT INTO tasks (id, keyword, status, progress, msg, created_at, root_dir, version, is_deleted, input_type) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, %s)",
                         (task_id, keyword, "排队中", 0, "等待调度", now, root_dir, version, input_type))
            conn.commit(); conn.close()
            logger.info(f"Task added: {keyword} ({task_id}), type: {input_type}")
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
        cursor.execute("SELECT id, keyword, status, progress, msg, created_at, version, input_type, total_tokens FROM tasks WHERE is_deleted = 0 ORDER BY created_at DESC")
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
            
            # 物理清理对应的本地 HTML 文件
            try:
                cursor.execute("SELECT html_path FROM ali1688_sources WHERE task_id = %s", (task_id,))
                sources = cursor.fetchall()
                for s in sources:
                    if s.get("html_path"):
                        p = BASE_DIR / s["html_path"] if not Path(s["html_path"]).is_absolute() else Path(s["html_path"])
                        if p.exists() and p.is_file():
                            p.unlink()
                            logger.info(f"[Cleanup] Physically deleted local HTML: {p}")
            except Exception as cleanup_err:
                logger.error(f"[Cleanup] Failed to clean HTML files for task {task_id}: {cleanup_err}")

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
    logger.info(f"Full delete requested for task: {task_id}")
    pause_task(task_id)
    conn = get_db_conn(); cursor = conn.cursor()
    
    # 物理清理对应的本地 HTML 文件（双重保障）
    try:
        cursor.execute("SELECT html_path FROM ali1688_sources WHERE task_id = %s", (task_id,))
        sources = cursor.fetchall()
        for s in sources:
            if s.get("html_path"):
                p = BASE_DIR / s["html_path"] if not Path(s["html_path"]).is_absolute() else Path(s["html_path"])
                if p.exists() and p.is_file():
                    p.unlink()
                    logger.info(f"[Cleanup] Physically deleted local HTML: {p}")
    except Exception as cleanup_err:
        logger.warning(f"[Cleanup] Failed to clean HTML files for deleted task {task_id}: {cleanup_err}")

    cursor.execute("SELECT root_dir FROM tasks WHERE id = %s", (task_id,))
    row = cursor.fetchone()
    if row and row['root_dir']:
        folder_path = Path(row['root_dir'])
        if folder_path.exists() and "outputs" in folder_path.parts:
            try:
                import shutil
                shutil.rmtree(folder_path)
                logger.info(f"Physical folder deleted: {folder_path}")
            except Exception as e:
                logger.error(f"Failed to delete folder {folder_path}: {e}")
                
    # 从爆款和 1688 货源表中硬删除数据
    try:
        cursor.execute("DELETE FROM xianyu_items WHERE task_id = %s", (task_id,))
        cursor.execute("DELETE FROM ali1688_sources WHERE task_id = %s", (task_id,))
        conn.commit()
        logger.info(f"[DB] Cleared database records for task {task_id}")
    except Exception as db_err:
        logger.error(f"[DB] Failed to clear records for task {task_id}: {db_err}")

    Task.update(task_id, status="已删除", msg="任务及物理文件已清理", is_deleted=1, pgid=None)
    conn.close(); return {"status": "ok"}

@app.get("/api/task_details/{task_id}")
def get_task_details(task_id: str):
    try:
        conn = get_db_conn(); cursor = conn.cursor()
        # 1. 找到该任务下的所有闲鱼爆款
        cursor.execute("SELECT * FROM xianyu_items WHERE task_id = %s ORDER BY rank_index ASC", (task_id,))
        db_items = cursor.fetchall()
        
        details = []
        for item in db_items:
            item_db_id = item['id'] # 闲鱼商品的唯一主键
            # 2. 根据该主键去 1688 货源表里捞数据
            cursor.execute("SELECT * FROM ali1688_sources WHERE item_id = %s ORDER BY min_price ASC", (item_db_id,))
            sources_rows = cursor.fetchall()
            
            sources_data = []
            for s in sources_rows:
                # 安全解析图片 JSON
                try: imgs = json.loads(s['images']) if s['images'] else []
                except: imgs = []
                
                sources_data.append({
                    "db_id": s['id'],
                    "title": s['title'],
                    "min_price": float(s['min_price']) if s['min_price'] else 0,
                    "sku_count": s['sku_count'],
                    "url": s['source_url'],
                    "images": imgs,
                    "drop_reason": s['drop_reason']
                })
            
            details.append({
                "rank": item['rank_index'],
                "xianyu_item": {
                    "db_id": item_db_id,
                    "title": item['title'],
                    "price": float(item['price']),
                    "image_url": item['image_url'],
                    "want_count": item['want_count'],
                    "item_url": item['item_url']
                },
                "sources": sources_data
            })
            
        conn.close()
        return {"task_id": task_id, "details": details}
    except Exception as e:
        logger.error(f"Failed to fetch details for task {task_id}: {e}")
        return {"error": str(e)}

def load_source_skus_from_excel(source_id: int) -> list:
    """从本地 excel 中加载商品的默认规格数据"""
    try:
        conn = get_db_conn(); cursor = conn.cursor()
        cursor.execute("SELECT * FROM ali1688_sources WHERE id = %s", (source_id,))
        source = cursor.fetchone()
        if not source:
            conn.close()
            return []
            
        task_id = source['task_id']
        item_id = source['item_id']
        offer_id = source['offer_id']
        
        cursor.execute("SELECT rank_index, title FROM xianyu_items WHERE id = %s", (item_id,))
        item = cursor.fetchone()
        if not item:
            conn.close()
            return []
            
        rank = item['rank_index']
        item_title = item['title']
        
        cursor.execute("SELECT root_dir FROM tasks WHERE id = %s", (task_id,))
        task = cursor.fetchone()
        root_dir_db = task['root_dir'] if task else None
        conn.close()
        
        skus = []
        if root_dir_db:
            root_path = Path(root_dir_db)
            if not root_path.is_absolute():
                root_path = BASE_DIR / root_path
                
            clean_title = sanitize_dir_name(item_title)
            dir_name = f"Rank_{rank}_{clean_title}"
            source_dir = root_path / dir_name
            
            # 兼容相对路径回退
            if not source_dir.exists():
                rel_path = Path(root_dir_db).name
                source_dir = BASE_DIR / "outputs" / rel_path / dir_name
                
            if source_dir.exists():
                xlsx_files = list(source_dir.glob(f"*_{offer_id}.xlsx"))
                if xlsx_files:
                    from openpyxl import load_workbook
                    wb = load_workbook(filename=xlsx_files[0], read_only=True)
                    ws = wb.active
                    rows = list(ws.iter_rows(values_only=True))
                    if len(rows) > 1:
                        for r in rows[1:]:
                            if not r or len(r) < 2 or r[0] is None:
                                continue
                            img_val = str(r[4]) if len(r) > 4 and r[4] is not None else ""
                            is_valid_img = img_val.startswith("http") or img_val.startswith("//") or "alicdn.com" in img_val
                            skus.append({
                                "sku_text": _clean_html_span(str(r[0])),
                                "price": float(r[1]) if r[1] is not None else 0.0,
                                "stock": int(r[2]) if r[2] is not None else 0,
                                "spec_id": str(r[3]) if len(r) > 3 and r[3] is not None else "",
                                "image": img_val if is_valid_img else ""
                            })
        return skus
    except Exception as e:
        logger.error(f"Failed to load skus from excel for source {source_id}: {e}")
        return []


def load_source_skus_from_db(source_id: int):
    try:
        conn = get_db_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT sku_text, price, stock, spec_id, image FROM ali1688_skus WHERE source_id = %s", (source_id,))
        rows = cursor.fetchall()
        conn.close()
        
        if rows:
            skus = []
            for r in rows:
                skus.append({
                    "sku_text": _clean_html_span(r["sku_text"]),
                    "price": float(r["price"]),
                    "stock": int(r["stock"]),
                    "spec_id": r["spec_id"],
                    "image": r["image"]
                })
            return skus
    except Exception as e:
        logger.error(f"Failed to load skus from DB for source {source_id}: {e}")
        
    # 兼容回退读取 Excel 物理文件
    logger.warning(f"[Fallback] DB skus empty or failed for source {source_id}. Loading from Excel...")
    return load_source_skus_from_excel(source_id)


@app.get("/api/source_skus/{source_id}")
def get_source_skus(source_id: int):
    logger.info(f"Fetching SKU list for source_id: {source_id}")
    skus = load_source_skus_from_db(source_id)
    return {"skus": skus}


@app.post("/api/publish/batch")
async def batch_publish_to_xianyu(req: dict = {}):
    logger.info(f"OpenAPI batch publish request: {req}")
    source_ids = req.get("source_ids", [])
    account_id = get_request_openapi_account_id(req)
    if not source_ids:
        return {"success": [], "failed": [{"source_id": 0, "msg": "未选中任何商品"}]}

    custom_configs = req.get("custom_configs", {})
    conn = get_db_conn(); cursor = conn.cursor()

    items_to_publish = []
    failed_items = []

    for sid in source_ids:
        cursor.execute("SELECT * FROM ali1688_sources WHERE id = %s", (sid,))
        source = cursor.fetchone()
        if not source:
            failed_items.append({"source_id": sid, "msg": "货源数据在数据库中不存在"})
            continue

        images = json.loads(source['images'] or "[]")
        custom_info = custom_configs.get(str(sid)) or {}
        custom_title = custom_info.get("title") or source['title']

        # 获取默认规格并进行加价 30 自愈处理
        skus = load_source_skus_from_db(sid)
        sku_items = []
        sku_images = []

        if skus:
            for s in skus:
                sku_items.append({
                    "sku_text": s["sku_text"],
                    "price": round(s["price"] + 30.0, 2),
                    "stock": min(9999, int(s["stock"]) or 1)
                })
            
            seen_img_skus = set()
            for s in skus:
                if s.get("image"):
                    first_attr = s["sku_text"].split(';')[0]
                    if first_attr not in seen_img_skus:
                        seen_img_skus.add(first_attr)
                        sku_images.append({
                            "src": s["image"],
                            "width": 800,
                            "height": 800,
                            "sku_text": first_attr
                        })
            
            final_price = min(s['price'] for s in sku_items)
        else:
            custom_price = custom_info.get("price")
            if custom_price is not None:
                final_price = float(custom_price)
            else:
                final_price = float(source['min_price']) + 30

        item_data = {
            "source_id": sid,
            "title": custom_title[:60],
            "description": f"【精选货源】\n{custom_title}\n品质保障，欢迎选购。",
            "price": final_price,
            "images": images,
        }
        if sku_items:
            item_data["sku_items"] = sku_items
        if sku_images:
            item_data["sku_images"] = sku_images

        items_to_publish.append(item_data)

    conn.close()

    # 调用批量上架自愈核心
    from xianyu_tools.xianyu_adapter.publisher_v3 import PublisherV3
    try:
        publisher = PublisherV3(account_id=account_id)
        batch_res = publisher.publish_items_batch(items_to_publish)
        
        # 将结果写回数据库记录并整合返回
        conn = get_db_conn(); cursor = conn.cursor()
        final_success = []
        final_failed = failed_items
        
        for succ in batch_res.get("success", []):
            sid = succ["source_id"]
            pid = succ["product_id"]
            pub_url = f"https://www.goofish.com/item?id={pid}"
            
            cursor.execute("SELECT task_id FROM ali1688_sources WHERE id = %s", (sid,))
            src = cursor.fetchone()
            task_id = src['task_id'] if src else ""
            
            cursor.execute("INSERT INTO xianyu_published_items (task_id, source_db_id, xianyu_item_id, publish_status, publish_msg, published_url) VALUES (%s,%s,%s,%s,%s,%s)",
                          (task_id, sid, pid, 'success', None, pub_url))
            final_success.append({
                "source_id": sid,
                "product_id": pid,
                "published_url": pub_url,
                "status": "success"
            })
            
        for fail in batch_res.get("failed", []):
            sid = fail["source_id"]
            msg = fail["msg"]
            
            cursor.execute("SELECT task_id FROM ali1688_sources WHERE id = %s", (sid,))
            src = cursor.fetchone()
            task_id = src['task_id'] if src else ""
            
            cursor.execute("INSERT INTO xianyu_published_items (task_id, source_db_id, xianyu_item_id, publish_status, publish_msg, published_url) VALUES (%s,%s,%s,%s,%s,%s)",
                          (task_id, sid, None, 'failed', msg, None))
            final_failed.append({
                "source_id": sid,
                "msg": msg,
                "status": "failed"
            })
            
        conn.commit()
        conn.close()
        
        return {"success": final_success, "failed": final_failed}
        
    except Exception as e:
        logger.error(f"Batch publisher global failure: {e}")
        return {"error": str(e), "success": [], "failed": failed_items}

@app.post("/api/publish/{source_id}")
async def publish_to_xianyu(source_id: int, req: dict = {}):
    logger.info(f"OpenAPI publish request for source_id: {source_id}, custom={req}")
    account_id = get_request_openapi_account_id(req)
    conn = get_db_conn(); cursor = conn.cursor()
    cursor.execute("SELECT * FROM ali1688_sources WHERE id = %s", (source_id,))
    source = cursor.fetchone()
    if not source: conn.close(); return {"error": "Source not found"}
    images = json.loads(source['images'] or "[]")

    # 支持前端传入自定义标题和价格，否则使用默认值
    custom_title = req.get("title") or source['title']
    
    sku_items = req.get("sku_items")
    if sku_items:
        # 如果有多规格，主商品价格自动校准为多规格中的最低价
        final_price = min(float(item['price']) for item in sku_items)
    else:
        custom_price = req.get("price")
        if custom_price is not None:
            final_price = float(custom_price)
        else:
            final_price = float(source['min_price']) + 30

    item_data = {
        "title": custom_title[:60],
        "description": f"【精选货源】\n{custom_title}\n品质保障，欢迎选购。",
        "price": final_price,
        "images": images,
    }
    sku_images = req.get("sku_images")
    if sku_items:
        item_data["sku_items"] = sku_items
    if sku_images:
        item_data["sku_images"] = sku_images
    from xianyu_tools.xianyu_adapter.publisher_v3 import PublisherV3
    try:
        publisher = PublisherV3(account_id=account_id)
        result = publisher.publish_item(item_data)
        pub_url = f"https://www.goofish.com/item?id={result.get('xianyu_item_id')}" if result.get('status') == 'success' else None
        cursor.execute("INSERT INTO xianyu_published_items (task_id, source_db_id, xianyu_item_id, publish_status, publish_msg, published_url) VALUES (%s,%s,%s,%s,%s,%s)",
                     (source['task_id'], source_id, result.get('xianyu_item_id'), result['status'], result.get('msg'), pub_url))
        conn.commit(); conn.close(); return {**result, "published_url": pub_url}
    except Exception as e:
        logger.error(f"Publisher Error: {e}"); conn.close(); return {"status": "failed", "msg": str(e)}

@app.get("/api/published_status/{source_id}")
def get_published_status(source_id: int):
    conn = get_db_conn(); cursor = conn.cursor()
    cursor.execute("SELECT publish_status, published_url FROM xianyu_published_items WHERE source_db_id = %s ORDER BY created_at DESC LIMIT 1", (source_id,))
    res = cursor.fetchone(); conn.close()
    return res if res else {"publish_status": "none"}

@app.post("/api/depublish/batch")
async def batch_depublish_from_xianyu(req: dict = {}):
    logger.info(f"OpenAPI batch depublish request: {req}")
    source_ids = req.get("source_ids", [])
    account_id = get_request_openapi_account_id(req)
    if not source_ids:
        return {"success": [], "failed": [{"source_id": 0, "msg": "未选中任何商品"}]}

    from xianyu_tools.xianyu_adapter.publisher_v3 import PublisherV3
    try:
        publisher = PublisherV3(account_id=account_id)
    except Exception as e:
        logger.error(f"Failed to initialize PublisherV3: {e}")
        return {"success": [], "failed": [{"source_id": sid, "msg": f"初始化发布器失败: {e}"} for sid in source_ids]}

    conn = get_db_conn(); cursor = conn.cursor()
    success_list = []
    failed_list = []

    for sid in source_ids:
        # 1. 查找此货源最近成功的上架记录
        cursor.execute("""
            SELECT xianyu_item_id, task_id 
            FROM xianyu_published_items 
            WHERE source_db_id = %s AND publish_status = 'success' 
            ORDER BY created_at DESC LIMIT 1
        """, (sid,))
        row = cursor.fetchone()
        
        if not row:
            failed_list.append({"source_id": sid, "msg": "未找到该商品的成功发布记录，无法执行下架"})
            continue
            
        xianyu_item_id = row['xianyu_item_id']
        task_id = row['task_id']
        
        # 2. 执行下架
        try:
            result = publisher.depublish_item(xianyu_item_id)
            is_success = result.get("status") == "success"
            is_invalid_state = "不满足下架条件" in result.get("msg", "")
            
            if is_success or is_invalid_state:
                # 3. 记账
                msg = '已下架' if is_success else f"已下架 ({result.get('msg')})"
                cursor.execute("""
                    INSERT INTO xianyu_published_items (task_id, source_db_id, xianyu_item_id, publish_status, publish_msg, published_url)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (task_id, sid, xianyu_item_id, 'depublished', msg, None))
                success_list.append({"source_id": sid})
            else:
                failed_list.append({"source_id": sid, "msg": result.get("msg", "下架失败")})
        except Exception as e:
            logger.error(f"Batch depublish failed for source {sid}: {e}")
            failed_list.append({"source_id": sid, "msg": f"下架异常: {e}"})

    conn.commit()
    conn.close()
    return {"success": success_list, "failed": failed_list}

@app.post("/api/depublish/{source_id}")
async def depublish_from_xianyu(source_id: int, req: dict = {}):
    logger.info(f"OpenAPI depublish request for source_id: {source_id}")
    account_id = get_request_openapi_account_id(req)
    conn = get_db_conn(); cursor = conn.cursor()
    
    # 1. 查找此货源最近成功的上架记录
    cursor.execute("""
        SELECT xianyu_item_id, task_id 
        FROM xianyu_published_items 
        WHERE source_db_id = %s AND publish_status = 'success' 
        ORDER BY created_at DESC LIMIT 1
    """, (source_id,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return {"status": "failed", "msg": "未找到该商品的成功发布记录，无法执行下架"}
        
    xianyu_item_id = row['xianyu_item_id']
    task_id = row['task_id']
    
    # 2. 调用 PublisherV3 执行下架
    from xianyu_tools.xianyu_adapter.publisher_v3 import PublisherV3
    try:
        publisher = PublisherV3(account_id=account_id)
        result = publisher.depublish_item(xianyu_item_id)
        
        is_success = result.get("status") == "success"
        is_invalid_state = "不满足下架条件" in result.get("msg", "")
        
        if is_success or is_invalid_state:
            # 3. 在发布表插入已下架状态，完成流水记账
            msg = '已下架' if is_success else f"已下架 ({result.get('msg')})"
            cursor.execute("""
                INSERT INTO xianyu_published_items (task_id, source_db_id, xianyu_item_id, publish_status, publish_msg, published_url)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (task_id, source_id, xianyu_item_id, 'depublished', msg, None))
            conn.commit()
            conn.close()
            
            return_msg = "下架成功" if is_success else f"已从本地强行下架/同步状态 (闲鱼提示: {result.get('msg')})"
            return {"status": "success", "msg": return_msg}
        else:
            conn.close()
            return {"status": "failed", "msg": result.get("msg", "下架失败")}
            
    except Exception as e:
        logger.error(f"Depublisher Error: {e}")
        conn.close()
        return {"status": "failed", "msg": str(e)}

@app.post("/api/delete/batch")
async def batch_delete_from_xianyu(req: dict = {}):
    logger.info(f"OpenAPI batch delete request: {req}")
    source_ids = req.get("source_ids", [])
    account_id = get_request_openapi_account_id(req)
    if not source_ids:
        return {"success": [], "failed": [{"source_id": 0, "msg": "未选中任何商品"}]}

    from xianyu_tools.xianyu_adapter.publisher_v3 import PublisherV3
    try:
        publisher = PublisherV3(account_id=account_id)
    except Exception as e:
        logger.error(f"Failed to initialize PublisherV3 for delete: {e}")
        return {"success": [], "failed": [{"source_id": sid, "msg": f"初始化发布器失败: {e}"} for sid in source_ids]}

    conn = get_db_conn(); cursor = conn.cursor()
    success_list = []
    failed_list = []

    for sid in source_ids:
        # 1. 查找此货源最新的一条发布流水记录，校验状态必须为 'depublished'
        cursor.execute("""
            SELECT publish_status, xianyu_item_id, task_id 
            FROM xianyu_published_items 
            WHERE source_db_id = %s 
            ORDER BY created_at DESC LIMIT 1
        """, (sid,))
        row = cursor.fetchone()

        if not row:
            failed_list.append({"source_id": sid, "msg": "商品未发布，无法删除"})
            continue

        status = row['publish_status']
        xianyu_item_id = row['xianyu_item_id']
        task_id = row['task_id']

        if status != 'depublished':
            failed_list.append({"source_id": sid, "msg": f"商品状态为 {status}，只有已下架商品可以删除"})
            continue

        # 2. 调用 PublisherV3 执行删除
        try:
            result = publisher.delete_item(xianyu_item_id)
            if result.get("status") == "success":
                # 3. 记账
                cursor.execute("""
                    INSERT INTO xianyu_published_items (task_id, source_db_id, xianyu_item_id, publish_status, publish_msg, published_url)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (task_id, sid, xianyu_item_id, 'deleted', '已删除', None))
                success_list.append({"source_id": sid})
            else:
                failed_list.append({"source_id": sid, "msg": result.get("msg", "删除失败")})
        except Exception as e:
            logger.error(f"Batch delete failed for source {sid}: {e}")
            failed_list.append({"source_id": sid, "msg": f"删除异常: {e}"})

    conn.commit()
    conn.close()
    return {"success": success_list, "failed": failed_list}

@app.post("/api/delete/{source_id}")
async def delete_from_xianyu(source_id: int, req: dict = {}):
    logger.info(f"OpenAPI delete request for source_id: {source_id}")
    account_id = get_request_openapi_account_id(req)
    conn = get_db_conn(); cursor = conn.cursor()

    # 1. 查找此货源最新的一条发布流水记录，校验状态必须为 'depublished'
    cursor.execute("""
        SELECT publish_status, xianyu_item_id, task_id 
        FROM xianyu_published_items 
        WHERE source_db_id = %s 
        ORDER BY created_at DESC LIMIT 1
    """, (source_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return {"status": "failed", "msg": "商品未发布，无法删除"}

    status = row['publish_status']
    xianyu_item_id = row['xianyu_item_id']
    task_id = row['task_id']

    if status != 'depublished':
        conn.close()
        return {"status": "failed", "msg": f"商品当前状态为 {status}，只有已下架商品可以删除"}

    # 2. 调用 PublisherV3 执行删除
    from xianyu_tools.xianyu_adapter.publisher_v3 import PublisherV3
    try:
        publisher = PublisherV3(account_id=account_id)
        result = publisher.delete_item(xianyu_item_id)

        if result.get("status") == "success":
            # 3. 记账
            cursor.execute("""
                INSERT INTO xianyu_published_items (task_id, source_db_id, xianyu_item_id, publish_status, publish_msg, published_url)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (task_id, source_id, xianyu_item_id, 'deleted', '已删除', None))
            conn.commit()
            conn.close()
            return {"status": "success", "msg": "删除成功"}
        else:
            conn.close()
            return {"status": "failed", "msg": result.get("msg", "删除失败")}

    except Exception as e:
        logger.error(f"Publisher Delete Error: {e}")
        conn.close()
        return {"status": "failed", "msg": str(e)}

@app.get("/api/xianyu_products")
def get_xianyu_products(
    page: int = 1, 
    limit: int = 10, 
    keyword: str = "", 
    sort_by: str = "publish_time", 
    sort_order: str = "desc",
    publish_status: str = "",
    min_source_price: float = None,
    max_source_price: float = None,
    min_ref_price: float = None,
    max_ref_price: float = None
):
    offset = (page - 1) * limit
    conn = get_db_conn(); cursor = conn.cursor()

    # 联表查询最新一条发布记录，且最新状态非 'deleted'
    query_base = """
        FROM xianyu_published_items p
        INNER JOIN (
            SELECT source_db_id, MAX(created_at) as max_time
            FROM xianyu_published_items
            GROUP BY source_db_id
        ) latest ON p.source_db_id = latest.source_db_id AND p.created_at = latest.max_time
        INNER JOIN ali1688_sources s ON p.source_db_id = s.id
        LEFT JOIN xianyu_items xi ON s.item_id = xi.id
        WHERE p.publish_status IN ('success', 'depublished', 'pending', 'failed')
    """

    params = []
    if keyword:
        query_base += " AND (s.title LIKE %s OR xi.title LIKE %s)"
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    if publish_status:
        if publish_status == 'success':
            query_base += " AND p.publish_status IN ('success', 'done')"
        else:
            query_base += " AND p.publish_status = %s"
            params.append(publish_status)

    if min_source_price is not None:
        query_base += " AND s.min_price >= %s"
        params.append(min_source_price)
    if max_source_price is not None:
        query_base += " AND s.min_price <= %s"
        params.append(max_source_price)

    if min_ref_price is not None:
        query_base += " AND xi.price >= %s"
        params.append(min_ref_price)
    if max_ref_price is not None:
        query_base += " AND xi.price <= %s"
        params.append(max_ref_price)

    count_query = f"SELECT COUNT(*) as count {query_base}"
    cursor.execute(count_query, tuple(params))
    total_count = cursor.fetchone()['count']

    # 排序字段映射防御 SQL 注入
    sort_mapping = {
        "title": "s.title",
        "xianyu_item_id": "p.xianyu_item_id",
        "publish_status": "p.publish_status",
        "source_price": "s.min_price",
        "ref_price": "xi.price",
        "publish_time": "p.created_at"
    }
    order_field = sort_mapping.get(sort_by, "p.created_at")
    order_direction = "DESC" if sort_order.lower() == "desc" else "ASC"

    data_query = f"""
        SELECT 
            p.id as publish_id,
            p.task_id,
            p.source_db_id,
            p.xianyu_item_id,
            p.publish_status,
            p.publish_msg,
            p.published_url,
            p.created_at as publish_time,
            s.title as source_title,
            s.source_url as source_url,
            s.images as source_images,
            s.min_price as source_price,
            s.sku_count as source_sku_count,
            xi.title as ref_title,
            xi.price as ref_price,
            xi.want_count as ref_want_count
        {query_base}
        ORDER BY {order_field} {order_direction}
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])
    cursor.execute(data_query, tuple(params))
    rows = cursor.fetchall()
    conn.close()

    items = []
    for r in rows:
        images_list = []
        if r['source_images']:
            try:
                images_list = json.loads(r['source_images'])
            except Exception:
                pass

        items.append({
            "publish_id": r["publish_id"],
            "task_id": r["task_id"],
            "source_db_id": r["source_db_id"],
            "xianyu_item_id": r["xianyu_item_id"],
            "publish_status": r["publish_status"],
            "publish_msg": r["publish_msg"],
            "published_url": r["published_url"],
            "publish_time": r["publish_time"].strftime("%Y-%m-%d %H:%M:%S") if r["publish_time"] else "",
            "source_title": r["source_title"],
            "source_url": r["source_url"],
            "source_image": images_list[0] if images_list else "",
            "source_price": float(r["source_price"]) if r["source_price"] is not None else 0.0,
            "source_sku_count": r["source_sku_count"],
            "ref_title": r["ref_title"] or "",
            "ref_price": float(r["ref_price"]) if r["ref_price"] is not None else 0.0,
            "ref_want_count": r["ref_want_count"] or 0
        })

    return {
        "items": items,
        "total": total_count,
        "page": page,
        "limit": limit
    }

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

@app.get("/api/token/stats")
def get_token_stats():
    try:
        conn = get_db_conn()
        cursor = conn.cursor()
        
        # 1. 汇总数据
        cursor.execute("""
            SELECT 
                COUNT(*) as total_calls,
                IFNULL(SUM(prompt_tokens), 0) as total_prompt_tokens,
                IFNULL(SUM(completion_tokens), 0) as total_completion_tokens,
                IFNULL(SUM(total_tokens), 0) as total_tokens,
                COUNT(DISTINCT model) as model_count,
                COUNT(DISTINCT feature) as feature_count
            FROM llm_token_logs
        """)
        summary = cursor.fetchone()
        if not summary or summary.get("total_calls") == 0:
            summary = {
                "total_calls": 0, "total_prompt_tokens": 0, "total_completion_tokens": 0, 
                "total_tokens": 0, "model_count": 0, "feature_count": 0
            }
        
        # 2. 按模型统计
        cursor.execute("""
            SELECT 
                model,
                COUNT(*) as calls,
                IFNULL(SUM(prompt_tokens), 0) as prompt_tokens,
                IFNULL(SUM(completion_tokens), 0) as completion_tokens,
                IFNULL(SUM(total_tokens), 0) as total_tokens
            FROM llm_token_logs
            GROUP BY model
            ORDER BY total_tokens DESC
        """)
        by_model = cursor.fetchall()
        
        # 3. 按功能统计
        cursor.execute("""
            SELECT 
                feature,
                COUNT(*) as calls,
                IFNULL(SUM(prompt_tokens), 0) as prompt_tokens,
                IFNULL(SUM(completion_tokens), 0) as completion_tokens,
                IFNULL(SUM(total_tokens), 0) as total_tokens
            FROM llm_token_logs
            GROUP BY feature
            ORDER BY total_tokens DESC
        """)
        by_feature = cursor.fetchall()
        
        # 4. 最近 20 条明细日志 (关联任务关键词)
        cursor.execute("""
            SELECT 
                l.id,
                l.task_id,
                t.keyword as task_keyword,
                l.feature,
                l.model,
                l.prompt_tokens,
                l.completion_tokens,
                l.total_tokens,
                DATE_FORMAT(l.created_at, '%Y-%m-%d %H:%i:%s') as created_at
            FROM llm_token_logs l
            LEFT JOIN tasks t ON l.task_id = t.id
            ORDER BY l.id DESC
            LIMIT 20
        """)
        recent_logs = cursor.fetchall()
        
        conn.close()
        return {
            "status": "success",
            "summary": summary,
            "by_model": by_model,
            "by_feature": by_feature,
            "recent_logs": recent_logs
        }
    except Exception as e:
        logger.error(f"Failed to fetch token stats: {e}")
        return {"status": "error", "message": str(e)}

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

@app.get("/api/system/configs")
def get_system_configs():
    try:
        from xianyu_tools.config import settings
        from xianyu_tools.xianyu_adapter.state_inspector import inspect_state_file

        openapi_cfg = normalize_openapi_multi_account(settings.get_openapi_raw_config())
        for account in openapi_cfg["accounts"]:
            try:
                session_report = inspect_state_file(account.get("state_file") or "xianyu_state.json")
                account_name = session_report.get("account_name") or ""
                is_usable = bool(session_report.get("is_usable"))
            except Exception:
                account_name = ""
                is_usable = False
            account["default_config"]["user_name"] = account_name
            account["session_report"] = {
                "account_name": account_name,
                "is_usable": is_usable,
            }

        return {
            "status": "success",
            "data": {
                "llm": settings.get_llm_config(),
                "openapi": openapi_cfg,
                "crawl": settings.get_crawl_config()
            }
        }
    except Exception as e:
        logger.error(f"Failed to fetch system configs API: {e}")
        return {"status": "failed", "msg": str(e)}

@app.post("/api/system/configs")
async def update_system_configs(payload: dict):
    try:
        from xianyu_tools.config import settings
        from xianyu_tools.xianyu_adapter.state_inspector import inspect_state_file
        import json
        
        llm_cfg = payload.get("llm", [])
        openapi_cfg = normalize_openapi_multi_account(payload.get("openapi", {}))
        crawl_cfg = payload.get("crawl", {})
        
        logger.info(
            "[OpenAPI Save] active_account_id=%s accounts=%s",
            openapi_cfg.get("active_account_id"),
            [item.get("id") for item in openapi_cfg.get("accounts", [])]
        )
        for account in openapi_cfg["accounts"]:
            account.pop("session_report", None)
            try:
                session_report = inspect_state_file(account.get("state_file") or "xianyu_state.json")
                account_name = session_report.get("account_name") or ""
            except Exception:
                account_name = ""
            account["default_config"]["user_name"] = account_name
            
        # --- 校验并规范化 crawl 配置 ---
        source_limit = crawl_cfg.get("source_limit_1688", 10)
        try:
            source_limit = int(source_limit)
            if source_limit <= 0:
                source_limit = 10
            elif source_limit > 100:
                source_limit = 100
        except (ValueError, TypeError):
            source_limit = 10
        crawl_cfg["source_limit_1688"] = source_limit

        # 过滤模型子集，确保其中每一个都存在于 llm 配置的白名单中
        models_subset = crawl_cfg.get("source_filter_models", [])
        if not isinstance(models_subset, list):
            models_subset = []
        valid_models = []
        for cfg in llm_cfg:
            raw_models = cfg.get("models") or cfg.get("model") or []
            model_arr = raw_models if isinstance(raw_models, list) else [raw_models]
            for m in model_arr:
                if m and isinstance(m, str) and m not in valid_models:
                    valid_models.append(m)
        filtered_models = [m for m in models_subset if m in valid_models]
        crawl_cfg["source_filter_models"] = filtered_models
        
        # 1. 动态加载本地已有的 config.json 文件，以完整保留原有 database 配置！
        config_file = settings.config_file
        existing_config = {}
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    existing_config = json.load(f)
            except Exception:
                pass
                
        db_cfg = existing_config.get("database", {})
        # 如果读取失败或者原本没有，则采用 settings 的默认后备数据库配置
        if not db_cfg:
            db_cfg = settings.get_database_config()
            
        new_config_data = {
            "database": db_cfg,
            "llm": llm_cfg,
            "openapi": openapi_cfg,
            "crawl": crawl_cfg
        }
        
        config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(new_config_data, f, ensure_ascii=False, indent=4)
            
        # 2. 同步写入数据库表中
        conn = get_db_conn()
        cursor = conn.cursor()
        
        # 确保表一定存在
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_configs (
                cfg_key VARCHAR(50) PRIMARY KEY,
                cfg_value TEXT NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        
        cursor.execute("INSERT INTO system_configs (cfg_key, cfg_value) VALUES (%s, %s) ON DUPLICATE KEY UPDATE cfg_value = VALUES(cfg_value)", ("llm", json.dumps(llm_cfg)))
        cursor.execute("INSERT INTO system_configs (cfg_key, cfg_value) VALUES (%s, %s) ON DUPLICATE KEY UPDATE cfg_value = VALUES(cfg_value)", ("openapi", json.dumps(openapi_cfg)))
        cursor.execute("INSERT INTO system_configs (cfg_key, cfg_value) VALUES (%s, %s) ON DUPLICATE KEY UPDATE cfg_value = VALUES(cfg_value)", ("crawl", json.dumps(crawl_cfg)))
        conn.commit()
        conn.close()
        
        # 3. 清理 settings 的数据库缓存，并重新触发 load()
        settings._db_cache.clear()
        settings.load()
        
        return {"status": "success", "msg": "配置已保存并同步成功"}
    except Exception as e:
        logger.error(f"Failed to save system configs API: {e}")
        return {"status": "failed", "msg": f"保存配置发生异常: {str(e)}"}

@app.get("/api/system/regions")
def get_system_regions():
    import urllib.request
    import urllib.parse
    import openpyxl
    import os
    import json
    from pathlib import Path
    
    json_path = Path("config/goofish_regions.json")
    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {"status": "success", "data": data}
        except Exception as e:
            logger.error(f"Failed to read regions cache: {e}")
            
    # 如果缓存不存在，尝试自动从闲管家下载解析并缓存
    url_base = "https://file.goofish.pro/doc/"
    filename = "闲管家省市区.xlsx"
    encoded_url = url_base + urllib.parse.quote(filename)
    dest_path = Path("config/goofish_regions.xlsx")
    
    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(
            encoded_url, 
            headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        )
        with urllib.request.urlopen(req) as response:
            with open(dest_path, "wb") as f:
                f.write(response.read())
                
        wb = openpyxl.load_workbook(dest_path, read_only=True)
        sheet = wb.active
        
        regions = {}
        # Header: ('省份ID', '省份名称', '城市ID', '城市名称', '地区ID', '地区名称')
        for r_idx, row in enumerate(sheet.iter_rows(values_only=True)):
            if r_idx == 0:
                continue
            if not row or len(row) < 6:
                continue
                
            prov_id, prov_name, city_id, city_name, dist_id, dist_name = row
            if not prov_id or not prov_name:
                continue
                
            prov_id = int(prov_id)
            prov_name = str(prov_name).strip()
            
            if prov_id not in regions:
                regions[prov_id] = {
                    "name": prov_name,
                    "code": prov_id,
                    "cities": {}
                }
                
            if not city_id or not city_name:
                continue
                
            city_id = int(city_id)
            city_name = str(city_name).strip()
            
            if city_id not in regions[prov_id]["cities"]:
                regions[prov_id]["cities"][city_id] = {
                    "name": city_name,
                    "code": city_id,
                    "districts": {}
                }
                
            if not dist_id or not dist_name:
                continue
                
            dist_id = int(dist_id)
            dist_name = str(dist_name).strip()
            
            regions[prov_id]["cities"][city_id]["districts"][dist_id] = {
                "name": dist_name,
                "code": dist_id
            }

        sorted_regions = []
        for p_id in sorted(regions.keys()):
            p_data = regions[p_id]
            sorted_cities = []
            for c_id in sorted(p_data["cities"].keys()):
                c_data = p_data["cities"][c_id]
                sorted_districts = []
                for d_id in sorted(c_data["districts"].keys()):
                    sorted_districts.append(c_data["districts"][d_id])
                c_data["districts"] = sorted_districts
                sorted_cities.append(c_data)
            p_data["cities"] = sorted_cities
            sorted_regions.append(p_data)
            
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(sorted_regions, f, ensure_ascii=False, indent=4)
            
        return {"status": "success", "data": sorted_regions}
    except Exception as e:
        logger.error(f"Failed to auto download/parse goofish regions: {e}")
        return {"status": "failed", "msg": f"获取省市区失败: {str(e)}"}
    finally:
        if dest_path.exists():
            os.remove(dest_path)

@app.get("/api/system/openapi_categories")
def get_openapi_categories(group: str = None, query: str = None, cat_id: str = None, account_id: str = None):
    import json
    from pathlib import Path
    
    cache_path = Path("config/xianyu_categories.json")
    if not cache_path.exists():
        try:
            from xianyu_tools.xianyu_adapter.publisher_v3 import PublisherV3
            pub = PublisherV3(account_id=account_id)
            categories = pub._load_categories()
        except Exception as e:
            logger.error(f"Failed to trigger categories download: {e}")
            categories = []
    else:
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                categories = json.load(f)
        except Exception as e:
            logger.error(f"Failed to read category cache: {e}")
            categories = []
            
    if not categories:
        return {"status": "failed", "msg": "获取类目失败，缓存为空且同步异常"}
        
    # 提取所有大类分组 sp_biz_name
    groups_set = set()
    for item in categories:
        g_name = item.get("sp_biz_name")
        if g_name:
            groups_set.add(g_name)
    groups = sorted(list(groups_set))
    
    # 根据 group, query, cat_id 进行过滤
    filtered = []
    query_lower = query.lower().strip() if query else None
    
    seen_ids = set()
    for item in categories:
        item_group = item.get("sp_biz_name")
        item_name = item.get("channel_cat_name", "")
        item_id = item.get("channel_cat_id")
        
        # 0. 精准过滤 ID (如果提供了 cat_id)
        if cat_id and item_id != cat_id:
            continue
            
        # 1. 过滤大类
        if not cat_id and group and item_group != group:
            continue
            
        # 2. 模糊匹配关键字
        if not cat_id and query_lower and query_lower not in item_name.lower():
            continue
            
        # 3. 对发布类目 ID 进行去重，避免相同类目由于被重复分发在多个大类下而导致前端显示重复项
        if item_id in seen_ids:
            continue
        seen_ids.add(item_id)
            
        filtered.append({
            "id": item_id,
            "name": f"{item_group} - {item_name}" if item_group else item_name,
            "group": item_group
        })
        
    # 限制返回的前 100 条
    limited_data = filtered[:100]
    
    return {
        "status": "success",
        "data": {
            "groups": groups,
            "categories": limited_data,
            "total_matches": len(filtered),
            "is_truncated": len(filtered) > 100
        }
    }

# --- 闲鱼登录态自动捕获逻辑与接口 ---
is_logging_in = False
logging_in_account_id = ""
login_err_msg = ""

async def run_xianyu_login_capture(account_id: str | None = None):
    global is_logging_in, logging_in_account_id, login_err_msg
    is_logging_in = True
    logging_in_account_id = account_id or ""
    login_err_msg = ""
    
    from xianyu_tools.xianyu_adapter.browser_transport import PlaywrightBrowserTransport, PlaywrightBrowserConfig, default_desktop_context_options
    from xianyu_tools.config import settings
    account_cfg = get_openapi_account(settings.get_openapi_raw_config(), account_id)
    state_file = account_cfg.get("state_file") or f"xianyu_state_{account_cfg.get('id') or 'default'}.json"
    
    transport = PlaywrightBrowserTransport(
        config=PlaywrightBrowserConfig(
            headless=False,
            browser_channel="chrome",
            launch_args=["--start-maximized"],
            context_options=default_desktop_context_options(),
        )
    )
    
    try:
        async with transport._playwright_context() as playwright:
            browser = await playwright.chromium.launch(
                channel="chrome",
                headless=False,
                args=["--start-maximized"],
            )
            try:
                context = await transport._new_context(browser)
                page = await context.new_page()
                
                logger.info("[Xianyu Login] Opening Goofish homepage for QR login...")
                await page.goto(
                    "https://www.goofish.com/",
                    wait_until="domcontentloaded",
                    timeout=60000,
                )

                await page.wait_for_timeout(2500)

                # 直接点击闲鱼首页头部右上角登录入口，优先避开页面其它同名文案。
                login_selectors = [
                    'div[class*="user-order-container"] a:has-text("登录")',
                    'a:has-text("登录")',
                    "text=立即登录",
                    "text=登录",
                ]
                login_opened = False
                for selector in login_selectors:
                    try:
                        locator = page.locator(selector).first
                        if await locator.count():
                            logger.info(f"[Xianyu Login] Trying QR login opener selector: {selector}")
                            await locator.click(timeout=3000)
                            await page.wait_for_timeout(1200)
                            if await page.locator("text=手机扫码安全登录").count():
                                logger.info(f"[Xianyu Login] Opened QR login modal via selector: {selector}")
                                login_opened = True
                                break
                    except Exception:
                        continue

                if not login_opened:
                    logger.warning("[Xianyu Login] QR login modal was not auto-opened; page remains on Goofish homepage.")
                
                logged_in = False
                # 轮询 10 分钟，登录进行中时用更短间隔尽快感知成功状态
                for _ in range(1200):
                    await asyncio.sleep(0.5)
                    
                    if page.is_closed():
                        break
                        
                    cookies = await context.cookies("https://www.goofish.com/")
                    cookie_names = {c["name"] for c in cookies}
                    
                    # 检查是否包含 unb 或者是 tracknick，表明已登录成功
                    if "unb" in cookie_names or "tracknick" in cookie_names:
                        logger.info("[Xianyu Login] Login detected! Capturing state snapshot...")
                        await asyncio.sleep(0.3)
                        
                        from xianyu_tools.xianyu_adapter.state_exporter import PlaywrightStateExporter, StateExportConfig, build_snapshot
                        exporter = PlaywrightStateExporter(
                            config=StateExportConfig(
                                output_file=state_file,
                                browser_channel="chrome",
                                headless=False,
                            )
                        )
                        page_data = await exporter._capture_page_data(page)
                        headers = await exporter._capture_headers(page)
                        final_cookies = await context.cookies("https://www.goofish.com/")
                        
                        snapshot = build_snapshot(page.url, page_data, headers, final_cookies)
                        
                        # 自动保存到本地文件
                        import json
                        with open(state_file, "w", encoding="utf-8") as f:
                            json.dump(snapshot, f, ensure_ascii=False, indent=2)
                        
                        logger.info("[Xianyu Login] State file successfully captured and saved.")
                        is_logging_in = False
                        logged_in = True
                        break
                
                if not logged_in and not page.is_closed():
                    logger.warning("[Xianyu Login] Session ended or timed out without login success.")
            except Exception as inner_e:
                logger.error(f"[Xianyu Login] Error in login runner: {inner_e}")
                login_err_msg = str(inner_e)
            finally:
                try:
                    if not page.is_closed():
                        await page.close()
                except Exception:
                    pass
                await browser.close()
    except Exception as e:
        logger.error(f"[Xianyu Login] Failed to launch playwright browser: {e}")
        login_err_msg = str(e)
    finally:
        is_logging_in = False
        logging_in_account_id = ""

@app.get("/api/system/xianyu_login_status")
def get_xianyu_login_status(account_id: str = None):
    try:
        from xianyu_tools.config import settings
        from xianyu_tools.xianyu_adapter.state_inspector import inspect_state_file
        account_cfg = get_openapi_account(settings.get_openapi_raw_config(), account_id)
        state_file = account_cfg.get("state_file") or "xianyu_state.json"
        report = inspect_state_file(state_file)
        return {
            "status": "success",
            "data": {
                "report": report,
                "is_logging_in": is_logging_in and logging_in_account_id == (account_cfg.get("id") or ""),
                "err_msg": login_err_msg
            }
        }
    except Exception as e:
        logger.error(f"Failed to check xianyu login status: {e}")
        return {"status": "failed", "msg": str(e)}

@app.post("/api/system/xianyu_login_trigger")
async def trigger_xianyu_login(payload: dict = None):
    global is_logging_in
    if is_logging_in:
        return {"status": "failed", "msg": "当前正在执行登录，请勿重复操作"}

    try:
        from xianyu_tools.config import settings
        raw_cfg = settings.get_openapi_raw_config()
        requested_account_id = (payload or {}).get("account_id")
        account_cfg = get_openapi_account(raw_cfg, requested_account_id or (raw_cfg or {}).get("active_account_id"))
        account_id = account_cfg.get("id")
    except Exception:
        account_id = None

    asyncio.create_task(run_xianyu_login_capture(account_id))
    return {"status": "success", "msg": "已启动闲鱼登录浏览器，请使用手机扫码完成安全登录"}

app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
