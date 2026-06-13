import hashlib
import json
import time
from typing import Dict, Any, Union

class APISigner:
    @staticmethod
    def calculate_md5(text: str) -> str:
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    @staticmethod
    def sign_v3_protocol(body_dict: Dict[str, Any], app_key: str, app_secret: str, timestamp: Union[int, str] = None) -> Dict[str, str]:
        if app_key:
            app_key = str(app_key).strip()
        if app_secret:
            app_secret = str(app_secret).strip()
            
        if timestamp is None:
            timestamp = int(time.time())
        
        # 修正 2：强制使用紧凑 JSON (移除逗号和冒号后的空格)
        body_json = json.dumps(body_dict, separators=(',', ':'), ensure_ascii=False) 
        body_md5 = APISigner.calculate_md5(body_json)

        # 构造待签名字符串
        sign_source = f"{app_key},{body_md5},{timestamp},{app_secret}"
        signature = APISigner.calculate_md5(sign_source)

        return {
            "app_key": app_key,
            "body_md5": body_md5,
            "timestamp": str(timestamp),
            "sign": signature
        }
