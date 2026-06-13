import json
import requests
import os
import sys
import logging
from pathlib import Path

from xianyu_tools.logging_util import get_unified_logger
from xianyu_tools.config import settings

# --- 日志配置 ---
logger = get_unified_logger("LLMUtil")

# 记录每个配置项（Key）当前使用的模型索引
_model_indices = {}
_global_model_index = 0

def load_llm_configs():
    """支持读取单个配置或配置列表"""
    try:
        return settings.get_llm_config()
    except Exception as e:
        logger.error(f"Error loading LLM configs: {e}")
        return []

def record_token_usage(feature: str, model: str, prompt_tokens: int, completion_tokens: int, total_tokens: int, task_id: str = None):
    """
    记录一次大模型调用的 Token 消耗详情
    """
    try:
        import pymysql
        config = settings.get_database_config()
        if not config:
            return
        conn = pymysql.connect(**config)
        cursor = conn.cursor()
        
        # 1. 插入明细日志到数据库
        cursor.execute("""
            INSERT INTO llm_token_logs (task_id, feature, model, prompt_tokens, completion_tokens, total_tokens)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (task_id, feature, model, prompt_tokens, completion_tokens, total_tokens))
        
        # 2. 如果关联了任务，累加该任务的 total_tokens
        if task_id:
            try:
                cursor.execute("UPDATE tasks SET total_tokens = total_tokens + %s WHERE id = %s", (total_tokens, task_id))
            except Exception as e:
                logger.warning(f"Failed to increment task total_tokens in record_token_usage: {e}")
                
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to record token usage in DB: {e}")

def ask_llm_relevance_with_usage(source_title, search_keyword, task_id=None, feature="source_relevance", external_logger=None):
    """
    模型级轮询判定，支持外部 Logger 透传，返回 (是否相关, 本次消耗token)
    """
    # 优先使用透传的 logger，否则使用模块内置的 logger
    log = external_logger or logger

    configs = load_llm_configs()
    if not configs:
        return None, 0

    # 1. 读取系统配置中商品筛选使用的模型
    try:
        crawl_cfg = settings.get_crawl_config()
        allowed_models = crawl_cfg.get("source_filter_models", [])
    except Exception:
        allowed_models = []

    # 2. 扁平化可用配置的每一个厂商里的模型
    flat_models = []
    for cfg_idx, cfg in enumerate(configs):
        api_key = cfg.get("api_key")
        base_url = cfg.get("base_url")
        raw_model = cfg.get("model")
        raw_models = cfg.get("models")
        
        models = []
        if isinstance(raw_models, list):
            models = raw_models
        elif isinstance(raw_model, list):
            models = raw_model
        elif isinstance(raw_model, str):
            models = [raw_model]
        
        if not api_key or not models:
            continue
            
        for m in models:
            if isinstance(m, str) and m.strip():
                flat_models.append({
                    "model": m.strip(),
                    "api_key": api_key,
                    "base_url": base_url,
                    "cfg_idx": cfg_idx
                })

    # 3. 按指定的模型子集过滤
    target_models = flat_models
    if allowed_models:
        target_models = [item for item in flat_models if item["model"] in allowed_models]
        if not target_models:
            log.warning(f"[AI Audit] Allowed models subset {allowed_models} not found in available configurations, falling back to all available models.")
            target_models = flat_models

    if not target_models:
        log.error("[AI Audit] No active LLM configurations or models found for reasoning.")
        return None, 0

    global _global_model_index
    
    # 4. 全局跨厂商模型轮询与容灾机制
    for _ in range(len(target_models)):
        current_cfg = target_models[_global_model_index % len(target_models)]
        _global_model_index += 1 # 全局跨厂商模型轮询
        
        current_model = current_cfg["model"]
        api_key = current_cfg["api_key"]
        base_url = current_cfg["base_url"]

        prompt = f"""你是一个电商选品专家。请判断下面的 1688 商品是否为用户真正想要找的“核心品类商品”。
用户搜索意图: "{search_keyword}"
1688 商品标题: "{source_title}"
判定准则: 1.是主品类返回 "YES"；2.是配件、周边或无关项返回 "NO"。只返回 YES/NO。"""

        log.info("-" * 20)
        log.info(f"[AI Audit] Model: {current_model}")
        log.info(f"[AI Input]: {search_keyword} -> {source_title}")
        
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            data = {
                "model": current_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1
            }
            response = requests.post(f"{base_url}/chat/completions", headers=headers, json=data, timeout=15)
            res_json = response.json()
            
            if 'error' in res_json:
                log.error(f"[AI Error] {current_model}: {res_json['error'].get('message')}")
                continue

            raw_content = res_json['choices'][0]['message']['content'].strip()
            usage = res_json.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", 0)
            
            log.info(f"[AI Result]: {raw_content} (Prompt: {prompt_tokens}, Completion: {completion_tokens}, Total: {total_tokens})")
            log.info("-" * 20)

            # 自动落库记录与累加
            record_token_usage(feature, current_model, prompt_tokens, completion_tokens, total_tokens, task_id)

            return "YES" in raw_content.upper(), total_tokens
        except Exception as e:
            log.warning(f"[AI Failed] {current_model}: {e}")
            continue

    return None, 0

def ask_llm_relevance(source_title, search_keyword, external_logger=None):
    res, _ = ask_llm_relevance_with_usage(source_title, search_keyword, external_logger=external_logger)
    return res
