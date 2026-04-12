import json
import requests
import os
from pathlib import Path

# 记录每个配置项（Key）当前使用的模型索引
_model_indices = {}

def load_llm_configs():
    config_path = Path(__file__).resolve().parents[2] / "config" / "llm.json"
    if not config_path.exists(): return []
    try:
        with open(config_path, "r") as f:
            data = json.load(f)
            return data if isinstance(data, list) else [data]
    except Exception as e:
        print(f"Error loading llm.json: {e}")
        return []

def ask_llm_relevance(source_title, search_keyword):
    """
    模型级轮询判定：兼容单 model 字符串、单 model 列表、以及复数 models 列表
    """
    configs = load_llm_configs()
    if not configs: return None

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
            models = raw_model # 命中您的配置情况
        elif isinstance(raw_model, str):
            models = [raw_model]
        
        if not api_key or not models: continue

        if cfg_idx not in _model_indices: _model_indices[cfg_idx] = 0
        
        # 依次尝试该 Key 下的每一个模型
        for _ in range(len(models)):
            current_model = models[_model_indices[cfg_idx] % len(models)]
            _model_indices[cfg_idx] += 1
            
            # 严格确保 current_model 是字符串
            if not isinstance(current_model, str): continue

            print(f"    [AI Poll] Using Key: {api_key[:8]}... with Model: {current_model}")
            
            prompt = f"""
            你是一个电商选品专家。请判断下面的 1688 商品是否为用户真正想要找的“核心品类商品”。
            用户搜索意图: "{search_keyword}"
            1688 商品标题: "{source_title}"
            判定准则: 1.是主品类返回 "YES"；2.是配件、周边或无关项返回 "NO"。只返回 YES/NO。
            """
            
            try:
                headers = { "Content-Type": "application/json", "Authorization": f"Bearer {api_key}" }
                data = {
                    "model": current_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1
                }
                response = requests.post(f"{base_url}/chat/completions", headers=headers, json=data, timeout=15)
                res_json = response.json()
                
                if 'error' in res_json:
                    print(f"    [AI Poll] Model {current_model} Error: {res_json['error'].get('message')}. Trying next...")
                    continue

                result = res_json['choices'][0]['message']['content'].strip().upper()
                return "YES" in result
            except Exception as e:
                print(f"    [AI Poll] Request Failed for {current_model}: {e}")
                continue
                
    return None 
