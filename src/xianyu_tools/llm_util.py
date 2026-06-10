import json
import requests
import os
import sys
import logging
from pathlib import Path

from xianyu_tools.logging_util import get_unified_logger

# --- 日志配置 ---
logger = get_unified_logger("LLMUtil")

# 记录每个配置项（Key）当前使用的模型索引
_model_indices = {}

def load_llm_configs():
    """支持读取单个配置或配置列表"""
    config_path = Path(__file__).resolve().parents[2] / "config" / "llm.json"
    if not config_path.exists():
        return []
    
    try:
        with open(config_path, "r") as f:
            data = json.load(f)
            # 如果是列表，直接返回；如果是字典，包裹成列表
            return data if isinstance(data, list) else [data]
    except Exception as e:
        logger.error(f"Error loading llm.json: {e}")
        return []

def record_token_usage(feature: str, model: str, prompt_tokens: int, completion_tokens: int, total_tokens: int, task_id: str = None):
    """
    记录一次大模型调用的 Token 消耗详情
    """
    try:
        import pymysql
        config_path = Path(__file__).resolve().parents[2] / "config" / "database.json"
        if not config_path.exists():
            return
        config = json.load(open(config_path))
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

    # 遍历所有配置项（每个配置对应一个厂商/Key）
    for cfg_idx, cfg in enumerate(configs):
        api_key = cfg.get("api_key")
        base_url = cfg.get("base_url")
        
        # 兼容性处理：尝试获取模型列表
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

        # 初始化模型索引
        if cfg_idx not in _model_indices:
            _model_indices[cfg_idx] = 0
        
        # 尝试该 Key 下的每一个模型
        for _ in range(len(models)):
            current_model = models[_model_indices[cfg_idx] % len(models)]
            _model_indices[cfg_idx] += 1 # 模型级轮询
            
            if not isinstance(current_model, str):
                continue

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
