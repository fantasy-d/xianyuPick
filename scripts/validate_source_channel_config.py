from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = BASE_DIR / "src"
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.xianyu_tools.config import settings
from src.xianyu_tools.channel_search_filters import (
    get_ali1688_channel_search_filter_keys,
    get_ali1688_channel_search_filter_meta,
    get_ali1688_query_filter_definitions,
    get_ali1688_query_mapped_filter_keys,
)
from src.xianyu_tools.source_channel_config import (
    normalize_source_channels_config,
    strip_source_channel_runtime_fields,
)
from src.xianyu_tools.source_adapter.ali1688 import (
    apply_ali1688_query_filters_to_url,
    build_ali1688_query_filter_expectation,
    build_ali1688_query_filter_params,
    get_ali1688_query_filter_definition,
    verify_ali1688_query_filters_from_url,
)
from scripts.run_ali1688_slow_flow import (
    _mark_runtime_snapshot_non_query_probe,
    _mark_runtime_snapshot_query_navigation_failed,
    _verify_and_mark_runtime_query_snapshot,
)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _build_sample_source_channels() -> dict[str, Any]:
    return normalize_source_channels_config(
        {
            "active_channel_id": "ali1688",
            "channels": [
                {
                    "channel_id": "ali1688",
                    "channel_type": "ali1688",
                    "label": "1688 货源渠道",
                    "enabled": True,
                    "active_account_ids": ["ali1688-account-1", "ali1688-account-2", "bogus-account"],
                    "accounts": [
                        {
                            "account_id": "ali1688-account-1",
                            "label": "1688 账号 1",
                            "enabled": True,
                            "notes": "",
                            "session_report": {
                                "is_logged_in": True,
                                "is_usable": True,
                                "status_text": "登录正常",
                            },
                        },
                        {
                            "account_id": "ali1688-account-2",
                            "label": "1688 账号 2",
                            "enabled": True,
                            "notes": "",
                            "session_report": {
                                "is_logged_in": False,
                                "is_usable": False,
                                "status_text": "未检测到登录",
                            },
                        },
                    ],
                },
                {
                    "channel_id": "manual-1",
                    "channel_type": "custom",
                    "label": "手工渠道",
                    "enabled": True,
                    "active_account_ids": ["manual-1-account-1"],
                    "accounts": [
                        {
                            "account_id": "manual-1-account-1",
                            "label": "手工账号 1",
                            "enabled": True,
                            "notes": "",
                        }
                    ],
                },
            ],
        }
    )


def validate_source_channel_storage_cleanup() -> None:
    raw_cfg = _build_sample_source_channels()
    cleaned = strip_source_channel_runtime_fields(raw_cfg)
    ali1688_account = cleaned["channels"][0]["accounts"][0]
    _assert("state_file" not in ali1688_account, "持久化配置不应保留 state_file")
    _assert("user_data_dir" not in ali1688_account, "持久化配置不应保留 user_data_dir")
    _assert(cleaned["channels"][0]["active_account_ids"] == ["ali1688-account-1", "ali1688-account-2"], "持久化配置应保留有效 active_account_ids 原始集合")


def validate_custom_selected_normalization() -> None:
    source_channels_cfg = _build_sample_source_channels()
    normalized = settings.normalize_crawl_config(
        {
            "source_limit_1688": 12,
            "source_filter_models": ["model-a", "", None],
            "source_channel_selection_mode": "custom_selected",
            "enabled_source_channels": [
                {
                    "channel_id": "ali1688",
                    "enabled": True,
                    "account_ids": ["ali1688-account-1", "ali1688-account-2", "bogus-account"],
                },
                {
                    "channel_id": "bogus-channel",
                    "enabled": True,
                    "account_ids": ["bogus-account"],
                },
            ],
        },
        source_channels_cfg=source_channels_cfg,
    )
    _assert(normalized["source_limit_1688"] == 12, "source_limit_1688 应保留有效整数值")
    _assert(normalized["source_filter_models"] == ["model-a"], "source_filter_models 应过滤空值")
    _assert(len(normalized["enabled_source_channels"]) == 1, "无效渠道应被自动移除")
    selected_accounts = normalized["enabled_source_channels"][0]["account_ids"]
    _assert(selected_accounts == ["ali1688-account-1"], "custom_selected 模式下应只保留可用账号")


def validate_active_pool_fallback() -> None:
    source_channels_cfg = _build_sample_source_channels()
    normalized = settings.normalize_crawl_config(
        {
            "source_channel_selection_mode": "active_pool",
            "enabled_source_channels": [],
        },
        source_channels_cfg=source_channels_cfg,
    )
    _assert(len(normalized["enabled_source_channels"]) == 1, "active_pool 应回落到可用激活渠道")
    selected_entry = normalized["enabled_source_channels"][0]
    _assert(selected_entry["channel_id"] == "ali1688", "active_pool 应优先选择 ali1688 激活渠道")
    _assert(selected_entry["account_ids"] == ["ali1688-account-1"], "active_pool 应只带入登录成功的激活账号")


def validate_runtime_selection() -> None:
    original_get_source_channels_config = settings.get_source_channels_config
    original_get_crawl_config = settings.get_crawl_config
    source_channels_cfg = _build_sample_source_channels()
    crawl_cfg = settings.normalize_crawl_config(
        {
            "source_channel_selection_mode": "custom_selected",
            "enabled_source_channels": [
                {
                    "channel_id": "ali1688",
                    "enabled": True,
                    "account_ids": ["ali1688-account-1"],
                }
            ],
        },
        source_channels_cfg=source_channels_cfg,
    )
    try:
        settings.get_source_channels_config = lambda: source_channels_cfg
        settings.get_crawl_config = lambda: crawl_cfg
        runtimes = settings.get_crawl_source_account_runtimes(channel_type="ali1688", only_usable=False)
        _assert(len(runtimes) == 1, "运行时选择器应返回配置中选中的账号")
        runtime = runtimes[0]
        _assert(runtime["channel_id"] == "ali1688", "运行时条目应保留渠道 ID")
        _assert(runtime["account_id"] == "ali1688-account-1", "运行时条目应保留账号 ID")
        _assert(runtime["channel_label"] == "1688 货源渠道", "运行时条目应保留渠道标签")
    finally:
        settings.get_source_channels_config = original_get_source_channels_config
        settings.get_crawl_config = original_get_crawl_config


def validate_channel_search_filters_normalization() -> None:
    source_channels_cfg = _build_sample_source_channels()
    normalized = settings.normalize_crawl_config(
        {
            "source_channel_selection_mode": "custom_selected",
            "enabled_source_channels": [
                {
                    "channel_id": "ali1688",
                    "enabled": True,
                    "account_ids": ["ali1688-account-1"],
                }
            ],
            "channel_search_filters": [
                {
                    "channel_id": "ali1688",
                    "filters": {
                        "single_piece_drop_shipping": True,
                        "free_shipping": True,
                        "rapid_invoice": False,
                        "bogus_flag": True,
                    },
                },
                {
                    "channel_id": "manual-1",
                    "filters": {
                        "free_shipping": True,
                    },
                },
                {
                    "channel_id": "bogus-channel",
                    "filters": {
                        "single_piece_drop_shipping": True,
                    },
                },
            ],
        },
        source_channels_cfg=source_channels_cfg,
    )
    filters = normalized["channel_search_filters"]
    _assert(len(filters) == 2, "已知渠道都应保留配置容器，非法渠道应被移除")
    ali1688_filters = next(item for item in filters if item["channel_id"] == "ali1688")["filters"]
    _assert("bogus_flag" not in ali1688_filters, "非法筛选字段应被清洗")
    _assert(ali1688_filters["single_piece_drop_shipping"] is True, "合法字段应保留布尔值")
    _assert(ali1688_filters["free_shipping"] is True, "合法字段应保留布尔值")
    _assert(ali1688_filters["selected_distributors"] is False, "缺省字段应补全为 false")
    manual_filters = next(item for item in filters if item["channel_id"] == "manual-1")["filters"]
    _assert(manual_filters == {}, "不支持筛选能力的渠道应保留空 filters")


def validate_channel_search_filters_default_initialization() -> None:
    source_channels_cfg = _build_sample_source_channels()
    normalized = settings.normalize_crawl_config(
        {
            "source_channel_selection_mode": "active_pool",
            "enabled_source_channels": [],
            "channel_search_filters": [],
        },
        source_channels_cfg=source_channels_cfg,
    )
    filters = normalized["channel_search_filters"]
    _assert(len(filters) == 2, "缺省情况下也应为已知渠道补齐筛选配置容器")
    ali1688_filters = next(item for item in filters if item["channel_id"] == "ali1688")["filters"]
    _assert(
        sorted(ali1688_filters.keys()) == sorted(get_ali1688_channel_search_filter_keys()),
        "ali1688 默认筛选容器应补齐全部共享筛选字段",
    )
    _assert(all(value is False for value in ali1688_filters.values()), "ali1688 默认筛选值应全部为 false")
    manual_filters = next(item for item in filters if item["channel_id"] == "manual-1")["filters"]
    _assert(manual_filters == {}, "不支持筛选能力的渠道也应保留空容器，便于前后端对齐")


def validate_channel_search_filter_snapshot_contract() -> None:
    original_get_source_channels_config = settings.get_source_channels_config
    original_get_crawl_config = settings.get_crawl_config
    source_channels_cfg = _build_sample_source_channels()
    crawl_cfg = settings.normalize_crawl_config(
        {
            "source_channel_selection_mode": "custom_selected",
            "enabled_source_channels": [
                {
                    "channel_id": "ali1688",
                    "enabled": True,
                    "account_ids": ["ali1688-account-1"],
                },
                {
                    "channel_id": "manual-1",
                    "enabled": True,
                    "account_ids": ["manual-1-account-1"],
                },
            ],
            "channel_search_filters": [
                {
                    "channel_id": "ali1688",
                    "filters": {
                        "single_piece_drop_shipping": True,
                        "free_shipping": True,
                    },
                },
                {
                    "channel_id": "manual-1",
                    "filters": {
                        "free_shipping": True,
                    },
                },
            ],
        },
        source_channels_cfg=source_channels_cfg,
    )
    try:
        settings.get_source_channels_config = lambda: source_channels_cfg
        settings.get_crawl_config = lambda: crawl_cfg

        ali1688_snapshot = settings.get_channel_search_filter_snapshot(
            channel_id="ali1688",
            channel_type="ali1688",
            crawl_cfg=crawl_cfg,
            source_channels_cfg=source_channels_cfg,
        )
        _assert(ali1688_snapshot["configured_filters"] == ali1688_snapshot["filters"], "配置快照应保留 configured_filters 别名")
        _assert(
            ali1688_snapshot["configured_enabled_filter_keys"] == ali1688_snapshot["enabled_filter_keys"],
            "配置快照应统一 enabled_filter_keys 与 configured_enabled_filter_keys 口径",
        )
        _assert(
            ali1688_snapshot["configured_filter_keys"] == ali1688_snapshot["configured_enabled_filter_keys"],
            "配置快照应补齐 configured_filter_keys 契约别名",
        )
        _assert(
            ali1688_snapshot["configured_filter_count"] == 2,
            "配置快照应补齐 configured_filter_count 计数摘要",
        )
        _assert(
            ali1688_snapshot["unapplied_filter_keys"] == ["single_piece_drop_shipping", "free_shipping"],
            "配置快照应把已启用筛选项初始化为未应用集合",
        )
        _assert(
            ali1688_snapshot["mapping_stage"] == "snapshot_only",
            "配置态快照应默认处于 snapshot_only",
        )
        _assert(
            ali1688_snapshot["filter_status_map"]["single_piece_drop_shipping"]["mapping_type"] == "query_candidate",
            "配置态快照应补齐每项筛选的 mapping_type 元信息",
        )
        _assert(
            ali1688_snapshot["filter_status_map"]["single_piece_drop_shipping"]["mapping_stage"] == "snapshot_only",
            "未进入 runtime 的筛选项应默认保持 snapshot_only 阶段",
        )
        _assert(
            ali1688_snapshot["filter_status_map"]["single_piece_drop_shipping"]["group"] == "distribution_capability",
            "配置态快照应补齐每项筛选所属分组",
        )

        manual_snapshot = settings.get_channel_search_filter_snapshot(
            channel_id="manual-1",
            channel_type="custom",
            crawl_cfg=crawl_cfg,
            source_channels_cfg=source_channels_cfg,
        )
        _assert(manual_snapshot["filters"] == {}, "非 1688 渠道快照应返回空 filters")
        _assert(manual_snapshot["configured_enabled_filter_keys"] == [], "非 1688 渠道不应产生启用筛选项")
        _assert(manual_snapshot["filter_status_map"] == {}, "非 1688 渠道不应伪造筛选状态")
    finally:
        settings.get_source_channels_config = original_get_source_channels_config
        settings.get_crawl_config = original_get_crawl_config


def validate_channel_search_filter_snapshot_normalization() -> None:
    legacy_snapshot = {
        "channel_id": "ali1688",
        "channel_type": "ali1688",
        "configured_filters": {
            "single_piece_drop_shipping": True,
            "free_shipping": True,
        },
        "query_injected_filter_keys": ["single_piece_drop_shipping"],
        "query_verification_details": {
            "single_piece_drop_shipping": {
                "matched_params": {"offerTags": "1988226"},
            }
        },
        "mapping_stage": "mixed",
    }
    normalized = settings.normalize_channel_search_filter_snapshot(legacy_snapshot)
    _assert(normalized["filters"]["single_piece_drop_shipping"] is True, "旧快照应被补齐 filters 别名")
    _assert(normalized["configured_filters"]["free_shipping"] is True, "旧快照应保留 configured_filters")
    _assert(
        normalized["configured_enabled_filter_keys"] == ["single_piece_drop_shipping", "free_shipping"],
        "旧快照应能恢复启用筛选项集合",
    )
    _assert(
        normalized["filter_status_map"]["single_piece_drop_shipping"]["status"] == "query_injected_pending_verification",
        "旧快照中的 query 注入状态应被恢复",
    )
    _assert(
        normalized["filter_status_map"]["single_piece_drop_shipping"]["mapping_type"] == "query_candidate",
        "旧快照归一化后应补齐 query 候选项的 mapping_type",
    )
    _assert(
        normalized["filter_status_map"]["single_piece_drop_shipping"]["mapping_stage"] == "query_candidate",
        "旧快照中的 query 注入项应恢复为 query_candidate 阶段",
    )
    _assert(
        normalized["verification_details"]["single_piece_drop_shipping"]["matched_params"]["offerTags"] == "1988226",
        "旧快照应补齐 verification_details 契约别名",
    )
    _assert(
        normalized["filter_status_map"]["free_shipping"]["status"] == "unapplied",
        "未显式进入 runtime 的筛选项应回落到 unapplied",
    )
    _assert(
        normalized["mapping_notes"] != "",
        "归一化后的快照应自动补齐 mapping_notes",
    )


def validate_channel_search_filter_runtime_state_projection() -> None:
    runtime_snapshot = {
        "channel_id": "ali1688",
        "channel_type": "ali1688",
        "configured_filters": {
            "single_piece_drop_shipping": True,
            "free_shipping": True,
            "rapid_invoice": True,
        },
        "configured_enabled_filter_keys": [
            "single_piece_drop_shipping",
            "free_shipping",
            "rapid_invoice",
        ],
        "query_injected_filter_keys": [
            "single_piece_drop_shipping",
            "rapid_invoice",
        ],
        "applied_filter_keys": [
            "single_piece_drop_shipping",
        ],
        "unapplied_filter_keys": [
            "free_shipping",
            "rapid_invoice",
        ],
        "query_verification_details": {
            "single_piece_drop_shipping": {
                "matched_params": {"offerTags": "1988226"},
            },
            "rapid_invoice": {
                "expected_values": ["1013"],
                "observed_values": [],
            },
        },
        "filter_status_map": {
            "single_piece_drop_shipping": {
                "configured": True,
                "status": "applied",
                "reason": "",
            },
            "free_shipping": {
                "configured": True,
                "status": "unapplied",
                "reason": "query_filter_not_applied_in_runtime",
            },
            "rapid_invoice": {
                "configured": True,
                "status": "query_injected_pending_verification",
                "reason": "query_filter_injected_pending_verification",
            },
        },
        "mapping_stage": "mixed",
    }
    normalized = settings.normalize_channel_search_filter_snapshot(runtime_snapshot)
    _assert(normalized["applied_filter_keys"] == ["single_piece_drop_shipping"], "已生效集合应保留单独命中的 query 项")
    _assert(
        normalized["filter_status_map"]["single_piece_drop_shipping"]["status"] == "applied",
        "命中的 query 项应保持 applied 状态",
    )
    _assert(
        normalized["filter_status_map"]["single_piece_drop_shipping"]["mapping_stage"] == "query_mapped",
        "命中的 query 项应升级为 query_mapped 阶段",
    )
    _assert(
        normalized["filter_status_map"]["rapid_invoice"]["status"] == "query_injected_pending_verification",
        "已注入但未验证项应保持 query_injected_pending_verification 状态",
    )
    _assert(
        normalized["filter_status_map"]["rapid_invoice"]["mapping_stage"] == "query_candidate",
        "已注入待验证项应保持 query_candidate 阶段",
    )
    _assert(
        normalized["filter_status_map"]["free_shipping"]["reason"] == "query_filter_not_applied_in_runtime",
        "未进入 runtime 的 query 候选项应保留明确原因",
    )
    _assert(
        normalized["applied_filter_count"] == 1 and normalized["unapplied_filter_count"] == 1 and normalized["query_injected_filter_count"] == 1,
        "runtime 态归一化后应补齐 applied / unapplied / query_injected 计数摘要",
    )
    _assert(
        normalized["verification_details"]["single_piece_drop_shipping"]["matched_params"]["offerTags"] == "1988226",
        "runtime 态归一化后应保留 applied 项的验证详情",
    )


def validate_channel_search_filter_verification_detail_projection() -> None:
    normalized = settings.normalize_channel_search_filter_snapshot(
        {
            "channel_id": "ali1688",
            "channel_type": "ali1688",
            "filters": {
                "single_piece_drop_shipping": True,
                "free_shipping": True,
            },
            "filter_status_map": {
                "single_piece_drop_shipping": {
                    "status": "applied",
                    "mapping_stage": "query_mapped",
                    "verification_detail": {
                        "matched_params": {"offerTags": "1988226"},
                        "verification_mode": "post_navigation_url",
                    },
                },
                "free_shipping": {
                    "status": "query_injected_pending_verification",
                    "mapping_stage": "query_candidate",
                    "verification_detail": {
                        "expected_values": ["1"],
                    },
                },
            },
        }
    )
    _assert(
        normalized["verification_details"]["single_piece_drop_shipping"]["matched_params"]["offerTags"] == "1988226",
        "顶层 verification_details 应投影 filter_status_map 中的 applied 验证细节",
    )
    _assert(
        normalized["query_verification_details"]["single_piece_drop_shipping"]["verification_mode"] == "post_navigation_url",
        "query_verification_details 应同步投影 verification_mode，便于前端统一消费",
    )
    _assert(
        normalized["verification_details"]["free_shipping"]["expected_values"] == ["1"],
        "待验证项的 verification_detail 也应投影到顶层快照",
    )


def validate_channel_search_filter_default_reason_by_mapping_type() -> None:
    normalized = settings.normalize_channel_search_filter_snapshot(
        {
            "channel_id": "ali1688",
            "channel_type": "ali1688",
            "filters": {
                "selected_distributors": True,
                "seven_day_return": True,
                "single_piece_free_shipping": True,
                "real_factory_verified": True,
                "strength_verified": True,
                "encrypted_waybill": True,
            },
        }
    )
    _assert(
        normalized["filter_status_map"]["selected_distributors"]["reason"] == "ui_selector_not_stable",
        "DOM checkbox 候选项在未进入 runtime 时应给出 ui_selector_not_stable 默认原因",
    )
    _assert(
        normalized["filter_status_map"]["selected_distributors"]["verification_entry"] == "search_result_checkbox",
        "分销严选应在快照中保留结果页 checkbox 验证入口",
    )
    _assert(
        normalized["filter_status_map"]["seven_day_return"]["verification_entry"] == "search_result_checkbox",
        "7天无理由应在快照中保留结果页 checkbox 验证入口",
    )
    _assert(
        normalized["filter_status_map"]["real_factory_verified"]["verification_entry"] == "search_result_checkbox",
        "真实工厂认证应在快照中保留结果页 checkbox 验证入口",
    )
    _assert(
        normalized["filter_status_map"]["strength_verified"]["verification_entry"] == "search_result_checkbox",
        "实力认证应在快照中保留结果页 checkbox 验证入口",
    )
    _assert(
        normalized["filter_status_map"]["single_piece_free_shipping"]["reason"] == "semantic_combo_not_confirmed",
        "组合语义候选项在未确认前应给出 semantic_combo_not_confirmed 默认原因",
    )
    _assert(
        normalized["filter_status_map"]["single_piece_free_shipping"]["semantic_dependencies"] == [
            "single_piece_drop_shipping",
            "free_shipping",
        ],
        "组合语义候选项应在快照中保留依赖项定义",
    )
    _assert(
        normalized["filter_status_map"]["single_piece_free_shipping"]["verification_entry"] == "search_result_semantic_combo",
        "组合语义候选项应在快照中保留验证入口定义",
    )
    _assert(
        normalized["filter_status_map"]["encrypted_waybill"]["reason"] == "special_panel_unmapped",
        "特殊入口候选项在未映射前应给出 special_panel_unmapped 默认原因",
    )
    _assert(
        normalized["filter_status_map"]["encrypted_waybill"]["verification_entry"] == "config_filter_panel",
        "特殊入口候选项应在快照中保留验证入口定义",
    )
    _assert(
        normalized["filter_status_map"]["encrypted_waybill"]["mapping_hint"] != "",
        "特殊入口候选项应在快照中保留映射提示",
    )


def validate_ali1688_query_filter_definition_contract() -> None:
    logistics = get_ali1688_query_filter_definition("official_logistics")
    _assert(logistics["param"] == "filtOfferTags", "官方物流应统一走 filtOfferTags 参数桶")
    _assert(
        logistics["verify_alias_params"] == ["filtOfferTags", "offerTags"],
        "官方物流应显式保留 URL 验证别名集合",
    )
    expectation = build_ali1688_query_filter_expectation("rapid_invoice")
    _assert(expectation["mapping_type"] == "query_candidate", "极速开票应标记为 query_candidate")
    _assert(expectation["expected_values"] == ["1013"], "极速开票应保留预期参数值")


def validate_shared_channel_search_filter_definition_contract() -> None:
    all_keys = get_ali1688_channel_search_filter_keys()
    _assert(len(all_keys) == 11, "共享筛选定义应稳定覆盖 11 个 1688 搜索筛选项")
    _assert(all_keys[0] == "rapid_invoice", "共享筛选定义应保持稳定顺序，避免前后端展示漂移")

    selected_meta = get_ali1688_channel_search_filter_meta("selected_distributors")
    _assert(
        selected_meta["mapping_type"] == "ui_checkbox_candidate",
        "分销严选应在共享定义中标记为 ui_checkbox_candidate",
    )
    _assert(
        selected_meta["verification_entry"] == "search_result_checkbox",
        "分销严选应在共享定义中标记结果页 checkbox 验证入口",
    )
    _assert(
        selected_meta["mapping_hint"] != "",
        "分销严选应在共享定义中保留映射提示",
    )

    encrypted_meta = get_ali1688_channel_search_filter_meta("encrypted_waybill")
    _assert(
        encrypted_meta["mapping_type"] == "special_panel_candidate",
        "密文面单应在共享定义中标记为 special_panel_candidate",
    )
    semantic_meta = get_ali1688_channel_search_filter_meta("single_piece_free_shipping")
    _assert(
        semantic_meta["semantic_dependencies"] == ["single_piece_drop_shipping", "free_shipping"],
        "1件代发包邮应在共享定义中保留组合依赖项",
    )
    _assert(
        semantic_meta["verification_entry"] == "search_result_semantic_combo",
        "1件代发包邮应在共享定义中标记结果页组合语义验证入口",
    )
    _assert(
        encrypted_meta["verification_entry"] == "config_filter_panel",
        "密文面单应在共享定义中标记配置筛选面板入口",
    )

    query_definitions = get_ali1688_query_filter_definitions()
    query_keys = get_ali1688_query_mapped_filter_keys()
    _assert(
        query_keys == list(query_definitions.keys()),
        "共享 query 键列表应与共享 query 定义保持同一来源",
    )
    _assert(
        sorted(query_keys) == sorted(["rapid_invoice", "single_piece_drop_shipping", "free_shipping", "freight_insurance_return", "official_logistics"]),
        "共享 query 候选集合应覆盖当前计划中的 5 个 query 候选项",
    )
    _assert(
        query_definitions["single_piece_drop_shipping"]["verify_alias_params"] == ["filtOfferTags", "offerTags"],
        "共享 query 定义应保留一件代发的 URL 验证别名集合",
    )


def validate_non_query_filter_runtime_html_probe() -> None:
    runtime_snapshot = settings.normalize_channel_search_filter_snapshot(
        {
            "channel_id": "ali1688",
            "channel_type": "ali1688",
            "configured_filters": {
                "selected_distributors": True,
                "single_piece_drop_shipping": True,
                "free_shipping": True,
                "single_piece_free_shipping": True,
                "encrypted_waybill": True,
            },
            "configured_enabled_filter_keys": [
                "selected_distributors",
                "single_piece_drop_shipping",
                "free_shipping",
                "single_piece_free_shipping",
                "encrypted_waybill",
            ],
            "mapping_stage": "mixed",
        }
    )
    next_snapshot = _mark_runtime_snapshot_non_query_probe(
        runtime_snapshot,
        observed_page_text="""
            <html>
              <body>
                <div>分销严选</div>
                <div>1件代发包邮</div>
                <div>密文面单</div>
              </body>
            </html>
        """,
        result_url="https://s.1688.com/selloffer/offer_search.htm?keywords=test",
    )

    selected_meta = next_snapshot["filter_status_map"]["selected_distributors"]
    semantic_meta = next_snapshot["filter_status_map"]["single_piece_free_shipping"]
    encrypted_meta = next_snapshot["filter_status_map"]["encrypted_waybill"]
    query_meta = next_snapshot["filter_status_map"]["single_piece_drop_shipping"]

    _assert(
        selected_meta["verification_detail"]["probe_mode"] == "html_text_scan",
        "DOM checkbox 候选项应记录 html_text_scan 探测模式",
    )
    _assert(
        selected_meta["verification_detail"]["matched_terms"] == ["分销严选"],
        "分销严选命中时应保留匹配到的 probe term",
    )
    _assert(
        selected_meta["verification_detail"]["text_visible"] is True,
        "分销严选命中时应标记 text_visible=true",
    )
    _assert(
        semantic_meta["verification_detail"]["matched_terms"] == ["1件代发包邮"],
        "组合语义候选项命中时应保留对应 probe term",
    )
    _assert(
        semantic_meta["verification_detail"]["semantic_dependencies"] == ["single_piece_drop_shipping", "free_shipping"],
        "组合语义候选项应在 runtime 探测详情中保留依赖项",
    )
    _assert(
        semantic_meta["verification_detail"]["dependencies_enabled"] is True,
        "当依赖项均已配置启用时，组合语义候选项应标记 dependencies_enabled=true",
    )
    _assert(
        semantic_meta["reason"] == "snapshot_only_until_semantics_confirmed",
        "组合语义候选项在页面命中且依赖齐备时，应升级为更具体的待确认原因",
    )
    _assert(
        semantic_meta["mapping_stage"] == "mixed",
        "组合语义候选项在页面命中且依赖齐备时，应标记已进入更真实的 runtime 观察阶段",
    )
    _assert(
        encrypted_meta["verification_detail"]["matched_terms"] == ["密文面单"],
        "特殊入口候选项命中时应保留对应 probe term",
    )
    _assert(
        encrypted_meta["verification_detail"]["result_url"].startswith("https://s.1688.com/"),
        "非 query 探测应保留当前结果页 URL 证据",
    )
    _assert(
        query_meta.get("verification_detail", {}) == {},
        "query 型候选项不应被 html_text_scan 探测逻辑覆盖",
    )


def validate_non_query_filter_runtime_html_probe_without_dependencies() -> None:
    runtime_snapshot = settings.normalize_channel_search_filter_snapshot(
        {
            "channel_id": "ali1688",
            "channel_type": "ali1688",
            "configured_filters": {
                "single_piece_free_shipping": True,
            },
            "configured_enabled_filter_keys": [
                "single_piece_free_shipping",
            ],
            "mapping_stage": "snapshot_only",
        }
    )
    next_snapshot = _mark_runtime_snapshot_non_query_probe(
        runtime_snapshot,
        observed_page_text="<div>1件代发包邮</div>",
        result_url="https://s.1688.com/selloffer/offer_search.htm?keywords=test",
    )
    semantic_meta = next_snapshot["filter_status_map"]["single_piece_free_shipping"]
    _assert(
        semantic_meta["verification_detail"]["dependencies_enabled"] is False,
        "当依赖项未同时启用时，组合语义候选项不应误判为依赖齐备",
    )
    _assert(
        semantic_meta["reason"] == "semantic_combo_not_confirmed",
        "当依赖项未齐时，组合语义候选项仍应保持默认待确认原因",
    )
    _assert(
        semantic_meta["mapping_stage"] == "snapshot_only",
        "当依赖项未齐时，组合语义候选项不应升级到更强的 runtime 观察阶段",
    )


def validate_ali1688_query_filter_param_merging() -> None:
    query_params, applied_filter_keys = build_ali1688_query_filter_params(
        {
            "single_piece_drop_shipping": True,
            "official_logistics": True,
            "free_shipping": True,
        }
    )
    _assert(
        query_params["filtOfferTags"] == "1988226,98306,235906,2484802",
        "同参数桶筛选项应按顺序合并而不是互相覆盖",
    )
    _assert(query_params["freeShipping"] == "1", "独立参数桶应保留最终值")
    _assert(
        applied_filter_keys == ["single_piece_drop_shipping", "official_logistics", "free_shipping"],
        "已启用 query 项应保留稳定的 applied_filter_keys 顺序",
    )


def validate_ali1688_query_filter_url_verification() -> None:
    result_url, observed_query, injected_filter_keys = apply_ali1688_query_filters_to_url(
        "https://s.1688.com/selloffer/offer_search.htm?keywords=test&offerTags=1988226",
        {
            "single_piece_drop_shipping": True,
            "freight_insurance_return": True,
            "rapid_invoice": True,
        },
    )
    _assert("complexTags" in observed_query, "组合 query 注入后应包含 complexTags 参数桶")
    verified_filter_keys, _observed_query, verification_details = verify_ali1688_query_filters_from_url(
        result_url,
        injected_filter_keys,
    )
    _assert("single_piece_drop_shipping" in verified_filter_keys, "一件代发应支持 offerTags 别名验证")
    _assert("freight_insurance_return" in verified_filter_keys, "退货包运费应在最终 URL 中被验证命中")
    _assert("rapid_invoice" in verified_filter_keys, "极速开票应在最终 URL 中被验证命中")
    _assert(
        verification_details["single_piece_drop_shipping"]["matched_params"]["offerTags"] == "1988226",
        "一件代发验证详情应回写命中的别名参数值",
    )


def validate_query_filter_in_place_runtime_verification() -> None:
    runtime_snapshot = settings.normalize_channel_search_filter_snapshot(
        {
            "channel_id": "ali1688",
            "channel_type": "ali1688",
            "configured_filters": {
                "single_piece_drop_shipping": True,
                "free_shipping": False,
            },
            "configured_enabled_filter_keys": ["single_piece_drop_shipping"],
            "mapping_stage": "snapshot_only",
        }
    )
    result_url, observed_query, injected_filter_keys = apply_ali1688_query_filters_to_url(
        "https://s.1688.com/selloffer/offer_search.htm?keywords=test&offerTags=1988226",
        {"single_piece_drop_shipping": True},
    )
    _assert(result_url.startswith("https://s.1688.com/"), "结果 URL 应保持 1688 搜索页域名")
    _assert(observed_query.get("offerTags") == "1988226", "原始结果 URL 已包含一件代发别名参数")
    next_snapshot, verified_filter_keys, verified_query_params, verification_details = _verify_and_mark_runtime_query_snapshot(
        runtime_snapshot,
        result_url=result_url,
        injected_filter_keys=injected_filter_keys,
        applied_query_params=observed_query,
        logger=None,
        verification_mode="in_place_url",
    )
    _assert(verified_filter_keys == ["single_piece_drop_shipping"], "当前 URL 已命中别名参数时应直接完成 in-place 验证")
    _assert(
        next_snapshot["mapping_stage"] == "query_mapped",
        "当唯一 query 项已在当前 URL 中验证通过时，应升级为 query_mapped",
    )
    _assert(
        next_snapshot["applied_filter_keys"] == ["single_piece_drop_shipping"],
        "当前 URL 命中的单个 query 项应写入 applied_filter_keys",
    )
    _assert(
        next_snapshot["filter_status_map"]["single_piece_drop_shipping"]["status"] == "applied",
        "当前 URL 命中的单个 query 项状态应升级为 applied",
    )
    _assert(
        verification_details["single_piece_drop_shipping"]["matched_params"]["offerTags"] == "1988226",
        "in-place 验证应保留命中的别名参数详情",
    )
    _assert(
        next_snapshot["filter_status_map"]["single_piece_drop_shipping"]["verification_detail"]["verification_mode"] == "in_place_url",
        "in-place 验证应明确记录 verification_mode",
    )
    _assert(
        verified_query_params.get("offerTags") == "1988226",
        "in-place 验证应保留当前结果 URL 的原始观察参数",
    )


def validate_query_filter_multi_item_mixed_runtime_verification() -> None:
    configured_filters = {
        "official_logistics": True,
        "free_shipping": True,
        "freight_insurance_return": True,
        "rapid_invoice": True,
    }
    _query_params, injected_filter_keys = build_ali1688_query_filter_params(configured_filters)
    runtime_snapshot = settings.normalize_channel_search_filter_snapshot(
        {
            "channel_id": "ali1688",
            "channel_type": "ali1688",
            "configured_filters": configured_filters,
            "configured_enabled_filter_keys": injected_filter_keys,
            "mapping_stage": "snapshot_only",
        }
    )
    result_url = (
        "https://s.1688.com/selloffer/offer_search.htm"
        "?keywords=test"
        "&filtOfferTags=2484802"
        "&freeShipping=1"
        "&complexTags=1001"
    )
    next_snapshot, verified_filter_keys, verified_query_params, verification_details = _verify_and_mark_runtime_query_snapshot(
        runtime_snapshot,
        result_url=result_url,
        injected_filter_keys=injected_filter_keys,
        applied_query_params={
            "filtOfferTags": "2484802",
            "freeShipping": "1",
            "complexTags": "1001",
        },
        logger=None,
        verification_mode="post_navigation_url",
    )
    _assert(
        sorted(verified_filter_keys) == ["free_shipping", "freight_insurance_return", "official_logistics"],
        "同类 query 候选项应能分别按目标值命中，而不是整桶一起误判",
    )
    _assert(
        next_snapshot["mapping_stage"] == "mixed",
        "部分 query 项命中、部分未命中时，应保持 mixed",
    )
    _assert(
        next_snapshot["filter_status_map"]["official_logistics"]["status"] == "applied",
        "官方物流命中时应升级为 applied",
    )
    _assert(
        next_snapshot["filter_status_map"]["free_shipping"]["status"] == "applied",
        "包邮命中时应升级为 applied",
    )
    _assert(
        next_snapshot["filter_status_map"]["freight_insurance_return"]["status"] == "applied",
        "退货包运费命中时应升级为 applied",
    )
    _assert(
        next_snapshot["filter_status_map"]["rapid_invoice"]["status"] == "query_injected_pending_verification",
        "极速开票未命中时应保持 query_injected_pending_verification",
    )
    _assert(
        next_snapshot["filter_status_map"]["rapid_invoice"]["reason"] == "query_filter_injected_pending_verification",
        "未命中的 query 候选项应在 filter_status_map 中保留待验证原因",
    )
    _assert(
        verification_details["official_logistics"]["matched_params"]["filtOfferTags"] == "2484802",
        "官方物流应保留同桶命中的参数详情",
    )
    _assert(
        verification_details["rapid_invoice"]["expected_values"] == ["1013"],
        "极速开票未命中时仍应保留目标值说明",
    )
    _assert(
        next_snapshot["filter_status_map"]["official_logistics"]["verification_detail"]["verification_mode"] == "post_navigation_url",
        "导航后验证应明确记录 verification_mode",
    )
    _assert(
        verified_query_params["complexTags"] == "1001",
        "混合态验证应保留最终观察到的参数桶值",
    )


def validate_query_filter_repeated_query_param_verification() -> None:
    verified_filter_keys, observed_query, verification_details = verify_ali1688_query_filters_from_url(
        (
            "https://s.1688.com/selloffer/offer_search.htm"
            "?keywords=test"
            "&complexTags=1001"
            "&complexTags=1013"
        ),
        ["freight_insurance_return", "rapid_invoice"],
    )
    _assert(
        sorted(verified_filter_keys) == ["freight_insurance_return", "rapid_invoice"],
        "重复 query 参数场景下，应能同时命中同桶里的多个筛选项",
    )
    _assert(
        observed_query["complexTags"] == "1001,1013",
        "重复 query 参数应在观察结果中合并为稳定的 CSV 值",
    )
    _assert(
        verification_details["rapid_invoice"]["matched_values"] == ["1013"],
        "极速开票应能从重复的 complexTags 参数中识别自己的目标值",
    )
    _assert(
        verification_details["freight_insurance_return"]["matched_values"] == ["1001"],
        "退货包运费应能从重复的 complexTags 参数中识别自己的目标值",
    )


def validate_query_filter_navigation_failed_runtime_projection() -> None:
    runtime_snapshot = settings.normalize_channel_search_filter_snapshot(
        {
            "channel_id": "ali1688",
            "channel_type": "ali1688",
            "configured_filters": {
                "single_piece_drop_shipping": True,
                "free_shipping": True,
            },
            "configured_enabled_filter_keys": [
                "single_piece_drop_shipping",
                "free_shipping",
            ],
            "mapping_stage": "snapshot_only",
        }
    )
    next_snapshot = _mark_runtime_snapshot_query_navigation_failed(
        runtime_snapshot,
        attempted_filter_keys=["single_piece_drop_shipping"],
        attempted_query_params={"filtOfferTags": "1988226,98306,235906"},
        attempted_result_url="https://s.1688.com/selloffer/offer_search.htm?keywords=test&filtOfferTags=1988226,98306,235906",
    )
    _assert(
        next_snapshot["mapping_stage"] == "mixed",
        "query 导航失败但已尝试注入时，应保留 mixed 以表示 runtime 已触及真实映射路径",
    )
    _assert(
        next_snapshot["filter_status_map"]["single_piece_drop_shipping"]["reason"] == "query_filter_navigation_failed",
        "导航失败的首个 query 项应保留明确失败原因",
    )
    _assert(
        next_snapshot["filter_status_map"]["single_piece_drop_shipping"]["mapping_stage"] == "query_candidate",
        "导航失败的首个 query 项仍应保留 query_candidate 阶段，而不是退回 snapshot_only",
    )
    _assert(
        next_snapshot["filter_status_map"]["single_piece_drop_shipping"]["verification_detail"]["verification_mode"] == "navigation_failed",
        "导航失败的首个 query 项应记录 verification_mode=navigation_failed",
    )
    _assert(
        next_snapshot["filter_status_map"]["single_piece_drop_shipping"]["verification_detail"]["attempted_result_url"].startswith("https://s.1688.com/"),
        "导航失败时应保留尝试跳转的结果页 URL 证据",
    )
    _assert(
        next_snapshot["filter_status_map"]["free_shipping"]["reason"] == "query_filter_not_applied_in_runtime",
        "未参与本次 query 尝试的候选项仍应保持未进入 runtime 的原因",
    )


def main() -> None:
    validators = [
        ("source_channel_storage_cleanup", validate_source_channel_storage_cleanup),
        ("custom_selected_normalization", validate_custom_selected_normalization),
        ("active_pool_fallback", validate_active_pool_fallback),
        ("runtime_selection", validate_runtime_selection),
        ("channel_search_filters_normalization", validate_channel_search_filters_normalization),
        ("channel_search_filters_default_initialization", validate_channel_search_filters_default_initialization),
        ("channel_search_filter_snapshot_contract", validate_channel_search_filter_snapshot_contract),
        ("channel_search_filter_snapshot_normalization", validate_channel_search_filter_snapshot_normalization),
        ("channel_search_filter_runtime_state_projection", validate_channel_search_filter_runtime_state_projection),
        ("channel_search_filter_verification_detail_projection", validate_channel_search_filter_verification_detail_projection),
        ("channel_search_filter_default_reason_by_mapping_type", validate_channel_search_filter_default_reason_by_mapping_type),
        ("shared_channel_search_filter_definition_contract", validate_shared_channel_search_filter_definition_contract),
        ("non_query_filter_runtime_html_probe", validate_non_query_filter_runtime_html_probe),
        ("non_query_filter_runtime_html_probe_without_dependencies", validate_non_query_filter_runtime_html_probe_without_dependencies),
        ("ali1688_query_filter_definition_contract", validate_ali1688_query_filter_definition_contract),
        ("ali1688_query_filter_param_merging", validate_ali1688_query_filter_param_merging),
        ("ali1688_query_filter_url_verification", validate_ali1688_query_filter_url_verification),
        ("query_filter_in_place_runtime_verification", validate_query_filter_in_place_runtime_verification),
        ("query_filter_multi_item_mixed_runtime_verification", validate_query_filter_multi_item_mixed_runtime_verification),
        ("query_filter_repeated_query_param_verification", validate_query_filter_repeated_query_param_verification),
        ("query_filter_navigation_failed_runtime_projection", validate_query_filter_navigation_failed_runtime_projection),
    ]
    results = []
    for name, validator in validators:
        validator()
        results.append({"name": name, "status": "passed"})

    print(json.dumps({"status": "passed", "checks": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
