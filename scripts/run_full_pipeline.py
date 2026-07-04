import os, json, asyncio, re, csv, argparse, sys, pymysql, random, traceback, shlex
from datetime import datetime
from pathlib import Path

# --- 核心：导入统一日志工具 ---
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "src"))
from xianyu_tools.logging_util import get_unified_logger

async def run_command(cmd, logger):
    logger.info(f"Executing Subprocess: {cmd}")
    process = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()
    if stderr: logger.warning(f"Subprocess Stderr Output: {stderr.decode()}")
    return stdout.decode('utf-8', errors='ignore')

def sanitize_dir_name(name: str) -> str:
    clean = re.sub(r'\s+', '', str(name))
    return re.sub(r'[\\/:*?"<>|]', '_', clean).strip()[:60]


def load_runtime_filter_audit_snapshot(item_dir: Path, fallback_snapshot: dict | None = None) -> dict:
    fallback_snapshot = fallback_snapshot if isinstance(fallback_snapshot, dict) else {}
    audit_path = item_dir / "_channel_filter_runtime_snapshot.json"
    if not audit_path.exists():
        return fallback_snapshot
    try:
        payload = json.loads(audit_path.read_text(encoding="utf-8"))
    except Exception:
        return fallback_snapshot
    if not isinstance(payload, dict):
        return fallback_snapshot

    snapshot = payload.get("snapshot")
    if not isinstance(snapshot, dict):
        snapshot = payload
    try:
        from xianyu_tools.config import settings
        return settings.normalize_channel_search_filter_snapshot(snapshot)
    except Exception:
        return snapshot if isinstance(snapshot, dict) else fallback_snapshot


def select_source_filter_snapshot_for_db(
    *,
    audit_exists: bool,
    audit_snapshot: dict | None,
    summary_snapshot: dict | None,
    fallback_snapshot: dict | None,
) -> dict:
    if audit_exists and isinstance(audit_snapshot, dict) and audit_snapshot:
        return audit_snapshot
    if isinstance(summary_snapshot, dict) and summary_snapshot:
        return summary_snapshot
    if isinstance(fallback_snapshot, dict) and fallback_snapshot:
        return fallback_snapshot
    return {}


def get_effective_ali1688_runtime_context(rotation_index: int = 0) -> dict:
    try:
        from xianyu_tools.config import settings
        runtime_cfg = settings.get_effective_crawl_source_runtime("ali1688", rotation_index=rotation_index)
        if not runtime_cfg:
            runtime_cfg = settings.get_active_ali1688_runtime_config()
        filter_snapshot = settings.get_channel_search_filter_snapshot(
            channel_id=runtime_cfg.get("channel_id") or "ali1688",
            channel_type="ali1688",
        )
        return {
            "state_file": runtime_cfg.get("state_file") or "",
            "source_channel_type": runtime_cfg.get("channel_type") or "ali1688",
            "source_channel_id": runtime_cfg.get("channel_id") or "ali1688",
            "source_channel_label": runtime_cfg.get("channel_label") or "1688 货源渠道",
            "source_account_id": runtime_cfg.get("account_id") or "",
            "source_account_label": runtime_cfg.get("account_label") or runtime_cfg.get("label") or "",
            "source_filter_snapshot": filter_snapshot,
        }
    except Exception:
        from xianyu_tools.config import settings
        return {
            "state_file": "",
            "source_channel_type": "ali1688",
            "source_channel_id": "ali1688",
            "source_channel_label": "1688 货源渠道",
            "source_account_id": "",
            "source_account_label": "",
            "source_filter_snapshot": settings.normalize_channel_search_filter_snapshot({
                "channel_id": "ali1688",
                "channel_type": "ali1688",
                "filters": {},
                "mapping_stage": "snapshot_only",
            }),
        }


def validate_active_ali1688_runtime() -> tuple[bool, str]:
    try:
        from xianyu_tools.config import settings

        runtime_candidates = settings.get_crawl_source_account_runtimes("ali1688", only_usable=True)
        if not runtime_candidates:
            runtime_cfg = settings.get_active_ali1688_runtime_config()
            return False, runtime_cfg.get("error_message") or "未配置可用的 1688 货源渠道账号"
        return True, ""
    except Exception as exc:
        return False, f"校验激活 1688 账号失败：{exc}"

def get_db_conn():
    from xianyu_tools.config import settings
    config = settings.get_database_config()
    config["cursorclass"] = pymysql.cursors.DictCursor
    return pymysql.connect(**config)

def init_db_schema():
    try:
        conn = get_db_conn()
        cursor = conn.cursor()
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
        cursor.execute("DROP TABLE IF EXISTS ali1688_source_htmls;")
        try:
            cursor.execute("ALTER TABLE ali1688_sources ADD COLUMN html_path VARCHAR(1024) DEFAULT '';")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE ali1688_sources ADD COLUMN source_channel_id VARCHAR(100) DEFAULT 'ali1688';")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE ali1688_sources ADD COLUMN source_channel_type VARCHAR(100) DEFAULT 'ali1688';")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE ali1688_sources ADD COLUMN source_channel_label VARCHAR(255) DEFAULT '1688 货源渠道';")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE ali1688_sources ADD COLUMN source_account_id VARCHAR(100) DEFAULT '';")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE ali1688_sources ADD COLUMN source_account_label VARCHAR(255) DEFAULT '';")
        except Exception:
            pass
        for ddl in (
            "ALTER TABLE ali1688_sources ADD COLUMN pickup_48h_text VARCHAR(64) DEFAULT '';",
            "ALTER TABLE ali1688_sources ADD COLUMN pickup_24h_text VARCHAR(64) DEFAULT '';",
            "ALTER TABLE ali1688_sources ADD COLUMN month_dispatch_text VARCHAR(64) DEFAULT '';",
            "ALTER TABLE ali1688_sources ADD COLUMN seven_day_dispatch_text VARCHAR(64) DEFAULT '';",
            "ALTER TABLE ali1688_sources ADD COLUMN listing_count_text VARCHAR(64) DEFAULT '';",
            "ALTER TABLE ali1688_sources ADD COLUMN distributor_count_text VARCHAR(64) DEFAULT '';",
            "ALTER TABLE ali1688_sources ADD COLUMN waybill_support_text VARCHAR(64) DEFAULT '';",
            "ALTER TABLE ali1688_sources ADD COLUMN settled_years_text VARCHAR(64) DEFAULT '';",
            "ALTER TABLE ali1688_sources ADD COLUMN company_name VARCHAR(255) DEFAULT '';",
            "ALTER TABLE ali1688_sources ADD COLUMN page_original_index INT DEFAULT 0;",
            "ALTER TABLE ali1688_sources ADD COLUMN month_dispatch_count INT DEFAULT 0;",
            "ALTER TABLE ali1688_sources ADD COLUMN seven_day_dispatch_count INT DEFAULT 0;",
            "ALTER TABLE ali1688_sources ADD COLUMN listing_count INT DEFAULT 0;",
            "ALTER TABLE ali1688_sources ADD COLUMN distributor_count INT DEFAULT 0;",
            "ALTER TABLE ali1688_sources ADD COLUMN source_filter_snapshot_json TEXT DEFAULT NULL;",
        ):
            try:
                cursor.execute(ddl)
            except Exception:
                pass
        try:
            cursor.execute("ALTER TABLE tasks ADD COLUMN input_type VARCHAR(20) DEFAULT 'keyword';")
        except Exception:
            pass
        conn.commit()
        conn.close()
    except Exception:
        pass

# 执行创表自愈
init_db_schema()

def extract_json(text):
    try:
        import re
        match = re.search(r'(\{.*"(?:hot_items|error)".*\})', text, re.DOTALL)
        if match: return match.group(1)
    except: pass
    return text

def run_ai_arbitration_for_source(source_title: str, search_keyword: str, logger, task_id=None) -> tuple[bool, str, int]:
    """
    同品类三级漏斗判定逻辑，返回 (是否相关, 不相关原因, 消耗的token数)
    """
    if not search_keyword:
        return True, "", 0
        
    s_title = str(source_title).lower()
    clean_keyword = re.sub(r'\s+', '', str(search_keyword)).lower()
    
    # 1. 规则初筛
    if clean_keyword in s_title:
        return True, "", 0
    core_parts = [clean_keyword[:2], clean_keyword[-2:], clean_keyword[1:3]]
    for part in core_parts:
        if len(part) >= 2 and part in s_title:
            return True, "", 0
            
    # 2. AI 仲裁
    logger.info(f"[AI Arbitration] Auditing: '{source_title}' against keyword '{search_keyword}'")
    try:
        from xianyu_tools.llm_util import ask_llm_relevance_with_usage
        ai_ok, tokens = ask_llm_relevance_with_usage(source_title, search_keyword, task_id=task_id, external_logger=logger)
        if ai_ok is True:
            return True, "", tokens
        elif ai_ok is False:
            return False, "AI判定不相关", tokens
    except Exception as e:
        logger.error(f"[AI Arbitration] Failed to run LLM relevance check: {e}")
        
    return False, f"不含关键词 '{clean_keyword}'", 0

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--task-id", required=False)
    args = parser.parse_args()
    
    keyword, task_id = args.keyword.replace("'", ""), args.task_id
    python_path = sys.executable
    Task = None; checkpoint = {}; root_dir = None

    if task_id:
        try:
            from web_api.main import Task
            conn = get_db_conn(); cursor = conn.cursor()
            cursor.execute("SELECT root_dir, checkpoint FROM tasks WHERE id = %s", (task_id,))
            row = cursor.fetchone(); conn.close()
            if row:
                root_dir = Path(row['root_dir'])
                checkpoint = json.loads(row['checkpoint']) if row['checkpoint'] else {}
        except: pass

    if not root_dir:
        root_dir = Path("outputs") / f"{sanitize_dir_name(keyword)}_{datetime.now().strftime('%Y%m%d')}"
    root_dir.mkdir(parents=True, exist_ok=True)
    log_file_path = root_dir / "task.log"
    logger = get_unified_logger("Pipeline", log_file=str(log_file_path))

    # --- 1. 闲鱼扫描 ---
    cur_phase = checkpoint.get("phase", 1)
    xianyu_json_path = root_dir / "xianyu_hot_items.json"
    if cur_phase > 1 and xianyu_json_path.exists():
        logger.info("[Phase 1] Checkpoint hit. Skip scan.")
        raw_output = xianyu_json_path.read_text()
    else:
        logger.info("[Phase 1] Starting Scan...")
        if Task: Task.update(task_id, msg="闲鱼扫描中...", progress=10)
        cmd_xianyu = f"export PYTHONPATH=$PYTHONPATH:{BASE_DIR}/src && {python_path} scripts/run_xianyu_hot_items.py --keyword '{keyword}' --state-file xianyu_state.json --max-pages 1 --top-n 10 --log-file '{log_file_path}'"
        full_output = await run_command(cmd_xianyu, logger)
        raw_output = extract_json(full_output)
        try:
            parsed_data = json.loads(raw_output)
            if "error" in parsed_data:
                err_msg = parsed_data.get("msg", "扫描闲鱼发生异常")
                logger.error(f"[Phase 1] Xianyu scan failed: {err_msg}")
                if Task: Task.update(task_id, status="失败", msg=err_msg)
                return
            xianyu_json_path.write_text(raw_output)
            if Task and task_id:
                try:
                    from scripts.run_xianyu_hot_items import detect_input_type
                    in_type = detect_input_type(keyword)
                    if in_type == 'url' and parsed_data.get("hot_items"):
                        resolved_title = parsed_data["hot_items"][0].get("title")
                        if resolved_title:
                            Task.update(task_id, keyword=resolved_title)
                            logger.info(f"Successfully updated task keyword to product title: {resolved_title}")
                except Exception as ue:
                    logger.error(f"Failed to update task keyword to title: {ue}")
            if Task: Task.update(task_id, checkpoint=json.dumps({"phase": 2, "processed_rank": 0}))
        except Exception as e:
            logger.error(f"[Phase 1] Failed to parse JSON. Error: {e}")
            fallback_msg = "解析闲鱼数据失败，子进程输出格式错误"
            if "timeout" in raw_output.lower() or "timeout" in str(e).lower():
                fallback_msg = "扫描闲鱼超时，网络连接异常"
            if Task: Task.update(task_id, status="失败", msg=fallback_msg)
            return

    try:
        hot_items = json.loads(raw_output).get("hot_items", [])
        if not hot_items:
            if Task: Task.update(task_id, status="失败", msg="未获取到任何宝贝数据")
            return
    except Exception as e:
        logger.error(f"Failed to load hot items from json: {e}")
        if Task: Task.update(task_id, status="失败", msg="宝贝数据解析异常")
        return

    # --- 资产初始化 ---
    db_item_ids = {}
    if task_id:
        conn = get_db_conn(); cursor = conn.cursor()
        cursor.execute("SELECT id, rank_index FROM xianyu_items WHERE task_id = %s", (task_id,))
        db_items = cursor.fetchall()
        if not db_items:
            for i, item in enumerate(hot_items, start=1):
                cursor.execute("INSERT INTO xianyu_items (task_id, rank_index, title, price, image_url, want_count, item_url) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                             (task_id, i, item.get('title'), item.get('price'), item.get('image_url'), item.get('want_count'), item.get('item_url')))
                db_item_ids[i] = cursor.lastrowid
            conn.commit()
        else:
            db_item_ids = {row['rank_index']: row['id'] for row in db_items}
        conn.close()

    # --- 1688 账号运行前校验 ---
    ali1688_ok, ali1688_error = validate_active_ali1688_runtime()
    if not ali1688_ok:
        logger.error(f"[Phase 2] {ali1688_error}")
        if Task:
            Task.update(task_id, status="失败", msg=ali1688_error)
        return
    # --- 2. 1688 深度验证 ---
    processed_rank = checkpoint.get("processed_rank", 0)
    for i, item in enumerate(hot_items, start=1):
        if i <= processed_rank: continue

        # 暂停自检
        if task_id:
            try:
                _c = get_db_conn(); _cur = _c.cursor()
                _cur.execute("SELECT status FROM tasks WHERE id = %s", (task_id,))
                _s = (_cur.fetchone() or {}).get('status'); _c.close()
                if _s == "正在暂停": return
            except: pass

        msg = f"处理爆款 {i}/{len(hot_items)}..."
        logger.info(f"[Phase 2] {msg}")
        if Task: Task.update(task_id, progress=30 + int((i/len(hot_items))*60), msg=msg)
        
        item_dir = root_dir / f"Rank_{i}_{sanitize_dir_name(item.get('title', 'item'))}"
        item_dir.mkdir(parents=True, exist_ok=True)
        # 动态获取系统配置中的商品爬取数配置限制
        try:
            from xianyu_tools.config import settings
            crawl_cfg = settings.get_crawl_config()
            source_limit = crawl_cfg.get("source_limit_1688", 10)
        except Exception:
            source_limit = 10

        runtime_context = get_effective_ali1688_runtime_context(rotation_index=i - 1)
        ali1688_state_file = runtime_context.get("state_file") or ""
        filter_snapshot_file = item_dir / "_channel_filter_snapshot.json"
        filter_snapshot_file.write_text(
            json.dumps(runtime_context.get("source_filter_snapshot") or {}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        cmd_1688 = (
            f"export PYTHONPATH=$PYTHONPATH:{BASE_DIR}/src && "
            f"{shlex.quote(python_path)} scripts/run_ali1688_slow_flow.py "
            f"--image-url {shlex.quote(str(item.get('image_url') or ''))} "
            f"--output-dir {shlex.quote(str(item_dir))} "
            f"--state-file {shlex.quote(str(ali1688_state_file))} "
            f"--channel-filter-snapshot-file {shlex.quote(str(filter_snapshot_file))} "
            f"--detail-top-n {int(source_limit)} "
            f"--target-keyword {shlex.quote(str(keyword))} "
            f"--log-file {shlex.quote(str(log_file_path))}"
        )
        await run_command(cmd_1688, logger)
        runtime_filter_audit_snapshot = load_runtime_filter_audit_snapshot(
            item_dir,
            runtime_context.get("source_filter_snapshot") or {},
        )
        runtime_filter_audit_path = item_dir / "_channel_filter_runtime_snapshot.json"
        runtime_filter_audit_exists = runtime_filter_audit_path.exists()
        runtime_filter_audit_stage = ""
        if runtime_filter_audit_exists:
            try:
                runtime_filter_audit_payload = json.loads(runtime_filter_audit_path.read_text(encoding="utf-8"))
                if isinstance(runtime_filter_audit_payload, dict):
                    runtime_filter_audit_stage = str(runtime_filter_audit_payload.get("stage") or "")
            except Exception:
                runtime_filter_audit_stage = ""
            logger.info(
                "[Phase 2] Loaded channel filter runtime audit snapshot: %s",
                {
                    "rank": i,
                    "stage": runtime_filter_audit_stage,
                    "path": str(runtime_filter_audit_path),
                    "applied_filter_keys": runtime_filter_audit_snapshot.get("applied_filter_keys") or [],
                    "unapplied_filter_keys": runtime_filter_audit_snapshot.get("unapplied_filter_keys") or [],
                },
            )
        
        # --- 资产入库 (全方位日志埋点版) ---
        if task_id and i in db_item_ids:
            item_db_id = db_item_ids[i]
            logger.info(f"[Sync-DB] Start sync for Rank {i} (ItemDBID: {item_db_id})")
            _conn = get_db_conn(); _cursor = _conn.cursor()
            try:
                summary_path = item_dir / "summary.json"
                logger.info(f"[Sync-DB] Checking file: {summary_path}")
                
                # 1. 删除旧数据时物理清理旧 HTML 文件
                try:
                    _cursor.execute("SELECT html_path FROM ali1688_sources WHERE task_id = %s AND item_id = %s", (task_id, item_db_id))
                    old_sources = _cursor.fetchall()
                    for os_rec in old_sources:
                        if os_rec.get("html_path"):
                            p = BASE_DIR / os_rec["html_path"] if not Path(os_rec["html_path"]).is_absolute() else Path(os_rec["html_path"])
                            if p.exists() and p.is_file():
                                p.unlink()
                                logger.info(f"[Sync-DB] Physically deleted old local HTML: {p}")
                except Exception as clean_err:
                    logger.warning(f"[Sync-DB] Failed to clean old HTML files: {clean_err}")

                _cursor.execute("DELETE FROM ali1688_sources WHERE task_id = %s AND item_id = %s", (task_id, item_db_id))
                logger.info(f"[Sync-DB] Old records cleared for Task:{task_id}")
                
                if summary_path.exists():
                    results = json.loads(summary_path.read_text())
                    logger.info(f"[Sync-DB] Loaded {len(results)} source candidates from summary.json")
                    
                    count = 0
                    total_task_tokens = 0
                    for res in results:
                        offer_id = res['offer_id']
                        img_json = json.dumps(res.get("images", []), ensure_ascii=False)
                        min_price = res.get('min_price', 0); sku_count = 0
                        
                        # 从内存 JSON 提取 SKU 规格和价格数据
                        sku_items = res.get("sku_items", [])
                        if sku_items:
                            prices = [float(s.get("price") or 0.0) for s in sku_items if s.get("price") is not None]
                            if prices:
                                min_price = min(prices)
                            sku_count = len(sku_items)
                        
                        # 计算本地 HTML 相对路径以建立对应关系
                        html_file = item_dir / f"detail_{offer_id}.html"
                        html_rel_path = ""
                        if html_file.exists():
                            try:
                                html_rel_path = str(html_file.relative_to(BASE_DIR))
                            except Exception:
                                html_rel_path = str(html_file.resolve())

                        # 进行 AI 同品类仲裁
                        final_drop_reason = res.get('drop_reason')
                        if not final_drop_reason:
                            is_ok, reject_reason, tokens_used = run_ai_arbitration_for_source(res['title'], keyword, logger, task_id=task_id)
                            total_task_tokens += tokens_used
                            if not is_ok:
                                final_drop_reason = reject_reason

                        # 执行插入
                        logger.info(f"[Sync-DB] Inserting source: {res['title'][:20]} (Price: {min_price})")
                        _cursor.execute("""
                            INSERT INTO ali1688_sources (
                                item_id, task_id, title, offer_id, min_price, sku_count, source_url, images,
                                drop_reason, html_path, source_channel_id, source_channel_type, source_channel_label, source_account_id, source_account_label,
                                pickup_48h_text, pickup_24h_text, month_dispatch_text, seven_day_dispatch_text,
                                listing_count_text, distributor_count_text, waybill_support_text, settled_years_text, company_name,
                                page_original_index, source_filter_snapshot_json,
                                month_dispatch_count, seven_day_dispatch_count, listing_count, distributor_count
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            item_db_id,
                            task_id,
                            res['title'],
                            offer_id,
                            min_price,
                            sku_count,
                            res['item_url'],
                            img_json,
                            final_drop_reason,
                            html_rel_path,
                            runtime_context["source_channel_id"],
                            runtime_context["source_channel_type"],
                            runtime_context["source_channel_label"],
                            runtime_context["source_account_id"],
                            runtime_context["source_account_label"],
                            res.get("pickup_48h_text", ""),
                            res.get("pickup_24h_text", ""),
                            res.get("month_dispatch_text", ""),
                            res.get("seven_day_dispatch_text", ""),
                            res.get("listing_count_text", ""),
                            res.get("distributor_count_text", ""),
                            res.get("waybill_support_text", ""),
                            res.get("settled_years_text", ""),
                            res.get("company_name", ""),
                            int(res.get("page_original_index") or 0),
                            json.dumps(
                                select_source_filter_snapshot_for_db(
                                    audit_exists=runtime_filter_audit_exists,
                                    audit_snapshot=runtime_filter_audit_snapshot,
                                    summary_snapshot=res.get("source_filter_snapshot"),
                                    fallback_snapshot=runtime_context.get("source_filter_snapshot"),
                                ),
                                ensure_ascii=False,
                            ),
                            int(res.get("month_dispatch_count") or 0),
                            int(res.get("seven_day_dispatch_count") or 0),
                            int(res.get("listing_count") or 0),
                            int(res.get("distributor_count") or 0),
                        ))
                        source_id = _cursor.lastrowid

                        # 2. 写入 SKU 到数据库 (ali1688_skus 表)
                        if sku_items:
                            try:
                                # 先清空该货源下已有的旧 SKU
                                _cursor.execute("DELETE FROM ali1688_skus WHERE source_id = %s", (source_id,))

                                for sku in sku_items:
                                    sku_text = str(sku.get("attributes") or "")
                                    price = float(sku.get("price")) if sku.get("price") is not None else 0.0
                                    stock = int(sku.get("stock")) if sku.get("stock") is not None else 0
                                    spec_id = str(sku.get("spec_id") or "")
                                    image = str(sku.get("image") or "")

                                    _cursor.execute("""
                                        INSERT INTO ali1688_skus (source_id, sku_text, price, stock, spec_id, image)
                                        VALUES (%s, %s, %s, %s, %s, %s)
                                    """, (source_id, sku_text, price, stock, spec_id, image))
                                logger.info(f"[Sync-DB] Imported {len(sku_items)} SKUs into database for source_id: {source_id}")
                            except Exception as db_sku_err:
                                logger.error(f"[Sync-DB] Failed to import SKUs to database: {db_sku_err}")

                        count += 1
                    
                    _conn.commit()
                    logger.info(f"[Sync-DB] Transaction Committed. Total {count} rows added.")

                    if total_task_tokens > 0 and task_id:
                        logger.info(f"[Sync-DB] AI relevance checks ran for this sync. Total AI tokens: {total_task_tokens} (already synced inside llm_util)")
                else:
                    logger.warning(
                        "[Sync-DB] summary.json NOT FOUND in %s; latest channel filter audit stage=%s",
                        item_dir,
                        runtime_filter_audit_stage or "unknown",
                    )
                
                # 更新进度
                _cursor.execute("UPDATE tasks SET checkpoint = %s WHERE id = %s", (json.dumps({"phase": 2, "processed_rank": i}), task_id))
                _conn.commit()
            except Exception as e:
                logger.error(f"[Sync-DB] CRITICAL ERROR at Rank {i}:")
                logger.error(traceback.format_exc())
            finally:
                _conn.close()

        # 冷却
        step_wait = random.uniform(3.0, 8.0)
        logger.info(f"[Cooling] Sleep {step_wait:.1f}s...")
        await asyncio.sleep(step_wait)

    if Task: Task.update(task_id, status="已完成", progress=100, msg="分析完成")

if __name__ == "__main__":
    asyncio.run(main())
