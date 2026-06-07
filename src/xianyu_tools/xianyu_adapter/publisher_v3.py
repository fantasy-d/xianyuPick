import json
import requests
import time
import logging
from pathlib import Path
from typing import Dict, Any, List
from xianyu_tools.signer import APISigner
from xianyu_tools.logging_util import get_unified_logger

logger = get_unified_logger("PublisherV3")

class PublisherV3:
    def __init__(self, config_path: str = "config/openapi.json"):
        self.config_path = Path(config_path)
        if not self.config_path.exists():
            raise FileNotFoundError(f"OpenAPI config not found at {config_path}")
        
        self.conf = json.loads(self.config_path.read_text())
        self.base_url = self.conf.get("base_url", "https://open.goofish.pro")
        self.appid = self.conf.get("appid")
        self.app_secret = self.conf.get("app_secret")
        self.defaults = self.conf.get("default_config", {})

    def _load_categories(self) -> List[Dict[str, Any]]:
        """
        加载类目列表。如果本地缓存 `config/xianyu_categories.json` 存在且内容不为空，则从本地读取；
        否则通过 `/api/open/product/category/list` 接口从开放平台拉取，并缓存到本地。
        """
        from typing import List, Dict
        cache_path = Path("config/xianyu_categories.json")
        if cache_path.exists():
            try:
                data = json.loads(cache_path.read_text(encoding="utf-8"))
                if isinstance(data, list) and len(data) > 0:
                    return data
            except Exception as e:
                logger.warning(f"Failed to read category cache: {e}")
                
        # 否则去调接口拉取
        payload = {
            "item_biz_type": 2,
            "sp_biz_type": 2
        }
        timestamp = int(time.time())
        try:
            auth = APISigner.sign_v3_protocol(payload, self.appid, self.app_secret, timestamp)
            target_url = f"{self.base_url}/api/open/product/category/list"
            query_params = {
                "appid": auth['app_key'],
                "timestamp": auth['timestamp'],
                "sign": auth['sign']
            }
            compact_body = json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
            headers = {"Content-Type": "application/json"}
            resp = requests.post(target_url, params=query_params, data=compact_body.encode('utf-8'), headers=headers, timeout=20)
            res = resp.json()
            if res.get("code") == 0:
                cat_list = res.get("data", {}).get("list", [])
                if cat_list:
                    # 写入缓存
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_text(json.dumps(cat_list, ensure_ascii=False, indent=4), encoding="utf-8")
                    return cat_list
        except Exception as e:
            logger.error(f"Failed to fetch category list from platform: {e}")
            
        return []

    def _match_category(self, title: str) -> str:
        """
        根据商品标题在已有的类目列表中进行模糊匹配。
        匹配规则：
        - 查找所有其名称 (channel_cat_name) 在标题中出现过的类目。
        - 如果找到了匹配项，按照类目名称长度降序排列，优先选择名字最长（即最精确）的分类。
        - 如果未找到任何匹配，返回 openapi.json 中的默认 channel_cat_id。
        """
        default_cat = self.defaults.get("channel_cat_id")
        if not title:
            return default_cat
            
        categories = self._load_categories()
        if not categories:
            return default_cat
            
        # 标准化标题：转小写，去除空格
        clean_title = title.lower().replace(" ", "")
        
        matches = []
        for cat in categories:
            cat_name = cat.get("channel_cat_name", "")
            if not cat_name:
                continue
            cat_name_lower = cat_name.lower()
            
            # 支持复合词的匹配：如果类目名包含 "/", 如 "平衡垫/球/盘"，我们按 "/" 拆分匹配任意一个
            if "/" in cat_name_lower:
                sub_names = cat_name_lower.split("/")
                for sub in sub_names:
                    sub = sub.strip()
                    if sub and sub in clean_title:
                        matches.append((cat.get("channel_cat_id"), len(sub)))
            else:
                if cat_name_lower in clean_title:
                    matches.append((cat.get("channel_cat_id"), len(cat_name_lower)))
                    
        if matches:
            # 按照匹配名字的长度降序排列，取长度最长的一个
            matches.sort(key=lambda x: x[1], reverse=True)
            matched_id = matches[0][0]
            logger.info(f"Matched category for title '{title[:15]}...': {matched_id}")
            return matched_id
            
        return default_cat

    def _format_sku_text(self, text: str) -> str:
        """将规格属性标准化为 '属性名:属性值;属性名2:属性值2' 格式，并限制每项在 1-20 字内"""
        if not text:
            return "规格:默认"
        import re
        # 剥离可能夹带的 <span> 标签及 HTML 垃圾内容
        text = re.sub(r'<span[^>]*?>.*?</span>', '', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'<[^>]+>', '', text)
        parts = text.split(";")
        formatted_parts = []
        for idx, part in enumerate(parts):
            part = part.strip()
            if not part:
                continue
            if ":" in part:
                sub_parts = part.split(":", 1)
                prop_name = sub_parts[0].strip()[:4]
                prop_val = sub_parts[1].strip()[:20]
                if not prop_val:
                    prop_val = "默认"
                formatted_parts.append(f"{prop_name}:{prop_val}")
            else:
                prop_name = f"规格{idx+1}" if len(parts) > 1 else "规格"
                prop_val = part[:20]
                if not prop_val:
                    prop_val = "默认"
                formatted_parts.append(f"{prop_name}:{prop_val}")
        if len(formatted_parts) > 2:
            formatted_parts = formatted_parts[:2]
        return ";".join(formatted_parts)

    def _align_sku_text(self, raw_text: str, valid_dimensions: List[str]) -> str:
        """根据计算出的有效公共维度规整化 SKU 规格文字，清洗敏感字符，确保维度和数量完全一致"""
        if not raw_text:
            raw_text = "默认"
        import re
        # 1. 剥离 <span> 等 HTML 垃圾内容
        raw_text = re.sub(r'<span[^>]*?>.*?</span>', '', raw_text, flags=re.IGNORECASE | re.DOTALL)
        raw_text = re.sub(r'<[^>]+>', '', raw_text)
        
        # 2. 将中文冒号和分号标准化为英文
        raw_text = raw_text.replace("；", ";").replace("：", ":")
        
        # 3. 如果没有 valid_dimensions，说明需要一维退化
        if not valid_dimensions:
            # 清洗整个文本中的冒号和分号，防止闲鱼二次误判
            clean_val = raw_text.replace(":", "-").replace(";", "-").strip()
            if not clean_val:
                clean_val = "默认"
            return f"规格:{clean_val[:20]}"
            
        # 4. 如果有 valid_dimensions，则需要根据其提取并重构
        parts = raw_text.split(";")
        kv_pairs = {}
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if ":" in part:
                k, v = part.split(":", 1)
                k, v = k.strip()[:4], v.strip()
            else:
                k, v = "规格", part.strip()
            kv_pairs[k] = v
            
        rebuilt_parts = []
        for dim in valid_dimensions:
            val = kv_pairs.get(dim)
            if val is None:
                val = "默认"
            # 清洗属性值中的冒号和分号
            val = val.replace(":", "-").replace(";", "-").strip()
            if not val:
                val = "默认"
            rebuilt_parts.append(f"{dim}:{val[:20]}")
            
        return ";".join(rebuilt_parts)

    def publish_item(self, source_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        第一步：创建商品 (Create)
        """
        images = source_data.get('images', [])
        if not images:
            return {"status": "failed", "msg": "系统未采集到该货源的图片，无法发布。请尝试重新扫描该商品。"}
        
        # 协议补全：确保所有图片都带 https:
        clean_images = []
        for img in images:
            if isinstance(img, str):
                if img.startswith("//"): img = "https:" + img
                elif not img.startswith("http"): img = "https://" + img
                clean_images.append(img)
        
        if not clean_images:
            return {"status": "failed", "msg": "有效的图片链接为空"}

        price_fen = int(float(source_data['price']) * 100)
        
        payload = {
            "item_biz_type": self.defaults.get("item_biz_type", 2),
            "sp_biz_type": self.defaults.get("sp_biz_type", 2),
            "channel_cat_id": self._match_category(source_data.get('title')),
            "price": price_fen,
            "original_price": price_fen + 5000,
            "express_fee": self.defaults.get("express_fee", 0),
            "stock": 10,
            "stuff_status": self.defaults.get("stuff_status", 100),
            "publish_shop": [{
                "user_name": self.defaults.get("user_name"),
                "province": self.defaults.get("province"),
                "city": self.defaults.get("city"),
                "district": self.defaults.get("district"),
                "title": source_data['title'][:60],
                "content": source_data['description'][:5000],
                "images": clean_images[:9] # 使用清洗后的图片
            }]
        }

        # 拼装多规格 SKU 信息
        sku_items_raw = source_data.get('sku_items', [])
        if len(sku_items_raw) >= 2:
            # 阶段 1：全局属性扫描，提取频次 >= 50% 的公共维度 (最多 2 个)
            import re
            dimension_counts = {}
            temp_parsed = []
            for item in sku_items_raw:
                raw_text = item.get('sku_text', '')
                if not raw_text:
                    raw_text = "默认"
                # 清除 HTML
                raw_text = re.sub(r'<span[^>]*?>.*?</span>', '', raw_text, flags=re.IGNORECASE | re.DOTALL)
                raw_text = re.sub(r'<[^>]+>', '', raw_text)
                raw_text = raw_text.replace("；", ";").replace("：", ":")
                
                parts = raw_text.split(";")
                item_dims = []
                for part in parts:
                    part = part.strip()
                    if not part:
                        continue
                    if ":" in part:
                        k = part.split(":", 1)[0].strip()[:4]
                    else:
                        k = "规格"
                    if k not in item_dims:
                        item_dims.append(k)
                        dimension_counts[k] = dimension_counts.get(k, 0) + 1
                temp_parsed.append((item, raw_text))

            # 筛选频次比例 >= 50% 的公共属性维度
            total_skus = len(sku_items_raw)
            valid_dimensions = []
            # 为了保持首次出现的物理顺序，我们根据第一个 SKU 出现的维度键来对齐
            ordered_dims_seen = []
            for item, raw_text in temp_parsed:
                parts = raw_text.split(";")
                for part in parts:
                    part = part.strip()
                    if not part:
                        continue
                    k = part.split(":", 1)[0].strip()[:4] if ":" in part else "规格"
                    if k not in ordered_dims_seen:
                        ordered_dims_seen.append(k)

            for k in ordered_dims_seen:
                if dimension_counts.get(k, 0) * 2 >= total_skus:
                    valid_dimensions.append(k)

            # 最多取前 2 个属性维度名
            valid_dimensions = valid_dimensions[:2]

            # 阶段 2：用 _align_sku_text 根据 valid_dimensions 重构每个 SKU 并去重自愈
            payload['sku_items'] = []
            total_stock = 0
            seen_skus = set()
            for item, raw_text in temp_parsed:
                sku_text_aligned = self._align_sku_text(raw_text, valid_dimensions)
                if sku_text_aligned in seen_skus:
                    logger.warning(f"SKU attributes conflict detected during dimension aligning. Skipping: {sku_text_aligned}")
                    continue
                seen_skus.add(sku_text_aligned)

                sku_stock = min(9999, int(item.get('stock') or 0))
                total_stock += sku_stock
                payload['sku_items'].append({
                    "price": int(float(item['price']) * 100),  # 转换为分
                    "stock": sku_stock,
                    "outer_id": item.get('outer_id', ''),
                    "sku_text": sku_text_aligned
                })

            if len(payload['sku_items']) < 2:
                if len(payload['sku_items']) == 1:
                    price_fen = payload['sku_items'][0]['price']
                    payload['price'] = price_fen
                    payload['original_price'] = price_fen + 5000
                    payload['stock'] = payload['sku_items'][0]['stock']
                payload.pop('sku_items', None)
                payload.pop('sku_images', None)
            else:
                payload['stock'] = total_stock  # 主库存校准为多规格库存之和

                # 仅在至少两个规格值时，才拼装多规格 SKU 图片信息，并使用相同的 valid_dimensions 进行对齐
                if 'sku_images' in source_data and source_data['sku_images']:
                    payload['sku_images'] = []
                    seen_img_skus = set()
                    for img in source_data['sku_images']:
                        src = img['src']
                        if isinstance(src, str):
                            if src.startswith("//"): src = "https:" + src
                            elif not src.startswith("http"): src = "https://" + src
                            
                            img_sku_text = self._align_sku_text(img['sku_text'], valid_dimensions)
                            if img_sku_text in seen_img_skus:
                                continue
                            seen_img_skus.add(img_sku_text)

                            payload['sku_images'].append({
                                "src": src,
                                "width": int(img.get('width', 800)),
                                "height": int(img.get('height', 800)),
                                "sku_text": img_sku_text
                            })
        elif len(sku_items_raw) == 1:
            # 自动退化为单规格上架：主售价和库存使用此唯一的 SKU 信息
            single_sku = sku_items_raw[0]
            price_fen = int(float(single_sku['price']) * 100)
            payload['price'] = price_fen
            payload['original_price'] = price_fen + 5000
            payload['stock'] = min(9999, int(single_sku.get('stock') or 10))

        timestamp = int(time.time())
        auth = APISigner.sign_v3_protocol(payload, self.appid, self.app_secret, timestamp)
        
        target_url = f"{self.base_url}/api/open/product/create"
        query_params = {
            "appid": auth['app_key'],
            "timestamp": auth['timestamp'],
            "sign": auth['sign']
        }
        
        compact_body = json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
        headers = {"Content-Type": "application/json"}
        
        try:
            resp = requests.post(target_url, params=query_params, data=compact_body.encode('utf-8'), headers=headers, timeout=20)
            result = resp.json()
            
            if result.get("code") == 0:
                product_id = str(result.get('data', {}).get('product_id'))
                logger.info(f"Step 1: Product Created. ID: {product_id}")
                
                # --- 核心：自动执行第二步：上架 ---
                listing_res = self.commit_publish(product_id)
                if listing_res['status'] == 'success':
                    return {"status": "success", "xianyu_item_id": product_id, "raw": result}
                else:
                    return {"status": "failed", "msg": listing_res['msg'], "raw": result}
            else:
                return {"status": "failed", "msg": result.get("msg"), "raw": result}
        except Exception as e:
            return {"status": "failed", "msg": str(e)}

    def commit_publish(self, product_id: str) -> Dict[str, Any]:
        """
        第二步：正式上架 (Commit Publish)
        """
        payload = {
            "product_id": int(product_id),
            "user_name": [self.defaults.get("user_name")]
        }

        timestamp = int(time.time())
        auth = APISigner.sign_v3_protocol(payload, self.appid, self.app_secret, timestamp)
        
        target_url = f"{self.base_url}/api/open/product/publish"
        params = {
            "appid": auth['app_key'],
            "timestamp": auth['timestamp'],
            "sign": auth['sign']
        }
        
        compact_body = json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
        headers = {"Content-Type": "application/json"}
        
        logger.info(f"Step 2: Listing Product {product_id}...")
        try:
            resp = requests.post(target_url, params=params, data=compact_body.encode('utf-8'), headers=headers, timeout=20)
            result = resp.json()
            if result.get("code") == 0:
                logger.info(f"Step 2: Listing Successful.")
                return {"status": "success", "msg": "上架成功"}
            else:
                return {"status": "failed", "msg": result.get("msg")}
        except Exception as e:
            return {"status": "failed", "msg": f"上架连接异常: {e}"}

if __name__ == "__main__":
    pass
