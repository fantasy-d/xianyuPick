import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

# 设置日志
logger = logging.getLogger("ConfigManager")

# 获取项目根目录
BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = BASE_DIR / "config" / "config.json"

class ConfigManager:
    _instance = None
    _config_data: Dict[str, Any] = {}
    _db_cache: Dict[str, Any] = {}
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, config_path: str = None):
        if not self._initialized:
            if config_path:
                self.config_file = Path(config_path)
            else:
                self.config_file = DEFAULT_CONFIG_PATH
            self._db_cache = {}
            self.load()
            self._initialized = True

    def load(self):
        """加载统一配置文件 config.json"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                if content.strip():
                    self._config_data = json.loads(content)
                else:
                    self._config_data = {}
            except Exception as e:
                logger.error(f"Failed to load config from {self.config_file}: {e}")
                self._config_data = {}
        else:
            self._config_data = {}

    def get(self, key: str, default: Any = None) -> Any:
        """获取第一层配置"""
        return self._config_data.get(key, default)

    def _read_config_from_db(self, key: str) -> Any:
        """从数据库读取特定配置（带内存缓存与连接超时控制）"""
        if key in self._db_cache:
            return self._db_cache[key]
            
        try:
            db_cfg = self.get_database_config()
            if not db_cfg:
                return None
            import pymysql
            # 加入短期超时限制，防止未初始化时发生连接阻塞
            conn_cfg = {**db_cfg, "connect_timeout": 3}
            conn = pymysql.connect(**conn_cfg)
            cursor = conn.cursor()
            cursor.execute("SELECT cfg_value FROM system_configs WHERE cfg_key = %s", (key,))
            row = cursor.fetchone()
            conn.close()
            if row:
                val = row["cfg_value"] if isinstance(row, dict) else row[0]
                data = json.loads(val)
                self._db_cache[key] = data
                return data
        except Exception:
            # 捕获所有异常以在未连上库或表未创建时平滑 fallback 到本地
            pass
        return None

    def get_database_config(self) -> Dict[str, Any]:
        """获取数据库配置，并支持向后兼容单独的 database.json"""
        # 1. 优先从统一配置中获取
        db_cfg = self.get("database")
        if db_cfg:
            return db_cfg
        
        # 2. 回退到单独的 database.json
        legacy_path = BASE_DIR / "config" / "database.json"
        if os.path.exists(legacy_path):
            try:
                with open(legacy_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load legacy database.json: {e}")
        return {}

    def get_llm_config(self) -> List[Dict[str, Any]]:
        """获取大模型配置，优先从数据库获取，否则回退到配置文件"""
        # 1. 优先从数据库中获取最新配置
        db_cfg = self._read_config_from_db("llm")
        if db_cfg:
            return db_cfg if isinstance(db_cfg, list) else [db_cfg]

        # 2. 回退到统一配置文件
        llm_cfg = self.get("llm")
        if llm_cfg:
            return llm_cfg if isinstance(llm_cfg, list) else [llm_cfg]
        
        # 3. 回退到单独的 llm.json
        legacy_path = BASE_DIR / "config" / "llm.json"
        if os.path.exists(legacy_path):
            try:
                with open(legacy_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else [data]
            except Exception as e:
                logger.error(f"Failed to load legacy llm.json: {e}")
        return []

    def get_openapi_raw_config(self) -> Dict[str, Any]:
        """获取闲鱼 OpenAPI 原始配置，优先从数据库获取，否则回退到配置文件"""
        # 1. 优先从数据库中获取最新配置
        db_cfg = self._read_config_from_db("openapi")
        if db_cfg:
            return db_cfg

        # 2. 回退到统一配置文件
        openapi_cfg = self.get("openapi")
        if openapi_cfg:
            return openapi_cfg
        
        # 3. 回退到单独的 openapi.json
        legacy_path = BASE_DIR / "config" / "openapi.json"
        if os.path.exists(legacy_path):
            try:
                with open(legacy_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load legacy openapi.json: {e}")
        return {}

    def get_openapi_config(self, account_id: str | None = None) -> Dict[str, Any]:
        """获取当前生效的闲鱼 OpenAPI 账号配置，兼容旧的单账号结构"""
        raw_cfg = self.get_openapi_raw_config() or {}
        accounts = raw_cfg.get("accounts")
        if not isinstance(accounts, list) or not accounts:
            return raw_cfg

        target_id = account_id or raw_cfg.get("active_account_id")
        selected = None
        if target_id:
            selected = next((item for item in accounts if item.get("id") == target_id), None)
        if not selected:
            selected = accounts[0]

        return selected or {}

    def get_crawl_config(self) -> Dict[str, Any]:
        """获取商品爬取参数配置，优先从数据库获取，否则回退到配置文件"""
        default_cfg = {
            "source_limit_1688": 10,
            "source_filter_models": []
        }
        
        # 1. 优先从数据库中获取最新配置
        db_cfg = self._read_config_from_db("crawl")
        if db_cfg and isinstance(db_cfg, dict):
            return {**default_cfg, **db_cfg}

        # 2. 回退到统一配置文件
        crawl_cfg = self.get("crawl")
        if crawl_cfg and isinstance(crawl_cfg, dict):
            return {**default_cfg, **crawl_cfg}
            
        return default_cfg

    def get_source_channels_raw_config(self) -> Dict[str, Any]:
        """获取货源渠道号池原始配置，优先从数据库获取，否则回退到配置文件"""
        db_cfg = self._read_config_from_db("source_channels")
        if db_cfg and isinstance(db_cfg, dict):
            return db_cfg

        channels_cfg = self.get("source_channels")
        if channels_cfg and isinstance(channels_cfg, dict):
            return channels_cfg

        return {}

    def get_source_channels_config(self) -> Dict[str, Any]:
        """获取货源渠道号池配置，并补齐最小默认结构"""
        default_cfg = {
            "active_channel_id": "ali1688",
            "channels": [
                {
                    "channel_id": "ali1688",
                    "channel_type": "ali1688",
                    "label": "1688 货源渠道",
                    "enabled": True,
                    "active_account_id": "ali1688-account-1",
                    "accounts": [
                        {
                            "account_id": "ali1688-account-1",
                            "label": "1688 账号 1",
                            "enabled": True,
                            "state_file": "state/ali1688/storage_state.json",
                            "user_data_dir": "profiles/ali1688_chrome_profile",
                            "cookies_source": "storage_state",
                            "notes": "",
                        }
                    ],
                }
            ],
        }

        raw_cfg = self.get_source_channels_raw_config()
        if not raw_cfg:
            return default_cfg

        merged = {**default_cfg, **raw_cfg}
        channels = raw_cfg.get("channels")
        if isinstance(channels, list) and channels:
            merged["channels"] = channels
        return merged

    def get_source_channel_config(self, channel_id: str | None = None) -> Dict[str, Any]:
        """获取指定货源渠道配置，默认返回当前激活渠道"""
        cfg = self.get_source_channels_config()
        channels = cfg.get("channels") or []
        if not channels:
            return {}

        target_id = channel_id or cfg.get("active_channel_id")
        selected = next((item for item in channels if item.get("channel_id") == target_id), None)
        return selected or channels[0]

    def get_source_channel_account_config(self, channel_id: str | None = None, account_id: str | None = None) -> Dict[str, Any]:
        """获取指定渠道账号配置，默认返回当前激活账号"""
        channel_cfg = self.get_source_channel_config(channel_id)
        accounts = channel_cfg.get("accounts") or []
        if not accounts:
            return {}

        target_id = account_id or channel_cfg.get("active_account_id")
        selected = next((item for item in accounts if item.get("account_id") == target_id), None)
        return selected or accounts[0]

    def get_active_source_channel_account(self, channel_type: str | None = None) -> Dict[str, Any]:
        """获取当前生效的渠道账号；如指定 channel_type，则优先返回该类型的激活账号"""
        cfg = self.get_source_channels_config()
        channels = cfg.get("channels") or []
        if not channels:
            return {}

        selected_channel = None
        active_channel_id = cfg.get("active_channel_id")
        if active_channel_id:
            selected_channel = next(
                (
                    item for item in channels
                    if item.get("channel_id") == active_channel_id
                    and (channel_type is None or item.get("channel_type") == channel_type)
                ),
                None,
            )
        if not selected_channel and channel_type is not None:
            selected_channel = next((item for item in channels if item.get("channel_type") == channel_type), None)
        if not selected_channel:
            selected_channel = channels[0]

        accounts = selected_channel.get("accounts") or []
        if not accounts:
            return {}

        active_account_id = selected_channel.get("active_account_id")
        selected_account = None
        if active_account_id:
            selected_account = next((item for item in accounts if item.get("account_id") == active_account_id), None)
        return selected_account or accounts[0]

    def get_active_ali1688_runtime_config(self) -> Dict[str, Any]:
        """获取当前生效的 1688 渠道运行时配置"""
        account = self.get_active_source_channel_account("ali1688")
        if not account:
            return {
                "channel_type": "ali1688",
                "state_file": "state/ali1688/storage_state.json",
                "user_data_dir": "profiles/ali1688_chrome_profile",
                "profile_directory": None,
            }

        return {
            "channel_type": "ali1688",
            "account_id": account.get("account_id"),
            "label": account.get("label"),
            "state_file": account.get("state_file") or "state/ali1688/storage_state.json",
            "user_data_dir": account.get("user_data_dir") or "profiles/ali1688_chrome_profile",
            "profile_directory": account.get("profile_directory") or None,
            "cookies_source": account.get("cookies_source") or "storage_state",
            "enabled": bool(account.get("enabled", True)),
        }

# 导出全局单例配置实例
settings = ConfigManager()
