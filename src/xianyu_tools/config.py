from __future__ import annotations

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
        """获取数据库配置，仅从统一配置结构读取"""
        db_cfg = self.get("database")
        if db_cfg:
            return db_cfg
        return {}

    def get_llm_config(self) -> List[Dict[str, Any]]:
        """获取大模型配置，优先从数据库获取，否则回退到统一配置文件"""
        db_cfg = self._read_config_from_db("llm")
        if db_cfg:
            return db_cfg if isinstance(db_cfg, list) else [db_cfg]

        llm_cfg = self.get("llm")
        if llm_cfg:
            return llm_cfg if isinstance(llm_cfg, list) else [llm_cfg]
        return []

    def get_openapi_raw_config(self) -> Dict[str, Any]:
        """获取闲鱼 OpenAPI 原始配置，优先从数据库获取，否则回退到统一配置文件"""
        db_cfg = self._read_config_from_db("openapi")
        if db_cfg:
            return db_cfg

        openapi_cfg = self.get("openapi")
        if openapi_cfg:
            return openapi_cfg
        return {}

    def get_openapi_config(self, account_id: str | None = None) -> Dict[str, Any]:
        """获取当前生效的闲鱼 OpenAPI 账号配置，仅支持多账号新结构"""
        raw_cfg = self.get_openapi_raw_config() or {}
        accounts = raw_cfg.get("accounts")
        if not isinstance(accounts, list) or not accounts:
            return {}

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
                    "active_account_ids": ["ali1688-account-1"],
                    "active_account_id": "ali1688-account-1",
                    "accounts": [
                        {
                            "account_id": "ali1688-account-1",
                            "label": "1688 账号 1",
                            "enabled": True,
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

    @staticmethod
    def _normalize_active_source_account_ids(
        accounts: List[Dict[str, Any]],
        raw_ids: Any,
        fallback_id: str | None = None,
    ) -> List[str]:
        account_ids = [item.get("account_id") for item in accounts if item.get("account_id")]
        requested_ids = raw_ids if isinstance(raw_ids, list) else [raw_ids] if raw_ids else []
        normalized_ids: List[str] = []
        for account_id in requested_ids:
            if account_id in account_ids and account_id not in normalized_ids:
                normalized_ids.append(account_id)

        if not normalized_ids and fallback_id in account_ids:
            normalized_ids.append(fallback_id)
        if not normalized_ids and account_ids:
            normalized_ids.append(account_ids[0])
        return normalized_ids

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

        active_account_ids = self._normalize_active_source_account_ids(
            accounts,
            channel_cfg.get("active_account_ids"),
            fallback_id=channel_cfg.get("active_account_id"),
        )
        target_id = account_id or (active_account_ids[0] if active_account_ids else None) or channel_cfg.get("active_account_id")
        selected = next((item for item in accounts if item.get("account_id") == target_id), None)
        return selected or accounts[0]

    @staticmethod
    def _pick_enabled_source_channel(
        channels: List[Dict[str, Any]],
        channel_id: str | None = None,
        channel_type: str | None = None,
    ) -> Dict[str, Any]:
        candidates = [
            item for item in channels
            if item and (channel_type is None or item.get("channel_type") == channel_type)
        ]
        if not candidates:
            return {}

        requested = None
        if channel_id:
            requested = next((item for item in candidates if item.get("channel_id") == channel_id), None)
            if requested and requested.get("enabled", True) is not False:
                return requested

        enabled_candidates = [item for item in candidates if item.get("enabled", True) is not False]
        if enabled_candidates:
            return enabled_candidates[0]
        return requested or candidates[0]

    @staticmethod
    def _pick_enabled_source_account(accounts: List[Dict[str, Any]], account_id: str | None = None) -> Dict[str, Any]:
        if not accounts:
            return {}

        requested = None
        if account_id:
            requested = next((item for item in accounts if item.get("account_id") == account_id), None)
            if requested and requested.get("enabled", True) is not False:
                return requested

        enabled_accounts = [item for item in accounts if item.get("enabled", True) is not False]
        if enabled_accounts:
            return enabled_accounts[0]
        return requested or accounts[0]

    def get_active_source_channel(self, channel_type: str | None = None) -> Dict[str, Any]:
        """获取当前生效的渠道配置；优先返回启用中的渠道。"""
        cfg = self.get_source_channels_config()
        channels = cfg.get("channels") or []
        if not channels:
            return {}

        return self._pick_enabled_source_channel(
            channels,
            channel_id=cfg.get("active_channel_id"),
            channel_type=channel_type,
        )

    def get_active_source_channel_account(self, channel_type: str | None = None) -> Dict[str, Any]:
        """获取当前生效的渠道账号；如指定 channel_type，则优先返回该类型的激活账号"""
        selected_channel = self.get_active_source_channel(channel_type)
        if not selected_channel or selected_channel.get("enabled", True) is False:
            return {}
        accounts = selected_channel.get("accounts") or []
        if not accounts:
            return {}

        active_account_ids = self._normalize_active_source_account_ids(
            accounts,
            selected_channel.get("active_account_ids"),
            fallback_id=selected_channel.get("active_account_id"),
        )
        selected_account = {}
        for active_account_id in active_account_ids:
            selected_account = self._pick_enabled_source_account(accounts, account_id=active_account_id)
            if selected_account and selected_account.get("enabled", True) is not False:
                break
        if not selected_account:
            selected_account = self._pick_enabled_source_account(
                accounts,
                account_id=selected_channel.get("active_account_id"),
            )
        if not selected_account or selected_account.get("enabled", True) is False:
            return {}
        return selected_account

    def build_source_channel_account_runtime(self, channel_type: str | None, channel_id: str | None, account_id: str | None) -> Dict[str, Any]:
        """按渠道与账号生成系统托管的运行时路径配置"""
        safe_channel_id = str(channel_id or "source-channel").strip() or "source-channel"
        safe_account_id = str(account_id or "account-1").strip() or "account-1"

        if channel_type == "ali1688":
            return {
                "state_file": f"state/source_channels/{safe_channel_id}/{safe_account_id}/storage_state.json",
                "user_data_dir": f"profiles/source_channels/{safe_channel_id}/{safe_account_id}/chrome_profile",
                "profile_directory": "Default",
                "cookies_source": "storage_state",
            }

        return {
            "state_file": "",
            "user_data_dir": "",
            "profile_directory": None,
            "cookies_source": "",
        }

    def get_active_ali1688_runtime_config(self) -> Dict[str, Any]:
        """获取当前生效的 1688 渠道运行时配置"""
        cfg = self.get_source_channels_config()
        channels = cfg.get("channels") or []
        ali1688_channels = [item for item in channels if item.get("channel_type") == "ali1688"]
        active_channel = self.get_active_source_channel("ali1688")
        if active_channel and active_channel.get("channel_type") != "ali1688":
            active_channel = {}

        any_ali1688_channel = ali1688_channels[0] if ali1688_channels else {}
        channel_id = (
            active_channel.get("channel_id")
            or any_ali1688_channel.get("channel_id")
            or "ali1688"
        )
        account = self.get_active_source_channel_account("ali1688")
        if not account:
            if not ali1688_channels:
                error_message = "未配置 1688 货源渠道"
            elif active_channel and active_channel.get("enabled", True) is False:
                error_message = "1688 货源渠道已停用"
            else:
                error_message = "未配置可用的 1688 货源渠道账号"
            return {
                "channel_type": "ali1688",
                "channel_id": channel_id,
                "account_id": "",
                "active_account_ids": [],
                "label": "",
                "state_file": "",
                "user_data_dir": "",
                "profile_directory": "Default",
                "cookies_source": "storage_state",
                "enabled": False,
                "is_configured": False,
                "error_message": error_message,
            }

        runtime = self.build_source_channel_account_runtime("ali1688", channel_id, account.get("account_id"))

        return {
            "channel_type": "ali1688",
            "channel_id": channel_id,
            "account_id": account.get("account_id"),
            "active_account_ids": self._normalize_active_source_account_ids(
                active_channel.get("accounts") or [],
                active_channel.get("active_account_ids"),
                fallback_id=active_channel.get("active_account_id"),
            ),
            "label": account.get("label"),
            "state_file": runtime.get("state_file"),
            "user_data_dir": runtime.get("user_data_dir"),
            "profile_directory": runtime.get("profile_directory"),
            "cookies_source": runtime.get("cookies_source"),
            "enabled": bool(account.get("enabled", True)),
            "is_configured": True,
            "error_message": "",
        }

# 导出全局单例配置实例
settings = ConfigManager()
