from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

from xianyu_tools.channel_search_filters import (
    get_ali1688_channel_search_filter_keys,
    get_ali1688_channel_search_filter_meta,
)

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
        # 1. 优先从数据库中获取最新配置
        db_cfg = self._read_config_from_db("crawl")
        if db_cfg and isinstance(db_cfg, dict):
            return self.normalize_crawl_config(db_cfg)

        # 2. 回退到统一配置文件
        crawl_cfg = self.get("crawl")
        if crawl_cfg and isinstance(crawl_cfg, dict):
            return self.normalize_crawl_config(crawl_cfg)

        return self.normalize_crawl_config({})

    @staticmethod
    def _get_default_crawl_config() -> Dict[str, Any]:
        return {
            "source_limit_1688": 10,
            "source_filter_models": [],
            "source_channel_selection_mode": "active_pool",
            "enabled_source_channels": [],
            "channel_search_filters": [],
        }

    @staticmethod
    def _get_supported_channel_search_filter_keys(channel_type: str | None) -> List[str]:
        if str(channel_type or "").strip().lower() == "ali1688":
            return list(get_ali1688_channel_search_filter_keys())
        return []

    def _normalize_channel_search_filters(
        self,
        requested_filters: Any,
        channel_map: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        normalized_map: Dict[str, Dict[str, Any]] = {}
        requested_map: Dict[str, Dict[str, Any]] = {}
        if isinstance(requested_filters, list):
            for entry in requested_filters:
                if not isinstance(entry, dict):
                    continue
                channel_id = str(entry.get("channel_id") or "").strip()
                channel_cfg = channel_map.get(channel_id)
                if not channel_id or not channel_cfg:
                    continue
                raw_filters = entry.get("filters")
                requested_map[channel_id] = raw_filters if isinstance(raw_filters, dict) else {}

        for channel_id, channel_cfg in channel_map.items():
            supported_keys = self._get_supported_channel_search_filter_keys(
                channel_cfg.get("channel_type")
            )
            raw_filters = requested_map.get(channel_id, {})
            normalized_map[channel_id] = {
                "channel_id": channel_id,
                "filters": {
                    key: bool(raw_filters.get(key, False))
                    for key in supported_keys
                },
            }

        ordered_entries: List[Dict[str, Any]] = []
        for channel_id in channel_map:
            matched = normalized_map.get(channel_id)
            if matched:
                ordered_entries.append(matched)
        return ordered_entries

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
        raw_channels = raw_cfg.get("channels")
        if not isinstance(raw_channels, list) or not raw_channels:
            raw_channels = default_cfg["channels"]

        normalized_channels: List[Dict[str, Any]] = []
        for index, channel in enumerate(raw_channels, start=1):
            merged_channel = {
                "channel_id": "",
                "channel_type": "custom",
                "label": "",
                "enabled": True,
                "active_account_ids": [],
                "active_account_id": "",
                "accounts": [],
            }
            merged_channel.update(dict(channel or {}))
            merged_channel["channel_id"] = merged_channel.get("channel_id") or f"channel-{index}"
            merged_channel["channel_type"] = merged_channel.get("channel_type") or "custom"
            merged_channel["label"] = merged_channel.get("label") or f"货源渠道 {index}"
            merged_channel["enabled"] = merged_channel.get("enabled", True) is not False

            raw_accounts = merged_channel.get("accounts")
            if not isinstance(raw_accounts, list) or not raw_accounts:
                raw_accounts = [
                    {
                        "account_id": f"{merged_channel['channel_id']}-account-1",
                        "label": f"{merged_channel['label']} 账号 1",
                        "enabled": True,
                        "notes": "",
                    }
                ]

            normalized_accounts: List[Dict[str, Any]] = []
            for account_index, account in enumerate(raw_accounts, start=1):
                merged_account = {
                    "account_id": "",
                    "label": "",
                    "enabled": True,
                    "notes": "",
                }
                merged_account.update(dict(account or {}))
                merged_account["account_id"] = merged_account.get("account_id") or f"{merged_channel['channel_id']}-account-{account_index}"
                merged_account["label"] = merged_account.get("label") or f"{merged_channel['label']} 账号 {account_index}"
                merged_account["enabled"] = merged_account.get("enabled", True) is not False
                merged_account["notes"] = merged_account.get("notes") or ""
                merged_account.update(
                    self.build_source_channel_account_runtime(
                        merged_channel.get("channel_type"),
                        merged_channel.get("channel_id"),
                        merged_account.get("account_id"),
                    )
                )
                normalized_accounts.append(merged_account)

            merged_channel["accounts"] = normalized_accounts
            active_account_ids = self._normalize_active_source_account_ids(
                normalized_accounts,
                merged_channel.get("active_account_ids"),
                fallback_id=merged_channel.get("active_account_id"),
            )
            merged_channel["active_account_ids"] = active_account_ids
            merged_channel["active_account_id"] = active_account_ids[0] if active_account_ids else ""
            normalized_channels.append(merged_channel)

        active_channel_id = merged.get("active_channel_id") or normalized_channels[0]["channel_id"]
        if not any(item.get("channel_id") == active_channel_id for item in normalized_channels):
            active_channel_id = normalized_channels[0]["channel_id"]

        return {
            "active_channel_id": active_channel_id,
            "channels": normalized_channels,
        }

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

    @staticmethod
    def _filter_source_account_ids(
        accounts: List[Dict[str, Any]],
        raw_ids: Any,
    ) -> List[str]:
        account_ids = [item.get("account_id") for item in accounts if item.get("account_id")]
        requested_ids = raw_ids if isinstance(raw_ids, list) else [raw_ids] if raw_ids else []
        normalized_ids: List[str] = []
        for account_id in requested_ids:
            if account_id in account_ids and account_id not in normalized_ids:
                normalized_ids.append(account_id)
        return normalized_ids

    def _is_source_account_usable(
        self,
        channel_cfg: Dict[str, Any],
        account_cfg: Dict[str, Any],
    ) -> bool:
        if not account_cfg or account_cfg.get("enabled", True) is False:
            return False

        session_report = account_cfg.get("session_report") or {}
        if isinstance(session_report, dict) and session_report:
            if session_report.get("is_logged_in") or session_report.get("is_usable"):
                return True
            return False

        runtime = self.build_source_channel_account_runtime(
            channel_cfg.get("channel_type"),
            channel_cfg.get("channel_id"),
            account_cfg.get("account_id"),
        )
        return self._is_runtime_state_file_usable(
            runtime.get("channel_type"),
            runtime.get("state_file"),
        )

    def normalize_crawl_config(
        self,
        raw_cfg: Dict[str, Any] | None,
        source_channels_cfg: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        default_cfg = self._get_default_crawl_config()
        raw_cfg = dict(raw_cfg or {})
        source_channels_cfg = source_channels_cfg or self.get_source_channels_config()
        channels = source_channels_cfg.get("channels") or []
        channel_map = {
            item.get("channel_id"): item
            for item in channels
            if item.get("channel_id")
        }

        source_limit = raw_cfg.get("source_limit_1688", default_cfg["source_limit_1688"])
        try:
            source_limit = int(source_limit)
            if source_limit <= 0:
                source_limit = default_cfg["source_limit_1688"]
            elif source_limit > 100:
                source_limit = 100
        except (TypeError, ValueError):
            source_limit = default_cfg["source_limit_1688"]

        models_subset = raw_cfg.get("source_filter_models", default_cfg["source_filter_models"])
        if not isinstance(models_subset, list):
            models_subset = []
        models_subset = [
            model for model in models_subset
            if isinstance(model, str) and model.strip()
        ]

        selection_mode = str(raw_cfg.get("source_channel_selection_mode") or "").strip()
        if selection_mode not in {"active_pool", "custom_selected"}:
            selection_mode = default_cfg["source_channel_selection_mode"]

        requested_entries = raw_cfg.get("enabled_source_channels")
        has_explicit_requested_entries = isinstance(requested_entries, list)
        normalized_entries: List[Dict[str, Any]] = []
        if has_explicit_requested_entries:
            for entry in requested_entries:
                if not isinstance(entry, dict):
                    continue
                channel_id = str(entry.get("channel_id") or "").strip()
                channel_cfg = channel_map.get(channel_id)
                if not channel_cfg:
                    continue
                requested_account_ids = self._filter_source_account_ids(
                    channel_cfg.get("accounts") or [],
                    entry.get("account_ids"),
                )
                selected_account_ids = []
                for account_id in requested_account_ids:
                    account_cfg = next(
                        (item for item in (channel_cfg.get("accounts") or []) if item.get("account_id") == account_id),
                        None,
                    )
                    if account_cfg and self._is_source_account_usable(channel_cfg, account_cfg):
                        selected_account_ids.append(account_id)
                normalized_entries.append(
                    {
                        "channel_id": channel_id,
                        "enabled": bool(entry.get("enabled", True)),
                        "account_ids": selected_account_ids,
                    }
                )

        if not normalized_entries and selection_mode != "custom_selected":
            for channel in channels:
                if channel.get("enabled", True) is False:
                    continue
                requested_active_account_ids = self._filter_source_account_ids(
                    channel.get("accounts") or [],
                    channel.get("active_account_ids"),
                )
                active_account_ids = []
                for account_id in requested_active_account_ids:
                    account_cfg = next(
                        (item for item in (channel.get("accounts") or []) if item.get("account_id") == account_id),
                        None,
                    )
                    if account_cfg and self._is_source_account_usable(channel, account_cfg):
                        active_account_ids.append(account_id)
                if not active_account_ids:
                    continue
                normalized_entries.append(
                    {
                        "channel_id": channel.get("channel_id"),
                        "enabled": True,
                        "account_ids": active_account_ids,
                    }
                )

        ordered_entries: List[Dict[str, Any]] = []
        for channel in channels:
            channel_id = channel.get("channel_id")
            matched = next((item for item in normalized_entries if item.get("channel_id") == channel_id), None)
            if matched:
                ordered_entries.append(matched)

        channel_search_filters = self._normalize_channel_search_filters(
            raw_cfg.get("channel_search_filters"),
            channel_map,
        )

        return {
            "source_limit_1688": source_limit,
            "source_filter_models": models_subset,
            "source_channel_selection_mode": selection_mode,
            "enabled_source_channels": ordered_entries,
            "channel_search_filters": channel_search_filters,
        }

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

    def get_channel_search_filters(
        self,
        channel_id: str | None = None,
        channel_type: str | None = None,
        crawl_cfg: Dict[str, Any] | None = None,
        source_channels_cfg: Dict[str, Any] | None = None,
    ) -> Dict[str, bool]:
        crawl_cfg = crawl_cfg or self.get_crawl_config()
        source_channels_cfg = source_channels_cfg or self.get_source_channels_config()
        channels = source_channels_cfg.get("channels") or []
        selected_channel = self._pick_enabled_source_channel(
            channels,
            channel_id=channel_id or source_channels_cfg.get("active_channel_id"),
            channel_type=channel_type,
        )
        if not selected_channel:
            return {}

        selected_channel_id = selected_channel.get("channel_id")
        supported_keys = self._get_supported_channel_search_filter_keys(
            selected_channel.get("channel_type")
        )
        default_filters = {key: False for key in supported_keys}
        requested_entries = crawl_cfg.get("channel_search_filters") or []
        matched = next(
            (
                item for item in requested_entries
                if isinstance(item, dict) and item.get("channel_id") == selected_channel_id
            ),
            None,
        )
        if not matched:
            return default_filters

        raw_filters = matched.get("filters")
        if not isinstance(raw_filters, dict):
            return default_filters

        normalized_filters = dict(default_filters)
        for key in supported_keys:
            normalized_filters[key] = bool(raw_filters.get(key, False))
        return normalized_filters

    @staticmethod
    def _ordered_unique_string_list(values: Any) -> List[str]:
        if not isinstance(values, list):
            return []
        seen: set[str] = set()
        result: List[str] = []
        for value in values:
            text = str(value or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            result.append(text)
        return result

    @staticmethod
    def _normalize_filter_mapping_type(channel_type: str | None, filter_key: str) -> str:
        if str(channel_type or "").strip().lower() == "ali1688":
            meta = get_ali1688_channel_search_filter_meta(str(filter_key or "").strip())
            return str(meta.get("mapping_type") or "snapshot_only").strip() or "snapshot_only"
        return "unsupported"

    @staticmethod
    def _normalize_filter_group(channel_type: str | None, filter_key: str) -> str:
        if str(channel_type or "").strip().lower() == "ali1688":
            meta = get_ali1688_channel_search_filter_meta(str(filter_key or "").strip())
            return str(meta.get("group") or "").strip()
        return ""

    @staticmethod
    def _normalize_filter_label(channel_type: str | None, filter_key: str) -> str:
        normalized_key = str(filter_key or "").strip()
        if str(channel_type or "").strip().lower() == "ali1688":
            meta = get_ali1688_channel_search_filter_meta(normalized_key)
            return str(meta.get("label") or normalized_key).strip() or normalized_key
        return normalized_key

    @staticmethod
    def _normalize_filter_extra_meta(channel_type: str | None, filter_key: str) -> Dict[str, Any]:
        if str(channel_type or "").strip().lower() != "ali1688":
            return {
                "semantic_dependencies": [],
                "verification_entry": "",
                "mapping_hint": "",
                "observation_scope": "",
                "entry_signal_type": "",
                "next_required_action": "",
            }
        meta = get_ali1688_channel_search_filter_meta(str(filter_key or "").strip())
        return {
            "semantic_dependencies": [
                str(item).strip()
                for item in meta.get("semantic_dependencies") or []
                if str(item).strip()
            ],
            "verification_entry": str(meta.get("verification_entry") or "").strip(),
            "mapping_hint": str(meta.get("mapping_hint") or "").strip(),
            "observation_scope": str(meta.get("observation_scope") or "").strip(),
            "entry_signal_type": str(meta.get("entry_signal_type") or "").strip(),
            "next_required_action": str(meta.get("next_required_action") or "").strip(),
        }

    @staticmethod
    def _derive_filter_mapping_stage(
        *,
        mapping_type: str,
        status: str,
        raw_mapping_stage: str,
    ) -> str:
        normalized_raw = str(raw_mapping_stage or "").strip()
        if normalized_raw:
            return normalized_raw
        if status == "applied":
            if mapping_type == "query_candidate":
                return "query_mapped"
            if mapping_type in {"ui_checkbox_candidate", "special_panel_candidate", "semantic_combo_candidate"}:
                return "ui_automation"
        if status == "query_injected_pending_verification":
            return "query_candidate"
        return "snapshot_only"

    @staticmethod
    def _derive_default_filter_reason(
        *,
        mapping_type: str,
        status: str,
    ) -> str:
        normalized_mapping_type = str(mapping_type or "").strip()
        normalized_status = str(status or "").strip()
        if normalized_status == "applied":
            return ""
        if normalized_status == "query_injected_pending_verification":
            if normalized_mapping_type == "query_candidate":
                return "query_filter_injected_pending_verification"
            return "runtime_mapping_not_implemented_yet"
        if normalized_mapping_type == "query_candidate":
            return "query_filter_not_applied_in_runtime"
        if normalized_mapping_type == "ui_checkbox_candidate":
            return "ui_selector_not_stable"
        if normalized_mapping_type == "special_panel_candidate":
            return "special_panel_unmapped"
        if normalized_mapping_type == "semantic_combo_candidate":
            return "semantic_combo_not_confirmed"
        return "runtime_mapping_not_implemented_yet"

    @staticmethod
    def _derive_semantic_conclusion(
        *,
        mapping_type: str,
        verification_detail: Dict[str, Any] | None,
    ) -> str:
        if str(mapping_type or "").strip() != "semantic_combo_candidate":
            return ""
        detail = dict(verification_detail or {})
        stage = str(detail.get("semantic_verification_stage") or "").strip()
        if stage == "direct_entry_result_shift_observed":
            return "independent_entry_result_shift_observed"
        if stage == "direct_entry_result_shift_not_observed":
            return "independent_entry_no_result_shift"
        if stage == "dependency_pair_enabled":
            return "dependency_pair_ready_pending_runtime"
        if stage == "dependency_pair_strong_verified":
            return "dependency_pair_strong_verified"
        if stage == "dependency_pair_incomplete":
            return "dependency_pair_incomplete"
        if detail.get("independent_ui_entry_observed") is True:
            return "independent_entry_observed_pending_result_validation"
        return ""

    @staticmethod
    def _derive_special_panel_conclusion(
        *,
        mapping_type: str,
        status: str,
        verification_detail: Dict[str, Any] | None,
    ) -> str:
        if str(mapping_type or "").strip() != "special_panel_candidate":
            return ""
        detail = dict(verification_detail or {})
        if detail.get("entry_signal_detected") is True and str(detail.get("verification_mode") or "").strip() != "dom_panel_action":
            return "entry_signal_detected_pending_panel_mapping"
        if str(detail.get("verification_mode") or "").strip() == "dom_panel_action":
            if str(status or "").strip() == "applied":
                if str(detail.get("panel_term_selected_via_after_action") or "").strip() == "active_condition_text":
                    return "panel_active_condition_observed"
                if detail.get("result_signature_changed") is True or detail.get("result_url_changed") is True:
                    return "panel_action_result_shift_observed"
                return "panel_action_applied_no_result_shift"
            if detail.get("panel_trigger_clicked") is True or detail.get("entry_click_attempted") is True:
                return "panel_open_or_toggle_failed"
        return ""

    def normalize_channel_search_filter_snapshot(
        self,
        snapshot: Dict[str, Any] | None,
        *,
        channel_id: str | None = None,
        channel_type: str | None = None,
    ) -> Dict[str, Any]:
        raw_snapshot = dict(snapshot or {})
        resolved_channel_id = str(raw_snapshot.get("channel_id") or channel_id or "").strip()
        resolved_channel_type = str(raw_snapshot.get("channel_type") or channel_type or "").strip()

        supported_filter_keys = self._ordered_unique_string_list(raw_snapshot.get("supported_filter_keys"))
        if not supported_filter_keys:
            supported_filter_keys = self._get_supported_channel_search_filter_keys(resolved_channel_type)

        raw_filters = raw_snapshot.get("configured_filters")
        if not isinstance(raw_filters, dict):
            raw_filters = raw_snapshot.get("filters")
        if not isinstance(raw_filters, dict):
            raw_filters = {}
        normalized_filters = {
            key: bool(raw_filters.get(key, False))
            for key in supported_filter_keys
        }

        configured_enabled_filter_keys = [
            key for key, enabled in normalized_filters.items() if enabled
        ]
        fallback_enabled = self._ordered_unique_string_list(raw_snapshot.get("configured_enabled_filter_keys"))
        if not fallback_enabled:
            fallback_enabled = self._ordered_unique_string_list(raw_snapshot.get("enabled_filter_keys"))
        if not configured_enabled_filter_keys and fallback_enabled:
            configured_enabled_filter_keys = [key for key in fallback_enabled if key in supported_filter_keys]
            for key in configured_enabled_filter_keys:
                normalized_filters[key] = True

        query_injected_filter_keys = [
            key
            for key in self._ordered_unique_string_list(raw_snapshot.get("query_injected_filter_keys"))
            if key in configured_enabled_filter_keys
        ]
        applied_filter_keys = [
            key
            for key in self._ordered_unique_string_list(raw_snapshot.get("applied_filter_keys"))
            if key in configured_enabled_filter_keys
        ]
        unapplied_filter_keys = [
            key
            for key in self._ordered_unique_string_list(raw_snapshot.get("unapplied_filter_keys"))
            if key in configured_enabled_filter_keys
        ]
        query_verification_details = raw_snapshot.get("query_verification_details")
        if not isinstance(query_verification_details, dict):
            query_verification_details = {}
        raw_unapplied_reason_map = raw_snapshot.get("unapplied_reason_map")
        if not isinstance(raw_unapplied_reason_map, dict):
            raw_unapplied_reason_map = {}
        raw_status_map = raw_snapshot.get("filter_status_map")
        if not isinstance(raw_status_map, dict):
            raw_status_map = {}

        filter_status_map: Dict[str, Dict[str, Any]] = {}
        for key in configured_enabled_filter_keys:
            raw_meta = raw_status_map.get(key)
            if not isinstance(raw_meta, dict):
                raw_meta = {}
            verification_detail = raw_meta.get("verification_detail")
            if not isinstance(verification_detail, dict):
                verification_detail = {}
            verification_detail = {
                **verification_detail,
                **dict(query_verification_details.get(key) or {}),
            }
            status = str(raw_meta.get("status") or "").strip()
            if status not in {"applied", "query_injected_pending_verification", "unapplied"}:
                if key in applied_filter_keys:
                    status = "applied"
                elif key in query_injected_filter_keys:
                    status = "query_injected_pending_verification"
                else:
                    status = "unapplied"
            mapping_type = self._normalize_filter_mapping_type(resolved_channel_type, key)
            reason = str(raw_meta.get("reason") or raw_unapplied_reason_map.get(key) or "").strip()
            if status == "applied":
                reason = ""
            elif not reason:
                reason = self._derive_default_filter_reason(
                    mapping_type=mapping_type,
                    status=status,
                )
            filter_group = self._normalize_filter_group(resolved_channel_type, key)
            extra_meta = self._normalize_filter_extra_meta(resolved_channel_type, key)
            per_filter_mapping_stage = self._derive_filter_mapping_stage(
                mapping_type=mapping_type,
                status=status,
                raw_mapping_stage=str(raw_meta.get("mapping_stage") or "").strip(),
            )
            semantic_conclusion = self._derive_semantic_conclusion(
                mapping_type=mapping_type,
                verification_detail=verification_detail,
            )
            if semantic_conclusion and not str(verification_detail.get("semantic_conclusion") or "").strip():
                verification_detail["semantic_conclusion"] = semantic_conclusion
            special_panel_conclusion = self._derive_special_panel_conclusion(
                mapping_type=mapping_type,
                status=status,
                verification_detail=verification_detail,
            )
            if special_panel_conclusion and not str(verification_detail.get("special_panel_conclusion") or "").strip():
                verification_detail["special_panel_conclusion"] = special_panel_conclusion
            filter_status_map[key] = {
                "configured": True,
                "supported": key in supported_filter_keys,
                "label": self._normalize_filter_label(resolved_channel_type, key),
                "mapping_type": mapping_type,
                "mapping_stage": per_filter_mapping_stage,
                "group": filter_group,
                "status": status,
                "reason": reason,
                "verification_detail": verification_detail,
                "semantic_dependencies": list(extra_meta.get("semantic_dependencies") or []),
                "verification_entry": str(extra_meta.get("verification_entry") or "").strip(),
                "mapping_hint": str(extra_meta.get("mapping_hint") or "").strip(),
                "observation_scope": str(extra_meta.get("observation_scope") or "").strip(),
                "entry_signal_type": str(extra_meta.get("entry_signal_type") or "").strip(),
                "next_required_action": str(extra_meta.get("next_required_action") or "").strip(),
                "semantic_conclusion": semantic_conclusion,
                "special_panel_conclusion": special_panel_conclusion,
            }

        if filter_status_map:
            applied_filter_keys = [
                key for key, meta in filter_status_map.items()
                if meta.get("status") == "applied"
            ]
            query_injected_filter_keys = [
                key for key, meta in filter_status_map.items()
                if meta.get("status") == "query_injected_pending_verification"
            ]
            unapplied_filter_keys = [
                key for key, meta in filter_status_map.items()
                if meta.get("status") == "unapplied"
            ]
        else:
            if not unapplied_filter_keys:
                unapplied_filter_keys = [
                    key for key in configured_enabled_filter_keys
                    if key not in applied_filter_keys and key not in query_injected_filter_keys
                ]
            filter_status_map = {
                key: {
                    **self._normalize_filter_extra_meta(resolved_channel_type, key),
                    "configured": True,
                    "supported": key in supported_filter_keys,
                    "label": self._normalize_filter_label(resolved_channel_type, key),
                    "mapping_type": self._normalize_filter_mapping_type(resolved_channel_type, key),
                    "mapping_stage": self._derive_filter_mapping_stage(
                        mapping_type=self._normalize_filter_mapping_type(resolved_channel_type, key),
                        status=(
                            "applied" if key in applied_filter_keys
                            else "query_injected_pending_verification" if key in query_injected_filter_keys
                            else "unapplied"
                        ),
                        raw_mapping_stage="",
                    ),
                    "group": self._normalize_filter_group(resolved_channel_type, key),
                    "status": (
                        "applied" if key in applied_filter_keys
                        else "query_injected_pending_verification" if key in query_injected_filter_keys
                        else "unapplied"
                    ),
                    "reason": (
                        "" if key in applied_filter_keys
                        else str(
                            raw_unapplied_reason_map.get(key)
                            or self._derive_default_filter_reason(
                                mapping_type=self._normalize_filter_mapping_type(resolved_channel_type, key),
                                status=(
                                    "query_injected_pending_verification" if key in query_injected_filter_keys
                                    else "unapplied"
                                ),
                            )
                        )
                    ),
                    "verification_detail": dict(query_verification_details.get(key) or {}),
                    "semantic_conclusion": self._derive_semantic_conclusion(
                        mapping_type=self._normalize_filter_mapping_type(resolved_channel_type, key),
                        verification_detail=dict(query_verification_details.get(key) or {}),
                    ),
                    "special_panel_conclusion": self._derive_special_panel_conclusion(
                        mapping_type=self._normalize_filter_mapping_type(resolved_channel_type, key),
                        status=(
                            "applied" if key in applied_filter_keys
                            else "query_injected_pending_verification" if key in query_injected_filter_keys
                            else "unapplied"
                        ),
                        verification_detail=dict(query_verification_details.get(key) or {}),
                    ),
                }
                for key in configured_enabled_filter_keys
            }

        unapplied_reason_map = {
            key: str(
                (filter_status_map.get(key) or {}).get("reason")
                or raw_unapplied_reason_map.get(key)
                or self._derive_default_filter_reason(
                    mapping_type=(filter_status_map.get(key) or {}).get("mapping_type"),
                    status=(filter_status_map.get(key) or {}).get("status"),
                )
            )
            for key in unapplied_filter_keys
        }

        query_injected_query_params = raw_snapshot.get("query_injected_query_params")
        if not isinstance(query_injected_query_params, dict):
            query_injected_query_params = {}

        mapping_stage = str(raw_snapshot.get("mapping_stage") or "").strip() or "snapshot_only"
        mapping_notes = str(raw_snapshot.get("mapping_notes") or "").strip()
        runtime_audit_stage = str(raw_snapshot.get("runtime_audit_stage") or "").strip()
        runtime_audit_source = str(raw_snapshot.get("runtime_audit_source") or "").strip()
        if not mapping_notes:
            if mapping_stage == "query_mapped":
                mapping_notes = "query 候选项已进入最终结果页验证闭环。"
            elif mapping_stage == "mixed":
                mapping_notes = "当前部分筛选项已进入真实映射，其余项仍处于待验证或未应用状态。"
            elif mapping_stage == "ui_automation":
                mapping_notes = "当前筛选项依赖页面控件自动化执行。"
            else:
                mapping_notes = "当前仅记录渠道级配置快照，尚未进入真实抓取 runtime 映射。"

        projected_verification_details = {
            key: dict(
                (
                    (filter_status_map.get(key) or {}).get("verification_detail")
                    or query_verification_details.get(key)
                    or {}
                )
            )
            for key in configured_enabled_filter_keys
            if isinstance(
                (
                    (filter_status_map.get(key) or {}).get("verification_detail")
                    or query_verification_details.get(key)
                    or {}
                ),
                dict,
            )
            and (
                (filter_status_map.get(key) or {}).get("verification_detail")
                or query_verification_details.get(key)
            )
        }

        return {
            "channel_id": resolved_channel_id,
            "channel_type": resolved_channel_type,
            "filters": dict(normalized_filters),
            "configured_filters": dict(normalized_filters),
            "supported_filter_keys": list(supported_filter_keys),
            "filter_labels": {
                key: self._normalize_filter_label(resolved_channel_type, key)
                for key in supported_filter_keys
            },
            "configured_filter_keys": list(configured_enabled_filter_keys),
            "configured_filter_count": len(configured_enabled_filter_keys),
            "enabled_filter_keys": list(configured_enabled_filter_keys),
            "configured_enabled_filter_keys": list(configured_enabled_filter_keys),
            "query_injected_filter_keys": list(query_injected_filter_keys),
            "query_injected_filter_count": len(query_injected_filter_keys),
            "query_injected_query_params": dict(query_injected_query_params),
            "verification_details": {
                key: dict(detail or {})
                for key, detail in projected_verification_details.items()
                if isinstance(detail, dict)
            },
            "query_verification_details": {
                key: dict(detail or {})
                for key, detail in projected_verification_details.items()
                if isinstance(detail, dict)
            },
            "applied_filters": {key: True for key in applied_filter_keys},
            "applied_filter_keys": list(applied_filter_keys),
            "applied_filter_count": len(applied_filter_keys),
            "unapplied_filters": {key: True for key in unapplied_filter_keys},
            "unapplied_filter_keys": list(unapplied_filter_keys),
            "unapplied_filter_count": len(unapplied_filter_keys),
            "unapplied_reason_map": dict(unapplied_reason_map),
            "filter_status_map": filter_status_map,
            "mapping_stage": mapping_stage,
            "mapping_notes": mapping_notes,
            "runtime_audit_stage": runtime_audit_stage,
            "runtime_audit_source": runtime_audit_source,
        }

    def get_channel_search_filter_snapshot(
        self,
        channel_id: str | None = None,
        channel_type: str | None = None,
        crawl_cfg: Dict[str, Any] | None = None,
        source_channels_cfg: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        source_channels_cfg = source_channels_cfg or self.get_source_channels_config()
        channels = source_channels_cfg.get("channels") or []
        selected_channel = self._pick_enabled_source_channel(
            channels,
            channel_id=channel_id or source_channels_cfg.get("active_channel_id"),
            channel_type=channel_type,
        )
        if not selected_channel:
            return self.normalize_channel_search_filter_snapshot({
                "channel_id": "",
                "channel_type": str(channel_type or "").strip(),
                "filters": {},
                "mapping_stage": "snapshot_only",
            })

        selected_channel_type = selected_channel.get("channel_type") or ""
        filters = self.get_channel_search_filters(
            channel_id=selected_channel.get("channel_id"),
            crawl_cfg=crawl_cfg,
            source_channels_cfg=source_channels_cfg,
        )
        supported_filter_keys = self._get_supported_channel_search_filter_keys(selected_channel_type)
        return self.normalize_channel_search_filter_snapshot({
            "channel_id": selected_channel.get("channel_id") or "",
            "channel_type": selected_channel_type,
            "filters": filters,
            "supported_filter_keys": supported_filter_keys,
            "mapping_stage": "snapshot_only",
        })

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

    def _resolve_runtime_path(self, raw_path: str | None) -> Path | None:
        if not raw_path:
            return None
        path = Path(str(raw_path).strip()).expanduser()
        if not path.is_absolute():
            path = (BASE_DIR / path).resolve()
        return path

    def _is_runtime_state_file_usable(self, channel_type: str | None, state_file: str | None) -> bool:
        if channel_type != "ali1688":
            return bool(state_file)
        state_path = self._resolve_runtime_path(state_file)
        if not state_path or not state_path.exists():
            return False
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                state_data = json.load(f)
            cookies = state_data.get("cookies") or []
            cookie_names = {
                str(item.get("name") or "")
                for item in cookies
                if isinstance(item, dict)
            }
            required = {"cookie2", "_m_h5_tk", "_m_h5_tk_enc", "ali_apache_id", "cna"}
            return bool(cookies) and bool(cookie_names.intersection(required))
        except Exception:
            return False

    def get_crawl_source_account_runtimes(
        self,
        channel_type: str | None = None,
        only_usable: bool = False,
    ) -> List[Dict[str, Any]]:
        crawl_cfg = self.get_crawl_config()
        source_channels_cfg = self.get_source_channels_config()
        channel_map = {
            item.get("channel_id"): item
            for item in (source_channels_cfg.get("channels") or [])
            if item.get("channel_id")
        }

        results: List[Dict[str, Any]] = []
        for selected_channel in crawl_cfg.get("enabled_source_channels", []):
            if selected_channel.get("enabled", True) is False:
                continue
            channel_id = selected_channel.get("channel_id")
            channel_cfg = channel_map.get(channel_id)
            if not channel_cfg:
                continue
            if channel_type and channel_cfg.get("channel_type") != channel_type:
                continue
            if channel_cfg.get("enabled", True) is False:
                continue

            accounts = channel_cfg.get("accounts") or []
            selected_account_ids = self._filter_source_account_ids(
                accounts,
                selected_channel.get("account_ids"),
            )
            if not selected_account_ids:
                continue

            for account_id in selected_account_ids:
                account_cfg = next(
                    (item for item in accounts if item.get("account_id") == account_id),
                    None,
                )
                if not account_cfg or account_cfg.get("enabled", True) is False:
                    continue
                runtime = self.build_source_channel_account_runtime(
                    channel_cfg.get("channel_type"),
                    channel_cfg.get("channel_id"),
                    account_id,
                )
                runtime_entry = {
                    "channel_type": channel_cfg.get("channel_type"),
                    "channel_id": channel_cfg.get("channel_id"),
                    "channel_label": channel_cfg.get("label") or channel_cfg.get("channel_id") or "",
                    "account_id": account_cfg.get("account_id"),
                    "account_label": account_cfg.get("label") or account_cfg.get("account_id") or "",
                    "label": account_cfg.get("label") or account_cfg.get("account_id") or "",
                    "enabled": True,
                    "is_configured": True,
                    "error_message": "",
                    **runtime,
                }
                runtime_entry["is_usable"] = self._is_runtime_state_file_usable(
                    runtime_entry.get("channel_type"),
                    runtime_entry.get("state_file"),
                )
                if only_usable and not runtime_entry["is_usable"]:
                    continue
                results.append(runtime_entry)

        return results

    def get_effective_crawl_source_runtime(
        self,
        channel_type: str | None = None,
        rotation_index: int = 0,
    ) -> Dict[str, Any]:
        candidates = self.get_crawl_source_account_runtimes(
            channel_type=channel_type,
            only_usable=True,
        )
        if not candidates:
            return {}
        safe_index = max(int(rotation_index or 0), 0) % len(candidates)
        return candidates[safe_index]

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
        channel_label = (
            active_channel.get("label")
            or any_ali1688_channel.get("label")
            or "1688 货源渠道"
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
                "channel_label": channel_label,
                "account_id": "",
                "account_label": "",
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
            "channel_label": channel_label,
            "account_id": account.get("account_id"),
            "account_label": account.get("label") or account.get("account_id") or "",
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
