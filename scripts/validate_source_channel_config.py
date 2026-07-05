from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from playwright.async_api import async_playwright

BASE_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = BASE_DIR / "src"
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.xianyu_tools.config import settings
from src.xianyu_tools.channel_search_filters import (
    get_ali1688_configurable_channel_search_filter_keys,
    get_ali1688_channel_search_filter_keys,
    get_ali1688_channel_search_filter_meta,
    get_ali1688_query_filter_definitions,
    get_ali1688_query_mapped_filter_keys,
)
from src.xianyu_tools.source_channel_config import (
    normalize_source_channels_config,
    strip_source_channel_runtime_fields,
)
from src.web_api.main import (
    _build_task_channel_summary_map,
    _build_detail_channel_group_sort_strategy,
    _build_detail_source_sort_strategy,
    _sort_detail_sources_and_groups,
    _summarize_channel_filter_snapshot,
)
from src.xianyu_tools.source_adapter.ali1688 import (
    apply_ali1688_query_filters_to_url,
    build_ali1688_query_filter_expectation,
    build_ali1688_query_filter_params,
    get_ali1688_query_filter_definition,
    verify_ali1688_query_filters_from_url,
)
from scripts.run_ali1688_slow_flow import (
    _detect_ali1688_filter_layout,
    _extract_dispatch_metrics_from_text,
    _find_filter_entry_locator,
    _apply_visible_filter_toggle_runtime,
    _apply_special_panel_candidate_runtime,
    _mark_runtime_snapshot_non_query_probe,
    _mark_runtime_snapshot_semantic_dependency_combos,
    _mark_runtime_snapshot_query_navigation_failed,
    _verify_and_mark_runtime_query_snapshot,
    _write_runtime_filter_snapshot_audit,
)
from scripts.run_full_pipeline import (
    load_runtime_filter_audit_snapshot,
    select_source_filter_snapshot_for_db,
)
from scripts.inspect_channel_filter_runtime_audit import (
    AUDIT_FILE_NAME,
    AUDIT_REPORT_SCHEMA_VERSION,
    build_runtime_audit_batch_report,
    build_runtime_audit_gate_report,
    build_runtime_audit_report,
    build_runtime_audit_todo_report,
    load_required_filters_from_config,
    runtime_audit_gate_exit_code,
)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate_ali1688_list_metrics_extraction_contract() -> None:
    metrics = _extract_dispatch_metrics_from_text(
        """
        48H揽收100% 24H揽收99%
        月代发1k+ 7天代发600+
        铺货数100内 分销商数400+
        面单支持 入驻1年 汕头市凯姿妮生物科技
        """
    )

    _assert(metrics["pickup_48h_text"] == "48H揽收100%", "应提取 48H 揽收文本")
    _assert(metrics["pickup_24h_text"] == "24H揽收99%", "应提取 24H 揽收文本")
    _assert(metrics["month_dispatch_text"] == "月代发1k+", "应保留月代发原始展示文本")
    _assert(metrics["seven_day_dispatch_text"] == "7天代发600+", "应保留 7 天代发原始展示文本")
    _assert(metrics["listing_count_text"] == "铺货数100内", "应保留铺货数原始展示文本")
    _assert(metrics["distributor_count_text"] == "分销商数400+", "应保留分销商数原始展示文本")
    _assert(metrics["waybill_support_text"] == "面单支持", "应提取面单支持状态")
    _assert(metrics["settled_years_text"] == "入驻1年", "应提取入驻年限")
    _assert(metrics["company_name"] == "汕头市凯姿妮生物科技", "应提取商家名称")
    _assert(metrics["month_dispatch_count"] == 1000, "月代发 1k+ 应归一为 1000")
    _assert(metrics["seven_day_dispatch_count"] == 600, "7 天代发 600+ 应归一为 600")
    _assert(metrics["listing_count"] == 100, "铺货数 100 内应归一为 100")
    _assert(metrics["distributor_count"] == 400, "分销商数 400+ 应归一为 400")

    detail_metrics = _extract_dispatch_metrics_from_text(
        """
        近30天代发数量 100以内
        48h揽收率 100.00%
        近7天代发数量 100以内
        24h揽收率 80.00%
        铺货分销商数 300+
        入驻5年
        """
    )

    _assert(detail_metrics["pickup_48h_text"] == "48H揽收100%", "详情页格式应归一 48H 揽收文本")
    _assert(detail_metrics["pickup_24h_text"] == "24H揽收80%", "详情页格式应归一 24H 揽收文本")
    _assert(detail_metrics["month_dispatch_text"] == "月代发100以内", "详情页近30天代发数量应映射到月代发")
    _assert(detail_metrics["seven_day_dispatch_text"] == "7天代发100以内", "详情页近7天代发数量应映射到 7 天代发")
    _assert(detail_metrics["distributor_count_text"] == "分销商数300+", "详情页铺货分销商数应映射到分销商数")
    _assert(detail_metrics["settled_years_text"] == "入驻5年", "详情页应提取入驻年限")
    _assert(detail_metrics["month_dispatch_count"] == 100, "详情页月代发 100 以内应归一为 100")
    _assert(detail_metrics["seven_day_dispatch_count"] == 100, "详情页 7 天代发 100 以内应归一为 100")
    _assert(detail_metrics["distributor_count"] == 300, "详情页分销商数 300+ 应归一为 300")


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


def validate_channel_search_filters_per_channel_isolation() -> None:
    source_channels_cfg = normalize_source_channels_config(
        {
            "active_channel_id": "ali1688-a",
            "channels": [
                {
                    "channel_id": "ali1688-a",
                    "channel_type": "ali1688",
                    "label": "1688 渠道 A",
                    "enabled": True,
                    "active_account_ids": ["ali1688-a-account-1"],
                    "accounts": [
                        {
                            "account_id": "ali1688-a-account-1",
                            "label": "1688 A 账号 1",
                            "enabled": True,
                            "session_report": {"is_logged_in": True, "is_usable": True},
                        }
                    ],
                },
                {
                    "channel_id": "ali1688-b",
                    "channel_type": "ali1688",
                    "label": "1688 渠道 B",
                    "enabled": True,
                    "active_account_ids": ["ali1688-b-account-1"],
                    "accounts": [
                        {
                            "account_id": "ali1688-b-account-1",
                            "label": "1688 B 账号 1",
                            "enabled": True,
                            "session_report": {"is_logged_in": True, "is_usable": True},
                        }
                    ],
                },
            ],
        }
    )
    crawl_cfg = settings.normalize_crawl_config(
        {
            "source_channel_selection_mode": "custom_selected",
            "enabled_source_channels": [
                {"channel_id": "ali1688-a", "enabled": True, "account_ids": ["ali1688-a-account-1"]},
                {"channel_id": "ali1688-b", "enabled": True, "account_ids": ["ali1688-b-account-1"]},
            ],
            "channel_search_filters": [
                {
                    "channel_id": "ali1688-a",
                    "filters": {
                        "single_piece_drop_shipping": True,
                        "free_shipping": True,
                    },
                },
                {
                    "channel_id": "ali1688-b",
                    "filters": {
                        "rapid_invoice": True,
                        "official_logistics": True,
                    },
                },
            ],
        },
        source_channels_cfg=source_channels_cfg,
    )

    a_filters = settings.get_channel_search_filters(
        channel_id="ali1688-a",
        channel_type="ali1688",
        crawl_cfg=crawl_cfg,
        source_channels_cfg=source_channels_cfg,
    )
    b_filters = settings.get_channel_search_filters(
        channel_id="ali1688-b",
        channel_type="ali1688",
        crawl_cfg=crawl_cfg,
        source_channels_cfg=source_channels_cfg,
    )

    _assert(a_filters["single_piece_drop_shipping"] is True, "渠道 A 应保留自己的一件代发配置")
    _assert(a_filters["free_shipping"] is True, "渠道 A 应保留自己的包邮配置")
    _assert(a_filters["rapid_invoice"] is False, "渠道 A 不应串入渠道 B 的极速开票配置")
    _assert(a_filters["official_logistics"] is False, "渠道 A 不应串入渠道 B 的官方物流配置")

    _assert(b_filters["rapid_invoice"] is True, "渠道 B 应保留自己的极速开票配置")
    _assert(b_filters["official_logistics"] is True, "渠道 B 应保留自己的官方物流配置")
    _assert(b_filters["single_piece_drop_shipping"] is False, "渠道 B 不应串入渠道 A 的一件代发配置")
    _assert(b_filters["free_shipping"] is False, "渠道 B 不应串入渠道 A 的包邮配置")

    a_snapshot = settings.get_channel_search_filter_snapshot(
        channel_id="ali1688-a",
        channel_type="ali1688",
        crawl_cfg=crawl_cfg,
        source_channels_cfg=source_channels_cfg,
    )
    b_snapshot = settings.get_channel_search_filter_snapshot(
        channel_id="ali1688-b",
        channel_type="ali1688",
        crawl_cfg=crawl_cfg,
        source_channels_cfg=source_channels_cfg,
    )

    _assert(
        a_snapshot["configured_enabled_filter_keys"] == ["single_piece_drop_shipping", "free_shipping"],
        "渠道 A 快照应只回读自身启用筛选项",
    )
    _assert(
        b_snapshot["configured_enabled_filter_keys"] == ["rapid_invoice", "official_logistics"],
        "渠道 B 快照应只回读自身启用筛选项",
    )
    _assert(
        "rapid_invoice" not in a_snapshot["configured_enabled_filter_keys"],
        "渠道 A 未启用的极速开票不应误读为已启用",
    )
    _assert(
        "single_piece_drop_shipping" not in b_snapshot["configured_enabled_filter_keys"],
        "渠道 B 未启用的一件代发不应误读为已启用",
    )
    _assert(
        "rapid_invoice" not in a_snapshot["filter_status_map"],
        "渠道 A 的 filter_status_map 不应串入渠道 B 的已启用筛选项",
    )
    _assert(
        "single_piece_drop_shipping" not in b_snapshot["filter_status_map"],
        "渠道 B 的 filter_status_map 不应串入渠道 A 的已启用筛选项",
    )


def validate_channel_search_filters_follow_active_channel_selection() -> None:
    source_channels_cfg = normalize_source_channels_config(
        {
            "active_channel_id": "ali1688-b",
            "channels": [
                {
                    "channel_id": "ali1688-a",
                    "channel_type": "ali1688",
                    "label": "1688 渠道 A",
                    "enabled": True,
                    "active_account_ids": ["ali1688-a-account-1"],
                    "accounts": [
                        {
                            "account_id": "ali1688-a-account-1",
                            "label": "1688 A 账号 1",
                            "enabled": True,
                            "session_report": {"is_logged_in": True, "is_usable": True},
                        }
                    ],
                },
                {
                    "channel_id": "ali1688-b",
                    "channel_type": "ali1688",
                    "label": "1688 渠道 B",
                    "enabled": True,
                    "active_account_ids": ["ali1688-b-account-1"],
                    "accounts": [
                        {
                            "account_id": "ali1688-b-account-1",
                            "label": "1688 B 账号 1",
                            "enabled": True,
                            "session_report": {"is_logged_in": True, "is_usable": True},
                        }
                    ],
                },
            ],
        }
    )
    crawl_cfg = settings.normalize_crawl_config(
        {
            "source_channel_selection_mode": "custom_selected",
            "enabled_source_channels": [
                {"channel_id": "ali1688-a", "enabled": True, "account_ids": ["ali1688-a-account-1"]},
                {"channel_id": "ali1688-b", "enabled": True, "account_ids": ["ali1688-b-account-1"]},
            ],
            "channel_search_filters": [
                {
                    "channel_id": "ali1688-a",
                    "filters": {
                        "single_piece_drop_shipping": True,
                    },
                },
                {
                    "channel_id": "ali1688-b",
                    "filters": {
                        "rapid_invoice": True,
                        "official_logistics": True,
                    },
                },
            ],
        },
        source_channels_cfg=source_channels_cfg,
    )

    active_filters = settings.get_channel_search_filters(
        crawl_cfg=crawl_cfg,
        source_channels_cfg=source_channels_cfg,
    )
    _assert(active_filters["rapid_invoice"] is True, "省略 channel_id 时应按活动渠道回读筛选配置")
    _assert(active_filters["official_logistics"] is True, "活动渠道的已启用筛选项应被默认回读")
    _assert(
        active_filters["single_piece_drop_shipping"] is False,
        "省略 channel_id 时不应误读非活动渠道的一件代发配置",
    )

    active_snapshot = settings.get_channel_search_filter_snapshot(
        crawl_cfg=crawl_cfg,
        source_channels_cfg=source_channels_cfg,
    )
    _assert(active_snapshot["channel_id"] == "ali1688-b", "省略 channel_id 时快照应绑定活动渠道")
    _assert(
        active_snapshot["configured_enabled_filter_keys"] == ["rapid_invoice", "official_logistics"],
        "省略 channel_id 时快照应只回读活动渠道的启用项",
    )
    _assert(
        "single_piece_drop_shipping" not in active_snapshot["filter_status_map"],
        "活动渠道快照不应串入其他渠道的启用筛选项",
    )


def validate_channel_search_filters_unsupported_channel_stays_empty() -> None:
    source_channels_cfg = _build_sample_source_channels()
    crawl_cfg = settings.normalize_crawl_config(
        {
            "source_channel_selection_mode": "custom_selected",
            "enabled_source_channels": [
                {
                    "channel_id": "manual-1",
                    "enabled": True,
                    "account_ids": ["manual-1-account-1"],
                }
            ],
            "channel_search_filters": [
                {
                    "channel_id": "manual-1",
                    "filters": {
                        "free_shipping": True,
                        "rapid_invoice": True,
                    },
                }
            ],
        },
        source_channels_cfg=source_channels_cfg,
    )

    manual_filters = settings.get_channel_search_filters(
        channel_id="manual-1",
        channel_type="custom",
        crawl_cfg=crawl_cfg,
        source_channels_cfg=source_channels_cfg,
    )
    _assert(manual_filters == {}, "不支持搜索筛选能力的渠道回读结果必须保持空字典")

    manual_snapshot = settings.get_channel_search_filter_snapshot(
        channel_id="manual-1",
        channel_type="custom",
        crawl_cfg=crawl_cfg,
        source_channels_cfg=source_channels_cfg,
    )
    _assert(manual_snapshot["filters"] == {}, "不支持能力的渠道快照不应伪造 filters")
    _assert(manual_snapshot["supported_filter_keys"] == [], "不支持能力的渠道不应暴露共享筛选字段")
    _assert(manual_snapshot["configured_enabled_filter_keys"] == [], "不支持能力的渠道不应出现启用筛选项")
    _assert(manual_snapshot["configured_filter_count"] == 0, "不支持能力的渠道启用计数应为 0")
    _assert(manual_snapshot["filter_status_map"] == {}, "不支持能力的渠道不应伪造筛选状态")
    _assert(manual_snapshot["verification_details"] == {}, "不支持能力的渠道不应伪造验证详情")
    _assert(manual_snapshot["query_verification_details"] == {}, "不支持能力的渠道不应伪造 query 验证详情")


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


def validate_semantic_combo_verification_detail_projection() -> None:
    normalized = settings.normalize_channel_search_filter_snapshot(
        {
            "channel_id": "ali1688",
            "channel_type": "ali1688",
            "configured_filters": {
                "single_piece_free_shipping": True,
            },
            "configured_enabled_filter_keys": ["single_piece_free_shipping"],
            "filter_status_map": {
                "single_piece_free_shipping": {
                    "status": "applied",
                    "mapping_type": "semantic_combo_candidate",
                    "mapping_stage": "ui_automation",
                    "verification_detail": {
                        "independent_ui_entry_observed": True,
                        "result_signature_changed": True,
                        "semantic_verification_stage": "direct_entry_result_shift_observed",
                    },
                }
            },
        }
    )
    _assert(
        normalized["verification_details"]["single_piece_free_shipping"]["independent_ui_entry_observed"] is True,
        "组合语义候选项的独立入口证据应投影到顶层 verification_details",
    )
    _assert(
        normalized["verification_details"]["single_piece_free_shipping"]["result_signature_changed"] is True,
        "组合语义候选项的结果签名变化证据应投影到顶层 verification_details",
    )
    _assert(
        normalized["query_verification_details"]["single_piece_free_shipping"]["semantic_verification_stage"]
        == "direct_entry_result_shift_observed",
        "组合语义候选项的阶段证据应同步投影到 query_verification_details，便于前端统一消费",
    )
    _assert(
        normalized["verification_details"]["single_piece_free_shipping"]["semantic_conclusion"]
        == "independent_entry_result_shift_observed",
        "组合语义候选项的统一语义结论应投影到顶层 verification_details",
    )
    _assert(
        normalized["query_verification_details"]["single_piece_free_shipping"]["semantic_conclusion"]
        == "independent_entry_result_shift_observed",
        "组合语义候选项的统一语义结论也应投影到 query_verification_details",
    )
    _assert(
        normalized["filter_status_map"]["single_piece_free_shipping"]["mapping_stage"] == "ui_automation",
        "组合语义候选项在 applied 且缺省回读时应保持 ui_automation 阶段口径",
    )
    _assert(
        normalized["filter_status_map"]["single_piece_free_shipping"]["semantic_conclusion"]
        == "independent_entry_result_shift_observed",
        "组合语义候选项在 filter_status_map 中也应保留统一语义结论",
    )


def validate_special_panel_verification_detail_projection() -> None:
    normalized = settings.normalize_channel_search_filter_snapshot(
        {
            "channel_id": "ali1688",
            "channel_type": "ali1688",
            "configured_filters": {
                "encrypted_waybill": True,
            },
            "configured_enabled_filter_keys": ["encrypted_waybill"],
            "filter_status_map": {
                "encrypted_waybill": {
                    "status": "unapplied",
                    "mapping_type": "special_panel_candidate",
                    "mapping_stage": "mixed",
                    "reason": "special_panel_open_failed",
                    "verification_detail": {
                        "verification_mode": "dom_panel_action",
                        "panel_trigger_clicked": True,
                        "entry_click_attempted": True,
                        "result_signature_changed": False,
                    },
                }
            },
        }
    )
    _assert(
        normalized["verification_details"]["encrypted_waybill"]["special_panel_conclusion"]
        == "panel_open_or_toggle_failed",
        "特殊入口候选项的统一入口结论应投影到顶层 verification_details",
    )
    _assert(
        normalized["query_verification_details"]["encrypted_waybill"]["special_panel_conclusion"]
        == "panel_open_or_toggle_failed",
        "特殊入口候选项的统一入口结论应同步投影到 query_verification_details",
    )
    _assert(
        normalized["filter_status_map"]["encrypted_waybill"]["special_panel_conclusion"]
        == "panel_open_or_toggle_failed",
        "特殊入口候选项在 filter_status_map 中也应保留统一入口结论",
    )


def validate_special_panel_result_shift_observed_projection() -> None:
    normalized = settings.normalize_channel_search_filter_snapshot(
        {
            "channel_id": "ali1688",
            "channel_type": "ali1688",
            "configured_filters": {
                "encrypted_waybill": True,
            },
            "configured_enabled_filter_keys": ["encrypted_waybill"],
            "filter_status_map": {
                "encrypted_waybill": {
                    "status": "applied",
                    "mapping_type": "special_panel_candidate",
                    "mapping_stage": "ui_automation",
                    "verification_detail": {
                        "verification_mode": "dom_panel_action",
                        "panel_trigger_clicked": True,
                        "entry_click_attempted": True,
                        "entry_click_succeeded": True,
                        "result_signature_changed": True,
                    },
                }
            },
        }
    )
    _assert(
        normalized["verification_details"]["encrypted_waybill"]["special_panel_conclusion"]
        == "panel_action_result_shift_observed",
        "特殊入口候选项在结果变化成功态下，应把统一入口结论投影到顶层 verification_details",
    )
    _assert(
        normalized["query_verification_details"]["encrypted_waybill"]["special_panel_conclusion"]
        == "panel_action_result_shift_observed",
        "特殊入口候选项在结果变化成功态下，也应把统一入口结论投影到 query_verification_details",
    )
    _assert(
        normalized["filter_status_map"]["encrypted_waybill"]["special_panel_conclusion"]
        == "panel_action_result_shift_observed",
        "特殊入口候选项在 filter_status_map 中也应保留结果变化成功态的统一入口结论",
    )


def validate_semantic_combo_no_result_shift_projection() -> None:
    normalized = settings.normalize_channel_search_filter_snapshot(
        {
            "channel_id": "ali1688",
            "channel_type": "ali1688",
            "configured_filters": {
                "single_piece_free_shipping": True,
            },
            "configured_enabled_filter_keys": ["single_piece_free_shipping"],
            "filter_status_map": {
                "single_piece_free_shipping": {
                    "status": "applied",
                    "mapping_type": "semantic_combo_candidate",
                    "mapping_stage": "ui_automation",
                    "verification_detail": {
                        "independent_ui_entry_observed": True,
                        "result_signature_changed": False,
                        "semantic_verification_stage": "direct_entry_result_shift_not_observed",
                    },
                }
            },
        }
    )
    _assert(
        normalized["verification_details"]["single_piece_free_shipping"]["semantic_conclusion"]
        == "independent_entry_no_result_shift",
        "组合语义候选项在独立入口动作后未观察到结果变化时，应投影统一语义结论",
    )
    _assert(
        normalized["query_verification_details"]["single_piece_free_shipping"]["semantic_conclusion"]
        == "independent_entry_no_result_shift",
        "组合语义候选项在独立入口动作后未观察到结果变化时，也应同步投影到 query_verification_details",
    )
    _assert(
        normalized["filter_status_map"]["single_piece_free_shipping"]["semantic_conclusion"]
        == "independent_entry_no_result_shift",
        "组合语义候选项在 filter_status_map 中也应保留未观察到结果变化的统一语义结论",
    )


def validate_special_panel_applied_no_result_shift_projection() -> None:
    normalized = settings.normalize_channel_search_filter_snapshot(
        {
            "channel_id": "ali1688",
            "channel_type": "ali1688",
            "configured_filters": {
                "encrypted_waybill": True,
            },
            "configured_enabled_filter_keys": ["encrypted_waybill"],
            "filter_status_map": {
                "encrypted_waybill": {
                    "status": "applied",
                    "mapping_type": "special_panel_candidate",
                    "mapping_stage": "ui_automation",
                    "verification_detail": {
                        "verification_mode": "dom_panel_action",
                        "panel_trigger_clicked": True,
                        "entry_click_attempted": True,
                        "entry_click_succeeded": True,
                        "result_signature_changed": False,
                    },
                }
            },
        }
    )
    _assert(
        normalized["verification_details"]["encrypted_waybill"]["special_panel_conclusion"]
        == "panel_action_applied_no_result_shift",
        "特殊入口候选项在动作成功但未观察到结果变化时，应投影统一入口结论",
    )
    _assert(
        normalized["query_verification_details"]["encrypted_waybill"]["special_panel_conclusion"]
        == "panel_action_applied_no_result_shift",
        "特殊入口候选项在动作成功但未观察到结果变化时，也应同步投影到 query_verification_details",
    )
    _assert(
        normalized["filter_status_map"]["encrypted_waybill"]["special_panel_conclusion"]
        == "panel_action_applied_no_result_shift",
        "特殊入口候选项在 filter_status_map 中也应保留动作成功但未观察到结果变化的统一入口结论",
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
        normalized["filter_labels"]["selected_distributors"] == "分销严选",
        "快照应投影共享筛选定义中的中文标签，供 UI 与审计报告统一展示",
    )
    _assert(
        normalized["filter_status_map"]["encrypted_waybill"]["label"] == "密文面单",
        "filter_status_map 中每个筛选项应保留中文标签，便于解释缺口",
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
    _assert(len(all_keys) == 12, "共享筛选定义应稳定覆盖 12 个 1688 搜索筛选项")
    _assert(all_keys[0] == "rapid_invoice", "共享筛选定义应保持稳定顺序，避免前后端展示漂移")
    labels_by_key = {
        key: get_ali1688_channel_search_filter_meta(key)["label"]
        for key in all_keys
    }
    _assert(
        labels_by_key == {
            "rapid_invoice": "极速开票",
            "selected_distributors": "分销严选",
            "single_piece_drop_shipping": "一件代发",
            "seven_day_return": "7天无理由",
            "single_piece_free_shipping": "1件代发包邮",
            "free_shipping": "包邮",
            "freight_insurance_return": "退货包运费",
            "real_factory_verified": "真实工厂认证",
            "strength_verified": "实力认证",
            "official_logistics": "官方物流",
            "encrypted_waybill": "密文面单",
            "douyin_encrypted_waybill": "抖音面单",
        },
        "共享筛选定义必须覆盖截图中的中文能力标签，避免 UI / 审计报告散落硬编码",
    )

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
    douyin_waybill_meta = get_ali1688_channel_search_filter_meta("douyin_encrypted_waybill")
    configurable_keys = get_ali1688_configurable_channel_search_filter_keys()
    _assert(
        encrypted_meta["mapping_type"] == "special_panel_candidate",
        "密文面单应在共享定义中标记为 special_panel_candidate",
    )
    _assert(
        encrypted_meta["is_parent"] is True and encrypted_meta["is_configurable"] is False,
        "密文面单应作为父级面板入口保留，但不能作为可勾选配置项",
    )
    _assert(
        "encrypted_waybill" not in configurable_keys,
        "密文面单父级入口不应出现在可配置筛选项列表中",
    )
    _assert(
        douyin_waybill_meta["mapping_type"] == "special_panel_candidate",
        "抖音面单应在共享定义中标记为 special_panel_candidate",
    )
    _assert(
        douyin_waybill_meta["parent_key"] == "encrypted_waybill"
        and douyin_waybill_meta["parent_label"] == "密文面单",
        "抖音面单应挂在密文面单父级入口下",
    )
    _assert(
        "douyin_encrypted_waybill" in configurable_keys,
        "抖音面单子选项应出现在可配置筛选项列表中",
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
    _assert(
        encrypted_meta["observation_scope"] == "result_page_text",
        "密文面单应在共享定义中标记当前入口线索的观察范围",
    )
    _assert(
        encrypted_meta["entry_signal_type"] == "text_term",
        "密文面单应在共享定义中标记当前入口线索类型",
    )
    _assert(
        encrypted_meta["next_required_action"] == "panel_open_and_toggle",
        "密文面单应在共享定义中标记下一步待补齐的动作链路",
    )
    _assert(
        "密文面单：抖音面单" in douyin_waybill_meta["probe_terms"],
        "抖音面单应识别 1688 图搜页的密文面单子选项 chip",
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
        selected_meta["verification_detail"]["observation_scope"] == "result_page_text",
        "非 query 页面探测应明确记录证据来自结果页文本",
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
        semantic_meta["verification_detail"]["semantic_verification_stage"] == "dependency_pair_enabled",
        "当依赖项齐备但尚未进入真实动作前，组合语义候选项应记录依赖对已开启阶段",
    )
    _assert(
        semantic_meta["verification_detail"]["semantic_conclusion"] == "dependency_pair_ready_pending_runtime",
        "当依赖项齐备但尚未进入真实动作前，组合语义候选项应沉淀统一语义结论字段",
    )
    _assert(
        next_snapshot["verification_details"]["single_piece_free_shipping"]["semantic_conclusion"]
        == "dependency_pair_ready_pending_runtime",
        "组合语义候选项在 html_text_scan 中的统一语义结论也应投影到顶层 verification_details",
    )
    _assert(
        next_snapshot["query_verification_details"]["single_piece_free_shipping"]["semantic_conclusion"]
        == "dependency_pair_ready_pending_runtime",
        "组合语义候选项在 html_text_scan 中的统一语义结论也应投影到 query_verification_details",
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
        encrypted_meta["reason"] == "special_panel_entry_detected_unmapped",
        "特殊入口候选项在页面命中时，应升级为已识别入口但尚未映射动作链路的状态",
    )
    _assert(
        encrypted_meta["verification_detail"]["entry_signal_detected"] is True,
        "特殊入口候选项在页面命中时，应明确记录入口线索已被观察到",
    )
    _assert(
        encrypted_meta["verification_detail"]["special_panel_conclusion"] == "entry_signal_detected_pending_panel_mapping",
        "特殊入口候选项在仅观察到入口线索时，应沉淀统一入口结论字段",
    )
    _assert(
        next_snapshot["verification_details"]["encrypted_waybill"]["special_panel_conclusion"]
        == "entry_signal_detected_pending_panel_mapping",
        "特殊入口候选项在 html_text_scan 中的统一入口结论也应投影到顶层 verification_details",
    )
    _assert(
        next_snapshot["query_verification_details"]["encrypted_waybill"]["special_panel_conclusion"]
        == "entry_signal_detected_pending_panel_mapping",
        "特殊入口候选项在 html_text_scan 中的统一入口结论也应投影到 query_verification_details",
    )
    _assert(
        encrypted_meta["verification_detail"]["entry_signal_type"] == "text_term",
        "特殊入口候选项应明确记录当前入口线索来源类型",
    )
    _assert(
        encrypted_meta["verification_detail"]["next_required_action"] == "panel_open_and_toggle",
        "特殊入口候选项应明确记录下一步仍需补齐的动作链路",
    )
    _assert(
        encrypted_meta["observation_scope"] == "result_page_text",
        "特殊入口候选项应把观察范围投影到快照层 filter_status_map",
    )
    _assert(
        encrypted_meta["entry_signal_type"] == "text_term",
        "特殊入口候选项应把入口线索类型投影到快照层 filter_status_map",
    )
    _assert(
        encrypted_meta["next_required_action"] == "panel_open_and_toggle",
        "特殊入口候选项应把下一步动作提示投影到快照层 filter_status_map",
    )
    _assert(
        encrypted_meta["mapping_stage"] == "mixed",
        "特殊入口候选项在页面命中时，应标记已进入更真实的 runtime 观察阶段",
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
        semantic_meta["verification_detail"]["semantic_verification_stage"] == "dependency_pair_incomplete",
        "当依赖项未齐时，组合语义候选项应记录依赖对未齐阶段",
    )
    _assert(
        semantic_meta["verification_detail"]["semantic_conclusion"] == "dependency_pair_incomplete",
        "当依赖项未齐时，组合语义候选项应沉淀统一语义结论字段",
    )
    _assert(
        next_snapshot["verification_details"]["single_piece_free_shipping"]["semantic_conclusion"]
        == "dependency_pair_incomplete",
        "当依赖项未齐时，组合语义候选项的统一语义结论也应投影到顶层 verification_details",
    )
    _assert(
        next_snapshot["query_verification_details"]["single_piece_free_shipping"]["semantic_conclusion"]
        == "dependency_pair_incomplete",
        "当依赖项未齐时，组合语义候选项的统一语义结论也应投影到 query_verification_details",
    )
    _assert(
        semantic_meta["reason"] == "semantic_combo_not_confirmed",
        "当依赖项未齐时，组合语义候选项仍应保持默认待确认原因",
    )
    _assert(
        semantic_meta["mapping_stage"] == "snapshot_only",
        "当依赖项未齐时，组合语义候选项不应升级到更强的 runtime 观察阶段",
    )


async def _run_special_panel_candidate_runtime_validation(
    *,
    should_apply: bool,
    layout: str = "standard",
) -> dict[str, Any]:
    runtime_snapshot = settings.normalize_channel_search_filter_snapshot(
        {
            "channel_id": "ali1688",
            "channel_type": "ali1688",
            "configured_filters": {
                "encrypted_waybill": True,
            },
            "configured_enabled_filter_keys": ["encrypted_waybill"],
            "mapping_stage": "snapshot_only",
        }
    )
    if layout == "image_result" and should_apply:
        html_content = """
        <html>
          <body>
            <div class="filterHeader">
              <div class="configFilter--mock">
                <div
                  id="encrypted-label"
                  class="configLabel--mock"
                  role="button"
                  aria-checked="false"
                >
                  密文面单
                </div>
              </div>
            </div>
            <div id="results">
              <div data-result-item data-id="item-1">面板前结果 1</div>
              <div data-result-item data-id="item-2">面板前结果 2</div>
            </div>
            <script>
              const label = document.getElementById('encrypted-label');
              const results = document.getElementById('results');
              label.addEventListener('click', () => {
                const checked = label.getAttribute('aria-checked') === 'true';
                label.setAttribute('aria-checked', checked ? 'false' : 'true');
                label.classList.toggle('is-checked', !checked);
                results.innerHTML = checked
                  ? '<div data-result-item data-id="item-1">面板前结果 1</div><div data-result-item data-id="item-2">面板前结果 2</div>'
                  : '<div data-result-item data-id="item-3">面板后结果 3</div>';
              });
            </script>
          </body>
        </html>
        """
    elif layout == "image_active_condition" and should_apply:
        html_content = """
        <html>
          <body>
            <div class="configFilter--mock">
              <span class="configLabel--mock">密文面单：抖音面单</span>
            </div>
            <div class="filterBottomOptions--mock">
              <div class="bottomFilterOption--mock" role="checkbox" aria-checked="false">
                <span class="optionLabel--mock">密文面单</span>
              </div>
            </div>
            <div id="results">
              <div data-result-item data-id="item-1">已筛选结果 1</div>
              <div data-result-item data-id="item-2">已筛选结果 2</div>
            </div>
          </body>
        </html>
        """
    elif should_apply:
        html_content = """
        <html>
          <body>
            <button id="panel-trigger" onclick="document.getElementById('panel').style.display='block'">配置筛选</button>
            <div id="panel" style="display:none">
              <label id="encrypted-label" class="filter-item">
                <input id="encrypted-input" type="checkbox" />
                <span>密文面单</span>
              </label>
            </div>
            <div id="results">
              <div data-result-item data-id="item-1">面板前结果 1</div>
              <div data-result-item data-id="item-2">面板前结果 2</div>
            </div>
            <script>
              const label = document.getElementById('encrypted-label');
              const input = document.getElementById('encrypted-input');
              const results = document.getElementById('results');
              label.addEventListener('click', () => {
                input.checked = !input.checked;
                label.classList.toggle('is-checked', input.checked);
                label.setAttribute('aria-checked', input.checked ? 'true' : 'false');
                results.innerHTML = input.checked
                  ? '<div data-result-item data-id="item-3">面板后结果 3</div>'
                  : '<div data-result-item data-id="item-1">面板前结果 1</div><div data-result-item data-id="item-2">面板前结果 2</div>';
              });
            </script>
          </body>
        </html>
        """
    else:
        html_content = """
        <html>
          <body>
            <button id="panel-trigger" onclick="document.getElementById('panel').style.display='block'">配置筛选</button>
            <div id="panel" style="display:none">
              <div>密文面单</div>
            </div>
          </body>
        </html>
        """
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(html_content)
        next_snapshot = await _apply_special_panel_candidate_runtime(page, runtime_snapshot)
        await browser.close()
    return next_snapshot


async def _run_visible_filter_toggle_runtime_validation(
    *,
    filter_key: str,
    html_content: str,
) -> dict[str, Any]:
    runtime_snapshot = settings.normalize_channel_search_filter_snapshot(
        {
            "channel_id": "ali1688",
            "channel_type": "ali1688",
            "configured_filters": {
                filter_key: True,
            },
            "configured_enabled_filter_keys": [filter_key],
            "mapping_stage": "snapshot_only",
        }
    )
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(html_content)
        next_snapshot = await _apply_visible_filter_toggle_runtime(page, runtime_snapshot)
        await browser.close()
    return next_snapshot


async def _run_filter_selector_probe(
    *,
    html_content: str,
    term: str,
) -> tuple[str, str]:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(html_content)
        layout_name = await _detect_ali1688_filter_layout(page)
        locator, strategy, _locator_resolution = await _find_filter_entry_locator(page, term, layout_name=layout_name)
        await browser.close()
    _assert(locator is not None, f"应能为 {term} 找到可操作入口")
    return layout_name, strategy


def validate_visible_filter_toggle_runtime_apply_for_ui_checkbox() -> None:
    next_snapshot = asyncio.run(
        _run_visible_filter_toggle_runtime_validation(
            filter_key="selected_distributors",
            html_content="""
            <html>
              <body>
                <div class="filterBottomOptions--mock">
                  <div id="entry" class="bottomFilterOption--mock" role="checkbox" aria-checked="false">
                    <div class="checkboxWrapper--mock"><div class="checkbox--mock"></div></div>
                    <span class="optionLabel--mock">分销严选</span>
                  </div>
                </div>
                <div id="results">
                  <div data-result-item data-id="alpha">货源 A</div>
                  <div data-result-item data-id="beta">货源 B</div>
                </div>
                <script>
                  const entry = document.getElementById('entry');
                  const results = document.getElementById('results');
                  entry.addEventListener('click', () => {
                    const checked = entry.getAttribute('aria-checked') === 'true';
                    entry.setAttribute('aria-checked', checked ? 'false' : 'true');
                    entry.classList.toggle('is-checked', !checked);
                    results.innerHTML = checked
                      ? '<div data-result-item data-id="alpha">货源 A</div><div data-result-item data-id="beta">货源 B</div>'
                      : '<div data-result-item data-id="gamma">货源 G</div>';
                  });
                </script>
              </body>
            </html>
            """,
        )
    )
    selected_meta = next_snapshot["filter_status_map"]["selected_distributors"]
    _assert(selected_meta["status"] == "applied", "图搜结果页可见 checkbox 候选项在点击成功后应升级为 applied")
    _assert(selected_meta["mapping_stage"] == "ui_automation", "图搜结果页可见 checkbox 候选项在点击成功后应进入 ui_automation")
    _assert(
        selected_meta["verification_detail"]["page_filter_layout"] == "image_result_filter_bar",
        "图搜结果页 checkbox 候选项应识别为 image_result_filter_bar",
    )
    _assert(
        selected_meta["verification_detail"]["entry_selector_strategy"] == "image_bottom_filter_option",
        "图搜结果页 checkbox 候选项应优先点击 bottomFilterOption 容器",
    )
    _assert(
        selected_meta["verification_detail"]["selector_resolution_mode"] == "selector_candidate",
        "图搜结果页 checkbox 候选项命中稳定容器时应记录 selector_candidate 解析模式",
    )
    _assert(
        selected_meta["verification_detail"]["text_fallback_considered"] is False,
        "图搜结果页 checkbox 候选项命中稳定容器时不应标记 text fallback 已参与",
    )
    _assert(
        selected_meta["verification_detail"]["selector_candidates_tried"][0]["strategy"] == "image_config_filter",
        "图搜结果页 selector 诊断应保留优先尝试顺序",
    )
    _assert(
        selected_meta["verification_detail"]["result_signature_changed"] is True,
        "图搜结果页 checkbox 候选项在动作成功后应记录结果页签名变化",
    )
    _assert(
        selected_meta["verification_detail"]["verification_mode"] == "dom_toggle_action",
        "图搜结果页 checkbox 候选项在动作成功后应明确记录 dom_toggle_action 校验方式",
    )


def validate_visible_filter_toggle_runtime_apply_for_url_change_without_selected_state() -> None:
    next_snapshot = asyncio.run(
        _run_visible_filter_toggle_runtime_validation(
            filter_key="selected_distributors",
            html_content="""
            <html>
              <body>
                <div class="filterBottomOptions--mock">
                  <div id="entry" class="bottomFilterOption--mock" role="checkbox" aria-checked="false">
                    <span class="optionLabel--mock">分销严选</span>
                  </div>
                </div>
                <div id="results">
                  <div data-result-item data-id="alpha">货源 A</div>
                  <div data-result-item data-id="beta">货源 B</div>
                </div>
                <script>
                  const entry = document.getElementById('entry');
                  entry.addEventListener('click', () => {
                    window.location.hash = 'tags=4501825';
                  });
                </script>
              </body>
            </html>
            """,
        )
    )
    selected_meta = next_snapshot["filter_status_map"]["selected_distributors"]
    detail = selected_meta["verification_detail"]
    _assert(
        selected_meta["status"] == "applied",
        "图搜结果页 selected 态不稳定时，点击后 URL 变化也应作为动作生效证据",
    )
    _assert(
        detail["panel_term_selected_after_action"] is False,
        "URL 变化闭环不能伪造 selected 态",
    )
    _assert(
        detail["result_url_changed"] is True,
        "URL 变化闭环应显式记录 result_url_changed",
    )
    report = build_runtime_audit_report({"stage": "visible_filter_toggle_checked", "snapshot": next_snapshot})
    by_key = {item["filter_key"]: item for item in report["filters"]}
    _assert(
        by_key["selected_distributors"]["can_close_real_site_gap"] is True,
        "审计分类器应接受点击后 URL 变化作为分销严选强证据",
    )


def validate_visible_filter_toggle_runtime_apply_for_semantic_combo() -> None:
    next_snapshot = asyncio.run(
        _run_visible_filter_toggle_runtime_validation(
            filter_key="single_piece_free_shipping",
            html_content="""
            <html>
              <body>
                <div class="filterBottomOptions--mock">
                  <div id="entry" class="bottomFilterOption--mock" role="checkbox" aria-checked="false">
                    <div class="checkboxWrapper--mock"><div class="checkbox--mock"></div></div>
                    <span class="optionLabel--mock">1件代发包邮</span>
                  </div>
                </div>
                <div id="results">
                  <div data-result-item data-id="offer-a">组合前结果 A</div>
                  <div data-result-item data-id="offer-b">组合前结果 B</div>
                </div>
                <script>
                  const entry = document.getElementById('entry');
                  const results = document.getElementById('results');
                  entry.addEventListener('click', () => {
                    const checked = entry.getAttribute('aria-checked') === 'true';
                    entry.setAttribute('aria-checked', checked ? 'false' : 'true');
                    entry.classList.toggle('is-checked', !checked);
                    results.innerHTML = checked
                      ? '<div data-result-item data-id="offer-a">组合前结果 A</div><div data-result-item data-id="offer-b">组合前结果 B</div>'
                      : '<div data-result-item data-id="offer-c">组合后结果 C</div>';
                  });
                </script>
              </body>
            </html>
            """,
        )
    )
    semantic_meta = next_snapshot["filter_status_map"]["single_piece_free_shipping"]
    _assert(semantic_meta["status"] == "applied", "当页面存在独立可点击入口时，组合语义候选项也应记录为 applied")
    _assert(
        semantic_meta["mapping_stage"] == "ui_automation",
        "当组合语义候选项通过真实可点击入口完成动作后，应进入 ui_automation 阶段",
    )
    _assert(
        semantic_meta["verification_detail"]["independent_ui_entry_observed"] is True,
        "当图搜结果页存在独立 1件代发包邮 入口时，应把该证据写入 verification_detail",
    )
    _assert(
        semantic_meta["verification_detail"]["entry_selector_strategy"] == "image_bottom_filter_option",
        "组合语义候选项在图搜结果页应优先点击 bottomFilterOption 容器",
    )
    _assert(
        semantic_meta["verification_detail"]["panel_term_selected_after_action"] is True,
        "组合语义候选项在动作成功后应记录真实选中态",
    )
    _assert(
        semantic_meta["verification_detail"]["result_signature_changed"] is True,
        "组合语义候选项在动作成功后应记录结果页签名变化",
    )
    _assert(
        semantic_meta["verification_detail"]["verification_mode"] == "dom_toggle_action",
        "组合语义候选项通过结果页入口动作成功后应明确记录 dom_toggle_action 校验方式",
    )
    _assert(
        semantic_meta["verification_detail"]["semantic_verification_stage"] == "direct_entry_result_shift_observed",
        "组合语义候选项在独立入口点击且结果签名变化后，应记录更强的结果侧阶段证据",
    )
    _assert(
        semantic_meta["verification_detail"]["semantic_conclusion"] == "independent_entry_result_shift_observed",
        "组合语义候选项在独立入口动作命中结果变化后，应沉淀统一语义结论字段",
    )
    _assert(
        next_snapshot["verification_details"]["single_piece_free_shipping"]["semantic_conclusion"]
        == "independent_entry_result_shift_observed",
        "组合语义候选项在结果变化成功态下，也应把统一语义结论投影到顶层 verification_details",
    )
    _assert(
        next_snapshot["verification_details"]["single_piece_free_shipping"]["semantic_verification_stage"]
        == "direct_entry_result_shift_observed",
        "组合语义候选项在结果变化成功态下，应把阶段证据投影到顶层 verification_details",
    )
    _assert(
        next_snapshot["query_verification_details"]["single_piece_free_shipping"]["semantic_conclusion"]
        == "independent_entry_result_shift_observed",
        "组合语义候选项在结果变化成功态下，也应把统一语义结论投影到 query_verification_details",
    )
    _assert(
        next_snapshot["query_verification_details"]["single_piece_free_shipping"]["semantic_verification_stage"]
        == "direct_entry_result_shift_observed",
        "组合语义候选项在结果变化成功态下，应把阶段证据投影到 query_verification_details",
    )


def validate_visible_filter_toggle_runtime_open_failed_for_ui_checkbox() -> None:
    next_snapshot = asyncio.run(
        _run_visible_filter_toggle_runtime_validation(
            filter_key="selected_distributors",
            html_content="""
            <html>
              <body>
                <div class="filterBottomOptions--mock">
                  <div id="entry" class="bottomFilterOption--mock">
                    <span class="optionLabel--mock">分销严选</span>
                  </div>
                </div>
              </body>
            </html>
            """,
        )
    )
    selected_meta = next_snapshot["filter_status_map"]["selected_distributors"]
    _assert(selected_meta["status"] == "unapplied", "当可见筛选项点击后无选中态证据时，仍应保持 unapplied")
    _assert(
        selected_meta["reason"] == "ui_apply_not_observed",
        "当可见筛选项动作后无选中态证据时，应给出 ui_apply_not_observed 原因",
    )


def validate_visible_filter_toggle_runtime_apply_for_standard_search_layout() -> None:
    next_snapshot = asyncio.run(
        _run_visible_filter_toggle_runtime_validation(
            filter_key="selected_distributors",
            html_content="""
            <html>
              <body>
                <div class="sn-row">
                  <div id="entry" class="search-filt-item" role="checkbox" aria-checked="false">
                    <span>分销严选</span>
                  </div>
                </div>
                <div id="results">
                  <div data-result-item data-id="std-a">标准结果 A</div>
                  <div data-result-item data-id="std-b">标准结果 B</div>
                </div>
                <script>
                  const entry = document.getElementById('entry');
                  const results = document.getElementById('results');
                  entry.addEventListener('click', () => {
                    const checked = entry.getAttribute('aria-checked') === 'true';
                    entry.setAttribute('aria-checked', checked ? 'false' : 'true');
                    entry.classList.toggle('selected', !checked);
                    results.innerHTML = checked
                      ? '<div data-result-item data-id="std-a">标准结果 A</div><div data-result-item data-id="std-b">标准结果 B</div>'
                      : '<div data-result-item data-id="std-c">标准结果 C</div>';
                  });
                </script>
              </body>
            </html>
            """,
        )
    )
    selected_meta = next_snapshot["filter_status_map"]["selected_distributors"]
    _assert(
        selected_meta["status"] == "applied",
        "标准搜索页可见 checkbox 候选项在点击成功后也应升级为 applied",
    )
    _assert(
        selected_meta["verification_detail"]["page_filter_layout"] == "standard_search_filter_bar",
        "标准搜索页 fixture 应识别为 standard_search_filter_bar",
    )
    _assert(
        selected_meta["verification_detail"]["entry_selector_strategy"] == "standard_search_filter_item",
        "标准搜索页应优先点击 search-filt-item 容器",
    )
    _assert(
        selected_meta["verification_detail"]["selector_resolution_mode"] == "selector_candidate",
        "标准搜索页 search-filt-item 结构命中稳定容器时应记录 selector_candidate 解析模式",
    )
    _assert(
        selected_meta["verification_detail"]["text_fallback_considered"] is False,
        "标准搜索页 search-filt-item 结构命中稳定容器时不应标记 text fallback 已参与",
    )
    _assert(
        selected_meta["verification_detail"]["panel_term_selected_after_action"] is True,
        "标准搜索页动作成功后应记录真实选中态",
    )
    _assert(
        selected_meta["verification_detail"]["result_signature_changed"] is True,
        "标准搜索页动作成功后应记录结果页签名变化",
    )


def validate_visible_filter_toggle_runtime_apply_for_standard_search_checkbox_group() -> None:
    checkbox_cases = [
        ("selected_distributors", "分销严选"),
        ("seven_day_return", "7天无理由"),
        ("real_factory_verified", "真实工厂认证"),
        ("strength_verified", "实力认证"),
    ]
    for filter_key, label in checkbox_cases:
        next_snapshot = asyncio.run(
            _run_visible_filter_toggle_runtime_validation(
                filter_key=filter_key,
                html_content=f"""
                <html>
                  <body>
                    <div class="sn-row">
                      <div id="entry" class="search-filt-item" role="checkbox" aria-checked="false">
                        <span>{label}</span>
                      </div>
                    </div>
                    <div id="results">
                      <div data-result-item data-id="std-a">标准结果 A</div>
                      <div data-result-item data-id="std-b">标准结果 B</div>
                    </div>
                    <script>
                      const entry = document.getElementById('entry');
                      const results = document.getElementById('results');
                      entry.addEventListener('click', () => {{
                        const checked = entry.getAttribute('aria-checked') === 'true';
                        entry.setAttribute('aria-checked', checked ? 'false' : 'true');
                        entry.classList.toggle('selected', !checked);
                        results.innerHTML = checked
                          ? '<div data-result-item data-id="std-a">标准结果 A</div><div data-result-item data-id="std-b">标准结果 B</div>'
                          : '<div data-result-item data-id="std-c">{label} 命中后结果</div>';
                      }});
                    </script>
                  </body>
                </html>
                """,
            )
        )
        selected_meta = next_snapshot["filter_status_map"][filter_key]
        _assert(
            selected_meta["status"] == "applied",
            f"标准搜索页 checkbox 候选项 {filter_key} 在点击成功后应升级为 applied",
        )
        _assert(
            selected_meta["verification_detail"]["page_filter_layout"] == "standard_search_filter_bar",
            f"标准搜索页 checkbox 候选项 {filter_key} 应识别为 standard_search_filter_bar",
        )
        _assert(
            selected_meta["verification_detail"]["entry_selector_strategy"] == "standard_search_filter_item",
            f"标准搜索页 checkbox 候选项 {filter_key} 应优先点击 search-filt-item 容器",
        )
        _assert(
            selected_meta["verification_detail"]["selector_resolution_mode"] == "selector_candidate",
            f"标准搜索页 checkbox 候选项 {filter_key} 命中稳定容器时应记录 selector_candidate 解析模式",
        )
        _assert(
            selected_meta["verification_detail"]["panel_term_selected_after_action"] is True,
            f"标准搜索页 checkbox 候选项 {filter_key} 动作成功后应记录真实选中态",
        )
        _assert(
            selected_meta["verification_detail"]["result_signature_changed"] is True,
            f"标准搜索页 checkbox 候选项 {filter_key} 动作成功后应记录结果页签名变化",
        )


def validate_visible_filter_toggle_runtime_apply_for_standard_select_item() -> None:
    next_snapshot = asyncio.run(
        _run_visible_filter_toggle_runtime_validation(
            filter_key="seven_day_return",
            html_content="""
            <html>
              <body>
                <div class="sn-select-wrap">
                  <div id="entry" class="select-item" role="checkbox" aria-checked="false">
                    <span>7天无理由</span>
                  </div>
                </div>
                <div id="results">
                  <div data-result-item data-id="sel-a">筛选前 A</div>
                  <div data-result-item data-id="sel-b">筛选前 B</div>
                </div>
                <script>
                  const entry = document.getElementById('entry');
                  const results = document.getElementById('results');
                  entry.addEventListener('click', () => {
                    const checked = entry.getAttribute('aria-checked') === 'true';
                    entry.setAttribute('aria-checked', checked ? 'false' : 'true');
                    entry.classList.toggle('selected', !checked);
                    results.innerHTML = checked
                      ? '<div data-result-item data-id="sel-a">筛选前 A</div><div data-result-item data-id="sel-b">筛选前 B</div>'
                      : '<div data-result-item data-id="sel-c">筛选后 C</div>';
                  });
                </script>
              </body>
            </html>
            """,
        )
    )
    selected_meta = next_snapshot["filter_status_map"]["seven_day_return"]
    _assert(
        selected_meta["status"] == "applied",
        "标准搜索页 select-item 结构在点击成功后应升级为 applied",
    )
    _assert(
        selected_meta["verification_detail"]["page_filter_layout"] == "standard_search_filter_bar",
        "select-item 结构应识别为 standard_search_filter_bar",
    )
    _assert(
        selected_meta["verification_detail"]["entry_selector_strategy"] == "standard_select_item",
        "标准搜索页 select-item 结构应优先命中 standard_select_item",
    )
    _assert(
        selected_meta["verification_detail"]["selector_resolution_mode"] == "selector_candidate",
        "标准搜索页 select-item 结构命中稳定容器时应记录 selector_candidate 解析模式",
    )
    _assert(
        selected_meta["verification_detail"]["panel_term_selected_after_action"] is True,
        "select-item 结构动作成功后应记录真实选中态",
    )
    _assert(
        selected_meta["verification_detail"]["result_signature_changed"] is True,
        "select-item 结构动作成功后应记录结果页签名变化",
    )


def validate_visible_filter_toggle_runtime_apply_for_standard_col_item() -> None:
    next_snapshot = asyncio.run(
        _run_visible_filter_toggle_runtime_validation(
            filter_key="real_factory_verified",
            html_content="""
            <html>
              <body>
                <div class="sn-row">
                  <div id="entry" class="sn-col-item" role="checkbox" aria-checked="false">
                    <span>真实工厂认证</span>
                  </div>
                </div>
                <div id="results">
                  <div data-result-item data-id="col-a">列项前 A</div>
                  <div data-result-item data-id="col-b">列项前 B</div>
                </div>
                <script>
                  const entry = document.getElementById('entry');
                  const results = document.getElementById('results');
                  entry.addEventListener('click', () => {
                    const checked = entry.getAttribute('aria-checked') === 'true';
                    entry.setAttribute('aria-checked', checked ? 'false' : 'true');
                    entry.classList.toggle('selected', !checked);
                    results.innerHTML = checked
                      ? '<div data-result-item data-id="col-a">列项前 A</div><div data-result-item data-id="col-b">列项前 B</div>'
                      : '<div data-result-item data-id="col-c">列项后 C</div>';
                  });
                </script>
              </body>
            </html>
            """,
        )
    )
    selected_meta = next_snapshot["filter_status_map"]["real_factory_verified"]
    _assert(
        selected_meta["status"] == "applied",
        "标准搜索页 sn-col-item 结构在点击成功后应升级为 applied",
    )
    _assert(
        selected_meta["verification_detail"]["page_filter_layout"] == "standard_search_filter_bar",
        "sn-col-item 结构应识别为 standard_search_filter_bar",
    )
    _assert(
        selected_meta["verification_detail"]["entry_selector_strategy"] == "standard_col_item",
        "标准搜索页 sn-col-item 结构应优先命中 standard_col_item",
    )
    _assert(
        selected_meta["verification_detail"]["selector_resolution_mode"] == "selector_candidate",
        "标准搜索页 sn-col-item 结构命中稳定容器时应记录 selector_candidate 解析模式",
    )
    _assert(
        selected_meta["verification_detail"]["panel_term_selected_after_action"] is True,
        "sn-col-item 结构动作成功后应记录真实选中态",
    )
    _assert(
        selected_meta["verification_detail"]["result_signature_changed"] is True,
        "sn-col-item 结构动作成功后应记录结果页签名变化",
    )


def validate_standard_layout_selector_priority_over_text_fallback() -> None:
    layout_name, strategy = asyncio.run(
        _run_filter_selector_probe(
            term="分销严选",
            html_content="""
            <html>
              <body>
                <div class="random-copy">分销严选</div>
                <div class="sn-row">
                  <div class="search-filt-item" role="checkbox" aria-checked="false">
                    <span>分销严选</span>
                  </div>
                </div>
              </body>
            </html>
            """,
        )
    )
    _assert(layout_name == "standard_search_filter_bar", "标准搜索页应优先识别为 standard_search_filter_bar")
    _assert(
        strategy == "standard_search_filter_item",
        "当稳定容器存在时，标准搜索页不应退化为 text_fallback",
    )


def validate_image_layout_selector_priority_over_text_fallback() -> None:
    layout_name, strategy = asyncio.run(
        _run_filter_selector_probe(
            term="分销严选",
            html_content="""
            <html>
              <body>
                <div class="random-copy">分销严选</div>
                <div class="filterBottomOptions--mock">
                  <div class="bottomFilterOption--mock" role="checkbox" aria-checked="false">
                    <span class="optionLabel--mock">分销严选</span>
                  </div>
                </div>
              </body>
            </html>
            """,
        )
    )
    _assert(layout_name == "image_result_filter_bar", "图搜结果页应优先识别为 image_result_filter_bar")
    _assert(
        strategy == "image_bottom_filter_option",
        "当图搜稳定容器存在时，不应退化为 text_fallback",
    )


def validate_special_panel_candidate_runtime_apply() -> None:
    next_snapshot = asyncio.run(_run_special_panel_candidate_runtime_validation(should_apply=True))
    encrypted_meta = next_snapshot["filter_status_map"]["encrypted_waybill"]
    _assert(
        encrypted_meta["status"] == "applied",
        "特殊入口候选项在面板打开并勾选成功后，应升级为 applied",
    )
    _assert(
        encrypted_meta["mapping_stage"] == "ui_automation",
        "特殊入口候选项在面板勾选成功后，应进入 ui_automation 阶段",
    )
    _assert(
        encrypted_meta["verification_detail"]["panel_trigger_text"] == "配置筛选",
        "特殊入口候选项应记录命中的面板触发器文案",
    )
    _assert(
        encrypted_meta["verification_detail"]["panel_trigger_candidates"] == ["配置筛选", "高级筛选", "更多筛选", "筛选"],
        "特殊入口候选项应记录标准布局下尝试过的触发词顺序",
    )
    _assert(
        encrypted_meta["verification_detail"]["panel_trigger_clicked"] is True,
        "特殊入口候选项应记录面板触发器点击成功",
    )
    _assert(
        encrypted_meta["verification_detail"]["panel_visible_via"] in {"term_visible", "[role='dialog']", ".ant-modal", ".ant-drawer", ".ant-popover", ".next-dialog", ".next-overlay-wrapper"},
        "特殊入口候选项应记录面板可见性的判定来源",
    )
    _assert(
        encrypted_meta["verification_detail"]["entry_click_succeeded"] is True,
        "特殊入口候选项应记录入口点击成功",
    )
    _assert(
        encrypted_meta["verification_detail"]["entry_selector_strategy"] == "text_fallback",
        "标准面板 fixture 应回退到文本入口策略，避免误判图搜布局",
    )
    _assert(
        encrypted_meta["verification_detail"]["selector_resolution_mode"] == "text_fallback",
        "特殊入口在标准面板文本命中场景下应记录 text_fallback 解析模式",
    )
    _assert(
        encrypted_meta["verification_detail"]["text_fallback_considered"] is True,
        "特殊入口在文本命中场景下应标记 text fallback 已参与",
    )
    _assert(
        encrypted_meta["verification_detail"]["panel_term_selected_after_action"] is True,
        "特殊入口候选项应记录动作后的选中态证据",
    )
    _assert(
        encrypted_meta["verification_detail"]["result_signature_changed"] is True,
        "特殊入口候选项在面板勾选成功后，应记录结果页签名变化",
    )
    _assert(
        encrypted_meta["verification_detail"]["special_panel_conclusion"] == "panel_action_result_shift_observed",
        "特殊入口候选项在面板动作成功且结果变化后，应沉淀统一入口结论字段",
    )
    _assert(
        next_snapshot["verification_details"]["encrypted_waybill"]["special_panel_conclusion"]
        == "panel_action_result_shift_observed",
        "特殊入口候选项在结果变化成功态下，也应把统一入口结论投影到顶层 verification_details",
    )
    _assert(
        next_snapshot["query_verification_details"]["encrypted_waybill"]["special_panel_conclusion"]
        == "panel_action_result_shift_observed",
        "特殊入口候选项在结果变化成功态下，也应把统一入口结论投影到 query_verification_details",
    )


def validate_special_panel_candidate_runtime_apply_on_image_result_layout() -> None:
    next_snapshot = asyncio.run(
        _run_special_panel_candidate_runtime_validation(
            should_apply=True,
            layout="image_result",
        )
    )
    encrypted_meta = next_snapshot["filter_status_map"]["encrypted_waybill"]
    _assert(
        encrypted_meta["status"] == "applied",
        "图搜结果页布局下，特殊入口候选项在点击 configLabel 容器后也应升级为 applied",
    )
    _assert(
        encrypted_meta["verification_detail"]["page_filter_layout"] == "image_result_filter_bar",
        "图搜结果页布局应被识别为 image_result_filter_bar",
    )
    _assert(
        encrypted_meta["verification_detail"]["entry_selector_strategy"] in {"image_config_filter", "image_config_label"},
        "图搜结果页布局应优先命中 configFilter/configLabel 容器，而不是文本兜底",
    )
    _assert(
        encrypted_meta["verification_detail"].get("panel_trigger_clicked") in {None, False},
        "图搜结果页布局在入口已可见时，不应伪造高级筛选触发器点击",
    )
    _assert(
        encrypted_meta["verification_detail"].get("panel_trigger_candidates") in (None, []),
        "图搜结果页直接入口场景不应伪造面板触发词探测链路",
    )
    _assert(
        encrypted_meta["verification_detail"]["result_signature_changed"] is True,
        "图搜结果页直接入口场景下，也应记录结果页签名变化",
    )
    _assert(
        encrypted_meta["verification_detail"]["special_panel_conclusion"] == "panel_action_result_shift_observed",
        "图搜结果页直接入口成功场景也应沉淀统一入口结论字段",
    )
    _assert(
        next_snapshot["verification_details"]["encrypted_waybill"]["special_panel_conclusion"]
        == "panel_action_result_shift_observed",
        "图搜结果页直接入口成功场景，也应把统一入口结论投影到顶层 verification_details",
    )
    _assert(
        next_snapshot["query_verification_details"]["encrypted_waybill"]["special_panel_conclusion"]
        == "panel_action_result_shift_observed",
        "图搜结果页直接入口成功场景，也应把统一入口结论投影到 query_verification_details",
    )


def validate_special_panel_candidate_runtime_apply_from_active_condition() -> None:
    next_snapshot = asyncio.run(
        _run_special_panel_candidate_runtime_validation(
            should_apply=True,
            layout="image_active_condition",
        )
    )
    encrypted_meta = next_snapshot["filter_status_map"]["encrypted_waybill"]
    detail = encrypted_meta["verification_detail"]
    _assert(
        encrypted_meta["status"] == "applied",
        "图搜页已选条件条出现“密文面单：xxx”时，应识别为密文面单已应用",
    )
    _assert(
        detail["panel_term_selected_via_before_action"] == "active_condition_text",
        "已选条件条证据应记录在 selected_via_before_action",
    )
    _assert(
        detail["panel_term_selected_via_after_action"] == "active_condition_text",
        "已选条件条证据应记录在 selected_via_after_action",
    )
    _assert(
        detail.get("entry_click_attempted") in (None, False),
        "已选条件条已经证明筛选存在时，不应再点击普通筛选入口导致反选",
    )
    _assert(
        encrypted_meta["special_panel_conclusion"] == "panel_active_condition_observed",
        "已选条件条应沉淀为 panel_active_condition_observed 结论",
    )
    report = build_runtime_audit_report({"stage": "special_panel_candidate_checked", "snapshot": next_snapshot})
    by_key = {item["filter_key"]: item for item in report["filters"]}
    _assert(
        by_key["encrypted_waybill"]["can_close_real_site_gap"] is True,
        "审计分类器应接受密文面单已选条件条作为强证据",
    )


def validate_special_panel_candidate_runtime_open_failed() -> None:
    next_snapshot = asyncio.run(_run_special_panel_candidate_runtime_validation(should_apply=False))
    encrypted_meta = next_snapshot["filter_status_map"]["encrypted_waybill"]
    _assert(
        encrypted_meta["status"] == "unapplied",
        "特殊入口候选项在无法完成勾选时，仍应保持 unapplied",
    )
    _assert(
        encrypted_meta["reason"] == "special_panel_open_failed",
        "特殊入口候选项在面板动作失败时，应给出 special_panel_open_failed 原因",
    )
    _assert(
        encrypted_meta["verification_detail"]["panel_trigger_clicked"] is True,
        "特殊入口候选项在打开失败时，仍应记录已尝试点击面板触发器",
    )
    _assert(
        encrypted_meta["verification_detail"]["panel_trigger_candidates"] == ["配置筛选", "高级筛选", "更多筛选", "筛选"],
        "特殊入口候选项在打开失败路径下，也应记录触发词探测顺序",
    )
    _assert(
        encrypted_meta["verification_detail"]["panel_term_selected_after_action"] is False,
        "特殊入口候选项在打开失败时，不应伪造选中态",
    )
    _assert(
        encrypted_meta["verification_detail"]["special_panel_conclusion"] == "panel_open_or_toggle_failed",
        "特殊入口候选项在面板动作失败时，应沉淀统一入口结论字段",
    )
    _assert(
        next_snapshot["verification_details"]["encrypted_waybill"]["special_panel_conclusion"]
        == "panel_open_or_toggle_failed",
        "特殊入口候选项在面板动作失败时，也应把统一入口结论投影到顶层 verification_details",
    )
    _assert(
        next_snapshot["query_verification_details"]["encrypted_waybill"]["special_panel_conclusion"]
        == "panel_open_or_toggle_failed",
        "特殊入口候选项在面板动作失败时，也应把统一入口结论投影到 query_verification_details",
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


def validate_detail_channel_sorting_contract() -> None:
    listing_price = 29.9
    source_rows = [
        {
            "db_id": 1001,
            "title": "A-1",
            "min_price": 12.5,
            "estimated_profit": 4.2,
            "page_original_index": 1,
            "source_channel_id": "ali1688",
            "source_channel_label": "1688 货源渠道",
        },
        {
            "db_id": 1002,
            "title": "A-2",
            "min_price": 9.8,
            "estimated_profit": 8.5,
            "page_original_index": 3,
            "source_channel_id": "ali1688",
            "source_channel_label": "1688 货源渠道",
        },
        {
            "db_id": 2001,
            "title": "B-1",
            "min_price": 11.3,
            "estimated_profit": 6.1,
            "page_original_index": 2,
            "source_channel_id": "yiwu-market",
            "source_channel_label": "义乌渠道",
        },
        {
            "db_id": 3001,
            "title": "C-1",
            "min_price": 13.2,
            "estimated_profit": 2.0,
            "page_original_index": 4,
            "source_channel_id": "guangzhou-market",
            "source_channel_label": "广州渠道",
        },
    ]
    channel_groups_map = {
        "ali1688": {
            "channel_id": "ali1688",
            "channel_type": "ali1688",
            "channel_label": "1688 货源渠道",
            "sources": [source_rows[0], source_rows[1]],
        },
        "yiwu-market": {
            "channel_id": "yiwu-market",
            "channel_type": "ali1688",
            "channel_label": "义乌渠道",
            "sources": [source_rows[2]],
        },
        "guangzhou-market": {
            "channel_id": "guangzhou-market",
            "channel_type": "ali1688",
            "channel_label": "广州渠道",
            "sources": [source_rows[3]],
        },
    }
    used_channels_map = {
        "guangzhou-market": {
            "channel_id": "guangzhou-market",
            "channel_type": "ali1688",
            "channel_label": "广州渠道",
        },
        "ali1688": {
            "channel_id": "ali1688",
            "channel_type": "ali1688",
            "channel_label": "1688 货源渠道",
        },
        "yiwu-market": {
            "channel_id": "yiwu-market",
            "channel_type": "ali1688",
            "channel_label": "义乌渠道",
        },
    }

    sorted_sources, sorted_groups, sorted_used_channels = _sort_detail_sources_and_groups(
        source_rows=source_rows,
        channel_groups_map=channel_groups_map,
        used_channels_map=used_channels_map,
        listing_price=listing_price,
    )

    _assert(
        [item["db_id"] for item in sorted_sources] == [1002, 2001, 1001, 3001],
        "详情页全量 sources 应按预估纯利倒序排序",
    )
    _assert(
        [group["channel_id"] for group in sorted_groups] == ["ali1688", "yiwu-market", "guangzhou-market"],
        "channel_groups 应按各渠道最高预估纯利倒序排序",
    )
    _assert(
        [channel["channel_id"] for channel in sorted_used_channels] == ["ali1688", "yiwu-market", "guangzhou-market"],
        "used_channels 顺序应与 channel_groups 排序保持一致",
    )
    _assert(
        [source["db_id"] for source in sorted_groups[0]["sources"]] == [1002, 1001],
        "单个渠道组内的 sources 也应按预估纯利倒序排序",
    )
    _assert(
        float(sorted_groups[0]["best_estimated_profit"]) == 8.5
        and float(sorted_groups[1]["best_estimated_profit"]) == 6.1
        and float(sorted_groups[2]["best_estimated_profit"]) == 2.0,
        "channel_groups 应补齐每个渠道的 best_estimated_profit 摘要",
    )


def validate_detail_sort_strategy_contract() -> None:
    source_sort_strategy = _build_detail_source_sort_strategy()
    _assert(
        source_sort_strategy == {
            "field": "estimated_profit",
            "order": "desc",
            "label": "预估纯利倒序",
            "description": "当前结果按预估纯利从高到低固定排序，渠道筛选仅影响当前展示范围。",
        },
        "详情页 source_sort_strategy 应保持固定排序契约",
    )

    channel_group_sort_strategy = _build_detail_channel_group_sort_strategy()
    _assert(
        channel_group_sort_strategy == {
            "field": "best_estimated_profit",
            "order": "desc",
            "label": "渠道最高预估纯利倒序",
            "description": "当前渠道分组按各渠道最高预估纯利从高到低固定排序。",
        },
        "详情页 channel_group_sort_strategy 应保持固定排序契约",
    )


def validate_detail_sort_filter_ui_semantics_contract() -> None:
    app_jsx = (BASE_DIR / "web" / "app.jsx").read_text(encoding="utf-8")

    _assert(
        "货源排序" not in app_jsx,
        "详情页不应再出现“货源排序”交互文案，避免把固定排序误解成可切换筛选控件",
    )
    _assert(
        "固定排序" in app_jsx and "sourceSortStrategyLabel" in app_jsx,
        "详情页应保留固定排序说明，并消费接口返回的 source_sort_strategy label",
    )
    _assert(
        "货源渠道" in app_jsx
        and 'value={sourceChannelFilter}' in app_jsx
        and "setSourceChannelFilter" in app_jsx,
        "详情页应保留独立的货源渠道筛选控件，渠道筛选只影响展示范围",
    )
    _assert(
        "sourceSortStrategyDescription" in app_jsx
        and "渠道筛选仅影响当前展示范围" in app_jsx,
        "详情页应向用户解释固定排序与渠道筛选的语义边界",
    )


def validate_detail_filter_conclusion_label_contract() -> None:
    app_jsx = (BASE_DIR / "web" / "app.jsx").read_text(encoding="utf-8")

    semantic_conclusions = [
        "dependency_pair_incomplete",
        "dependency_pair_ready_pending_runtime",
        "independent_entry_observed_pending_result_validation",
        "independent_entry_no_result_shift",
        "independent_entry_result_shift_observed",
    ]
    special_panel_conclusions = [
        "entry_signal_detected_pending_panel_mapping",
        "panel_open_or_toggle_failed",
        "panel_action_applied_no_result_shift",
        "panel_action_result_shift_observed",
    ]

    for conclusion in semantic_conclusions:
        _assert(
            conclusion in app_jsx,
            f"前端应解释 semantic_conclusion={conclusion}，避免组合语义结论只展示原始状态码",
        )
    for conclusion in special_panel_conclusions:
        _assert(
            conclusion in app_jsx,
            f"前端应解释 special_panel_conclusion={conclusion}，避免特殊入口结论只展示原始状态码",
        )
    _assert(
        "semanticConclusionLabelMap" in app_jsx
        and "specialPanelConclusionLabelMap" in app_jsx
        and "detail.semantic_conclusion" in app_jsx
        and "detail.special_panel_conclusion" in app_jsx,
        "详情页应优先消费统一结论字段，再补充原始动作证据",
    )


def validate_detail_filter_runtime_diagnostics_label_contract() -> None:
    app_jsx = (BASE_DIR / "web" / "app.jsx").read_text(encoding="utf-8")

    required_runtime_fields = [
        "selector_candidates_tried",
        "selector_resolution_mode",
        "text_fallback_considered",
        "panel_trigger_candidates",
        "panel_visible_via",
        "entry_selector_strategy",
        "page_filter_layout",
        "result_signature_changed",
        "result_url_changed",
        "panel_term_selected_via_after_action",
    ]
    required_user_labels = [
        "候选定位链路",
        "定位方式",
        "已评估文本兜底",
        "未退化到文本兜底",
        "触发词顺序",
        "面板可见来源",
        "点击入口",
        "页面布局",
        "已观察到结果签名变化",
        "已观察到结果页 URL 变化",
        "选中来源：结果页已选条件条",
        "语义结论：依赖组合已通过真实强证据确认",
        "入口结论：结果页已存在该筛选的已选条件",
        "阶段：依赖组合已通过真实强证据确认",
    ]

    for field in required_runtime_fields:
        _assert(
            field in app_jsx,
            f"详情页应消费 runtime 诊断字段 {field}，避免 DOM 筛选动作证据在前端解释层丢失",
        )
    for label in required_user_labels:
        _assert(
            label in app_jsx,
            f"详情页应将 runtime 诊断信息翻译为用户可读文案：{label}",
        )
    _assert(
        "formatQueryVerificationDetail" in app_jsx
        and "formatSourceFilterSummaryChipTitle" in app_jsx,
        "渠道组与单条货源摘要应复用同一套 runtime 诊断解释函数",
    )


def validate_detail_channel_filter_summary_contract() -> None:
    legacy_summary = _summarize_channel_filter_snapshot(
        {},
        channel_type="ali1688",
        has_recorded_snapshot=False,
    )
    _assert(
        legacy_summary["legacy_missing_snapshot"] is True,
        "历史无快照资产应显式标记为 legacy_missing_snapshot",
    )
    _assert(
        legacy_summary["configured"] == [],
        "历史无快照资产不应伪造已启用筛选项列表",
    )
    _assert(
        legacy_summary["configured_pending"] == []
        and legacy_summary["query_injected"] == []
        and legacy_summary["applied"] == []
        and legacy_summary["unapplied"] == [],
        "历史无快照资产不应被误解释成任何筛选状态集合",
    )

    configured_pending_summary = _summarize_channel_filter_snapshot(
        {
            "channel_id": "ali1688",
            "channel_type": "ali1688",
            "configured_filters": {
                "single_piece_free_shipping": True,
                "encrypted_waybill": True,
            },
            "configured_enabled_filter_keys": [
                "single_piece_free_shipping",
                "encrypted_waybill",
            ],
            "filter_status_map": {
                "single_piece_free_shipping": {
                    "status": "unapplied",
                    "reason": "semantic_combo_not_confirmed",
                    "mapping_stage": "snapshot_only",
                },
                "encrypted_waybill": {
                    "status": "unapplied",
                    "reason": "special_panel_entry_detected_unmapped",
                    "mapping_stage": "snapshot_only",
                },
            },
            "mapping_stage": "snapshot_only",
        },
        channel_type="ali1688",
        has_recorded_snapshot=True,
    )
    _assert(
        configured_pending_summary["legacy_missing_snapshot"] is False,
        "已记录快照的数据不应再被降级为历史缺失快照",
    )
    _assert(
        configured_pending_summary["configured"] == ["single_piece_free_shipping", "encrypted_waybill"],
        "详情摘要应直接保留当前渠道已启用的筛选项全集",
    )
    _assert(
        configured_pending_summary["configured_pending"] == ["single_piece_free_shipping", "encrypted_waybill"],
        "仅配置未验证的筛选项应统一落入 configured_pending",
    )
    _assert(
        configured_pending_summary["filter_status_map"]["single_piece_free_shipping"]["reason"]
        == "semantic_combo_not_confirmed",
        "详情摘要应直接透传 filter_status_map，避免前端再回头解释 snapshot",
    )

    runtime_summary = _summarize_channel_filter_snapshot(
        {
            "channel_id": "ali1688",
            "channel_type": "ali1688",
            "configured_filters": {
                "free_shipping": True,
                "rapid_invoice": True,
                "official_logistics": True,
            },
            "configured_enabled_filter_keys": [
                "free_shipping",
                "rapid_invoice",
                "official_logistics",
            ],
            "filter_status_map": {
                "free_shipping": {
                    "status": "applied",
                    "reason": "",
                    "mapping_stage": "query_mapped",
                    "verification_detail": {
                        "probe_mode": "url_query",
                        "matched_params": {
                            "freeShipping": "1",
                        },
                    },
                },
                "rapid_invoice": {
                    "status": "query_injected_pending_verification",
                    "reason": "query_filter_injected_pending_verification",
                    "mapping_stage": "query_candidate",
                },
                "official_logistics": {
                    "status": "unapplied",
                    "reason": "query_filter_not_applied_in_runtime",
                    "mapping_stage": "query_candidate",
                },
            },
            "mapping_stage": "mixed",
            "runtime_audit_stage": "summary_written",
            "runtime_audit_source": "_channel_filter_runtime_snapshot.json",
        },
        channel_type="ali1688",
        has_recorded_snapshot=True,
    )
    _assert(
        runtime_summary["configured"] == ["rapid_invoice", "free_shipping", "official_logistics"],
        "运行时摘要应保留当前渠道配置过的筛选项全集",
    )
    _assert(runtime_summary["applied"] == ["free_shipping"], "已命中的筛选项应进入 applied 摘要")
    _assert(
        runtime_summary["query_injected"] == ["rapid_invoice"],
        "已注入待验证的筛选项应进入 query_injected 摘要",
    )
    _assert(
        runtime_summary["unapplied"] == ["official_logistics"],
        "真实失败的筛选项应进入 unapplied 摘要",
    )
    _assert(
        runtime_summary["filter_status_map"]["rapid_invoice"]["status"] == "query_injected_pending_verification",
        "运行时摘要应直接透传 filter_status_map，供详情解释层优先消费接口契约",
    )
    _assert(
        runtime_summary["query_verification_details"]["free_shipping"]["matched_params"]["freeShipping"] == "1",
        "运行时摘要应直接透传 query_verification_details，避免前端再从 snapshot 回推命中参数",
    )
    _assert(runtime_summary["has_runtime_signal"] is True, "存在真实 runtime 状态时应标记 has_runtime_signal")
    _assert(
        runtime_summary["runtime_audit_stage"] == "summary_written",
        "运行时摘要应透出 runtime_audit_stage，供详情页说明证据阶段",
    )
    _assert(
        runtime_summary["runtime_audit_source"] == "_channel_filter_runtime_snapshot.json",
        "运行时摘要应透出 runtime_audit_source，供详情页说明证据来源",
    )


def validate_task_channel_summary_contract() -> None:
    task_channel_map = {
        "task-1": [
            {
                "channel_id": "ali1688",
                "channel_type": "ali1688",
                "channel_label": "1688 货源渠道",
                "source_count": 2,
            },
            {
                "channel_id": "yiwu-market",
                "channel_type": "ali1688",
                "channel_label": "义乌渠道",
                "source_count": 1,
            },
        ]
    }
    snapshot_rows = [
        {
            "task_id": "task-1",
            "channel_id": "ali1688",
            "channel_type": "ali1688",
            "channel_label": "1688 货源渠道",
            "source_filter_snapshot_json": json.dumps(
                {
                    "channel_id": "ali1688",
                    "channel_type": "ali1688",
                    "configured_enabled_filter_keys": ["free_shipping", "rapid_invoice"],
                    "filter_status_map": {
                        "free_shipping": {
                            "status": "applied",
                            "reason": "",
                            "mapping_stage": "query_mapped",
                        },
                        "rapid_invoice": {
                            "status": "query_injected_pending_verification",
                            "reason": "query_filter_injected_pending_verification",
                            "mapping_stage": "query_candidate",
                        },
                    },
                    "mapping_stage": "mixed",
                    "runtime_audit_stage": "summary_written",
                    "runtime_audit_source": "_channel_filter_runtime_snapshot.json",
                },
                ensure_ascii=False,
            ),
        },
        {
            "task_id": "task-1",
            "channel_id": "yiwu-market",
            "channel_type": "ali1688",
            "channel_label": "义乌渠道",
            "source_filter_snapshot_json": "",
        },
    ]

    summary_map = _build_task_channel_summary_map(
        task_channel_map=task_channel_map,
        snapshot_rows=snapshot_rows,
    )
    summaries = summary_map["task-1"]
    _assert(
        [item["channel_id"] for item in summaries] == ["ali1688", "yiwu-market"],
        "任务级 channel_summaries 应保留 used_channels 既有顺序",
    )
    _assert(
        summaries[0]["filter_summary"]["configured"] == ["rapid_invoice", "free_shipping"],
        "任务级 channel_summaries 应保留当前渠道已启用的筛选项全集",
    )
    _assert(
        summaries[0]["filter_summary"]["applied"] == ["free_shipping"],
        "任务级 channel_summaries 应汇总真实已生效筛选项",
    )
    _assert(
        summaries[0]["filter_summary"]["query_injected"] == ["rapid_invoice"],
        "任务级 channel_summaries 应汇总已注入待验证筛选项",
    )
    _assert(
        summaries[0]["filter_summary"]["filter_status_map"]["free_shipping"]["status"] == "applied",
        "任务级 channel_summaries 也应透传 filter_status_map，保持与详情摘要口径一致",
    )
    _assert(
        summaries[0]["filter_summary"]["runtime_audit_stage"] == "summary_written",
        "任务级 channel_summaries 应透出 runtime_audit_stage，保持列表页与详情页证据阶段一致",
    )
    _assert(
        summaries[0]["filter_summary"]["runtime_audit_source"] == "_channel_filter_runtime_snapshot.json",
        "任务级 channel_summaries 应透出 runtime_audit_source，保持列表页与详情页证据来源一致",
    )
    _assert(
        summaries[0]["has_recorded_filter_snapshot"] is True,
        "已记录快照的任务级渠道摘要应标记 has_recorded_filter_snapshot",
    )
    _assert(
        summaries[1]["filter_summary"]["legacy_missing_snapshot"] is True,
        "历史无快照的任务级渠道摘要应保持 legacy_missing_snapshot 降级标记",
    )
    _assert(
        summaries[1]["filter_summary"]["configured"] == [],
        "历史无快照的任务级渠道摘要不应伪造已启用筛选项全集",
    )
    _assert(
        summaries[1]["has_recorded_filter_snapshot"] is False,
        "历史无快照的任务级渠道摘要不应误标记为已记录快照",
    )


def validate_detail_source_filter_summary_contract() -> None:
    source_summary = _summarize_channel_filter_snapshot(
        {
            "channel_id": "ali1688",
            "channel_type": "ali1688",
            "configured_enabled_filter_keys": [
                "free_shipping",
                "rapid_invoice",
                "official_logistics",
            ],
            "filter_status_map": {
                "free_shipping": {
                    "status": "applied",
                    "reason": "",
                    "mapping_stage": "query_mapped",
                },
                "rapid_invoice": {
                    "status": "query_injected_pending_verification",
                    "reason": "query_filter_injected_pending_verification",
                    "mapping_stage": "query_candidate",
                },
                "official_logistics": {
                    "status": "unapplied",
                    "reason": "query_filter_not_applied_in_runtime",
                    "mapping_stage": "query_candidate",
                },
            },
            "mapping_stage": "mixed",
            "runtime_audit_stage": "visible_filter_toggle_checked",
            "runtime_audit_source": "_channel_filter_runtime_snapshot.json",
        },
        channel_type="ali1688",
        has_recorded_snapshot=True,
    )
    _assert(
        source_summary["configured"] == ["free_shipping", "rapid_invoice", "official_logistics"],
        "单条货源的 source_filter_summary 也应保留当前渠道已启用的筛选项全集",
    )
    _assert(
        source_summary["applied"] == ["free_shipping"]
        and source_summary["query_injected"] == ["rapid_invoice"]
        and source_summary["unapplied"] == ["official_logistics"],
        "单条货源的 source_filter_summary 应稳定区分 applied / query_injected / unapplied",
    )
    _assert(
        source_summary["configured_filter_count"] == 3,
        "单条货源的 source_filter_summary 应补齐 configured_filter_count，供前端直接消费",
    )
    _assert(
        source_summary["filter_status_map"]["rapid_invoice"]["status"] == "query_injected_pending_verification",
        "单条货源的 source_filter_summary 也应透传 filter_status_map，避免 source 卡片重新回推状态",
    )
    _assert(
        source_summary["query_verification_details"]["free_shipping"] == {},
        "单条货源的 source_filter_summary 应稳定保留 query_verification_details 字段结构",
    )
    _assert(
        source_summary["runtime_audit_stage"] == "visible_filter_toggle_checked",
        "单条货源的 source_filter_summary 应透出运行时审计阶段",
    )

    semantic_source_summary = _summarize_channel_filter_snapshot(
        {
            "channel_id": "ali1688",
            "channel_type": "ali1688",
            "configured_enabled_filter_keys": ["single_piece_free_shipping"],
            "filter_status_map": {
                "single_piece_free_shipping": {
                    "status": "unapplied",
                    "reason": "snapshot_only_until_semantics_confirmed",
                    "mapping_stage": "mixed",
                    "verification_detail": {
                        "probe_mode": "dom_toggle_action",
                        "verification_mode": "dom_toggle_action",
                        "semantic_conclusion": "independent_entry_no_result_shift",
                        "result_signature_changed": False,
                    },
                },
            },
            "query_verification_details": {
                "single_piece_free_shipping": {
                    "probe_mode": "dom_toggle_action",
                    "verification_mode": "dom_toggle_action",
                    "semantic_conclusion": "independent_entry_no_result_shift",
                    "result_signature_changed": False,
                },
            },
            "mapping_stage": "mixed",
        },
        channel_type="ali1688",
        has_recorded_snapshot=True,
    )
    _assert(
        semantic_source_summary["query_verification_details"]["single_piece_free_shipping"]["semantic_conclusion"]
        == "independent_entry_no_result_shift",
        "单条货源的 source_filter_summary 也应保留组合语义候选项的统一语义结论",
    )
    _assert(
        semantic_source_summary["query_verification_details"]["single_piece_free_shipping"]["probe_mode"]
        == "dom_toggle_action",
        "单条货源的 source_filter_summary 应保留 DOM 勾选动作的 probe_mode，便于前端解释链消费",
    )
    _assert(
        semantic_source_summary["query_verification_details"]["single_piece_free_shipping"]["verification_mode"]
        == "dom_toggle_action",
        "单条货源的 source_filter_summary 应保留 DOM 勾选动作的 verification_mode，避免 source 卡片退回原始状态码",
    )

    checkbox_diagnostic_summary = _summarize_channel_filter_snapshot(
        {
            "channel_id": "ali1688",
            "channel_type": "ali1688",
            "configured_enabled_filter_keys": ["selected_distributors"],
            "filter_status_map": {
                "selected_distributors": {
                    "status": "applied",
                    "reason": "",
                    "mapping_stage": "ui_automation",
                    "verification_detail": {
                        "probe_mode": "dom_toggle_action",
                        "verification_mode": "dom_toggle_action",
                        "page_filter_layout": "standard_search_filter_bar",
                        "entry_selector_strategy": "standard_search_filter_item",
                        "selector_resolution_mode": "selector_candidate",
                        "text_fallback_considered": False,
                        "selector_candidates_tried": [
                            {"strategy": "standard_search_filter_item", "matched": True},
                        ],
                        "result_signature_changed": True,
                    },
                },
            },
            "mapping_stage": "mixed",
        },
        channel_type="ali1688",
        has_recorded_snapshot=True,
    )
    checkbox_detail = checkbox_diagnostic_summary["query_verification_details"]["selected_distributors"]
    _assert(
        checkbox_detail["selector_resolution_mode"] == "selector_candidate",
        "单条货源摘要应保留 DOM checkbox 的 selector_resolution_mode 诊断字段",
    )
    _assert(
        checkbox_detail["text_fallback_considered"] is False,
        "单条货源摘要应保留 DOM checkbox 是否退化到文本兜底的诊断字段",
    )
    _assert(
        checkbox_detail["selector_candidates_tried"][0]["strategy"] == "standard_search_filter_item",
        "单条货源摘要应保留 DOM checkbox 的 selector 候选链路",
    )
    _assert(
        checkbox_detail["result_signature_changed"] is True,
        "单条货源摘要应保留 DOM checkbox 动作后的结果签名变化证据",
    )

    special_panel_source_summary = _summarize_channel_filter_snapshot(
        {
            "channel_id": "ali1688",
            "channel_type": "ali1688",
            "configured_enabled_filter_keys": ["encrypted_waybill"],
            "filter_status_map": {
                "encrypted_waybill": {
                    "status": "unapplied",
                    "reason": "ui_apply_not_observed",
                    "mapping_stage": "mixed",
                    "verification_detail": {
                        "probe_mode": "dom_panel_action",
                        "special_panel_conclusion": "panel_action_applied_no_result_shift",
                        "result_signature_changed": False,
                    },
                },
            },
            "query_verification_details": {
                "encrypted_waybill": {
                    "probe_mode": "dom_panel_action",
                    "special_panel_conclusion": "panel_action_applied_no_result_shift",
                    "result_signature_changed": False,
                },
            },
            "mapping_stage": "mixed",
        },
        channel_type="ali1688",
        has_recorded_snapshot=True,
    )
    _assert(
        special_panel_source_summary["query_verification_details"]["encrypted_waybill"]["special_panel_conclusion"]
        == "panel_action_applied_no_result_shift",
        "单条货源的 source_filter_summary 也应保留特殊入口候选项的统一入口结论",
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


def validate_runtime_filter_snapshot_audit_file_contract() -> None:
    runtime_snapshot = settings.normalize_channel_search_filter_snapshot(
        {
            "channel_id": "ali1688",
            "channel_type": "ali1688",
            "configured_filters": {
                "rapid_invoice": True,
                "single_piece_drop_shipping": True,
            },
            "configured_enabled_filter_keys": [
                "rapid_invoice",
                "single_piece_drop_shipping",
            ],
            "query_injected_filter_keys": ["rapid_invoice"],
            "applied_filter_keys": [],
            "unapplied_filter_keys": ["single_piece_drop_shipping"],
            "query_verification_details": {
                "rapid_invoice": {
                    "verification_mode": "post_navigation_url",
                    "matched_values": ["1013"],
                }
            },
            "filter_status_map": {
                "rapid_invoice": {
                    "configured": True,
                    "status": "query_injected_pending_verification",
                    "verification_detail": {
                        "verification_mode": "post_navigation_url",
                        "matched_values": ["1013"],
                    },
                },
                "single_piece_drop_shipping": {
                    "configured": True,
                    "status": "unapplied",
                    "reason": "runtime_mapping_not_implemented_yet",
                },
            },
            "mapping_stage": "mixed",
        }
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)
        normalized = _write_runtime_filter_snapshot_audit(
            out_dir,
            runtime_snapshot,
            stage="query_filter_post_navigation_verified",
            extra={"result_url": "https://s.1688.com/selloffer/offer_search.htm?complexTags=1013"},
        )
        audit_path = out_dir / "_channel_filter_runtime_snapshot.json"
        event_path = out_dir / "_channel_filter_runtime_events.jsonl"
        _assert(audit_path.exists(), "运行时筛选快照审计文件应稳定落盘")
        _assert(event_path.exists(), "运行时筛选快照事件流应稳定追加")

        payload = json.loads(audit_path.read_text(encoding="utf-8"))
        _assert(payload["stage"] == "query_filter_post_navigation_verified", "审计文件应记录当前阶段")
        _assert(payload["audit_generated_at_epoch"] > 0, "审计文件应记录生成时间，避免后续无法判断运行批次")
        _assert(
            payload["audit_run_id"].endswith("-ali1688-query_filter_post_navigation_verified"),
            "审计文件应记录可追踪运行 ID，便于把审计产物关联到具体阶段和渠道",
        )
        _assert(payload["channel_id"] == "ali1688", "审计文件顶层应保留渠道 ID")
        _assert(payload["configured_enabled_filter_keys"] == ["rapid_invoice", "single_piece_drop_shipping"], "审计文件应保留已配置启用项")
        _assert(payload["query_injected_filter_keys"] == ["rapid_invoice"], "审计文件应保留 query 注入项")
        _assert(payload["applied_filter_keys"] == [], "审计文件应保留已生效项")
        _assert(payload["unapplied_filter_keys"] == ["single_piece_drop_shipping"], "审计文件应保留未生效项")
        _assert(payload["snapshot"] == normalized, "审计文件应同时保留完整归一化快照")
        _assert(
            payload["snapshot"]["runtime_audit_stage"] == "query_filter_post_navigation_verified",
            "审计文件的完整快照应保留 runtime_audit_stage，供入库和 API 摘要解释",
        )
        _assert(
            payload["snapshot"]["runtime_audit_source"] == "_channel_filter_runtime_snapshot.json",
            "审计文件的完整快照应保留 runtime_audit_source，供前端说明证据来源",
        )
        _assert(
            payload["query_verification_details"]["rapid_invoice"]["matched_values"] == ["1013"],
            "审计文件应保留 query 验证详情",
        )

        events = [
            json.loads(line)
            for line in event_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        _assert(len(events) == 1, "首次写入应追加一条事件")
        _assert(events[0]["stage"] == payload["stage"], "事件流阶段应与最新审计 payload 一致")
        _assert(events[0]["audit_run_id"] == payload["audit_run_id"], "事件流应保留同一个审计运行 ID")
        audit_report = build_runtime_audit_report(payload)
        _assert(
            audit_report["audit_run_id"] == payload["audit_run_id"],
            "单文件审计报告应透出审计运行 ID，供人工复盘确认真实运行批次",
        )


def validate_full_pipeline_runtime_filter_audit_precedence() -> None:
    fallback_snapshot = settings.normalize_channel_search_filter_snapshot(
        {
            "channel_id": "ali1688",
            "channel_type": "ali1688",
            "configured_filters": {"rapid_invoice": True},
            "configured_enabled_filter_keys": ["rapid_invoice"],
            "filter_status_map": {
                "rapid_invoice": {
                    "configured": True,
                    "status": "unapplied",
                    "reason": "runtime_mapping_not_implemented_yet",
                }
            },
            "mapping_stage": "snapshot_only",
        }
    )
    runtime_snapshot = settings.normalize_channel_search_filter_snapshot(
        {
            "channel_id": "ali1688",
            "channel_type": "ali1688",
            "configured_filters": {"rapid_invoice": True},
            "configured_enabled_filter_keys": ["rapid_invoice"],
            "applied_filter_keys": ["rapid_invoice"],
            "filter_status_map": {
                "rapid_invoice": {
                    "configured": True,
                    "status": "applied",
                    "reason": "",
                    "verification_detail": {
                        "verification_mode": "post_navigation_url",
                        "matched_values": ["1013"],
                    },
                }
            },
            "mapping_stage": "query_mapped",
        }
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)
        without_audit = load_runtime_filter_audit_snapshot(out_dir, fallback_snapshot)
        _assert(
            without_audit["mapping_stage"] == "snapshot_only",
            "审计文件不存在时，上游管线应保留传入的初始快照",
        )

        summary_snapshot = settings.normalize_channel_search_filter_snapshot(
            {
                "channel_id": "ali1688",
                "channel_type": "ali1688",
                "configured_filters": {"rapid_invoice": True},
                "configured_enabled_filter_keys": ["rapid_invoice"],
                "query_injected_filter_keys": ["rapid_invoice"],
                "filter_status_map": {
                    "rapid_invoice": {
                        "configured": True,
                        "status": "query_injected_pending_verification",
                        "reason": "query_filter_injected_pending_verification",
                    },
                },
                "mapping_stage": "mixed",
            }
        )
        selected_without_audit = select_source_filter_snapshot_for_db(
            audit_exists=False,
            audit_snapshot=without_audit,
            summary_snapshot=summary_snapshot,
            fallback_snapshot=fallback_snapshot,
        )
        _assert(
            selected_without_audit["mapping_stage"] == "mixed",
            "审计文件不存在时，入库应优先使用 summary.json 内单条货源的运行快照，而不是初始配置快照",
        )
        _assert(
            selected_without_audit["query_injected_filter_keys"] == ["rapid_invoice"],
            "summary.json 内单条运行快照的 query 注入证据不应被 fallback 覆盖",
        )

        _write_runtime_filter_snapshot_audit(
            out_dir,
            runtime_snapshot,
            stage="summary_written",
            extra={"source_count": 1},
        )
        loaded = load_runtime_filter_audit_snapshot(out_dir, fallback_snapshot)
        _assert(
            loaded["mapping_stage"] == "query_mapped",
            "审计文件存在时，上游管线应优先使用最新运行时快照",
        )
        _assert(
            loaded["applied_filter_keys"] == ["rapid_invoice"],
            "上游管线读取审计快照时应保留真实已生效筛选项",
        )
        _assert(
            loaded["verification_details"]["rapid_invoice"]["matched_values"] == ["1013"],
            "上游管线读取审计快照时应保留验证详情，供入库和详情页解释",
        )
        _assert(
            loaded["runtime_audit_stage"] == "summary_written",
            "上游管线读取审计快照时应保留最终审计阶段",
        )
        selected_with_audit = select_source_filter_snapshot_for_db(
            audit_exists=True,
            audit_snapshot=loaded,
            summary_snapshot=summary_snapshot,
            fallback_snapshot=fallback_snapshot,
        )
        _assert(
            selected_with_audit["mapping_stage"] == "query_mapped",
            "审计文件存在时，入库应优先使用最终审计快照",
        )
        _assert(
            selected_with_audit["applied_filter_keys"] == ["rapid_invoice"],
            "最终审计快照应优先于 summary.json 内较早的 query 注入态",
        )
        _assert(
            selected_with_audit["runtime_audit_source"] == "_channel_filter_runtime_snapshot.json",
            "入库选择最终审计快照时应保留审计来源",
        )


def validate_runtime_audit_evidence_classifier_contract() -> None:
    report = build_runtime_audit_report(
        {
            "stage": "visible_filter_toggle_checked",
            "snapshot": {
                "channel_id": "ali1688",
                "channel_type": "ali1688",
                "configured_filters": {
                    "single_piece_free_shipping": True,
                    "encrypted_waybill": True,
                    "selected_distributors": True,
                },
                "configured_enabled_filter_keys": [
                    "single_piece_free_shipping",
                    "encrypted_waybill",
                    "selected_distributors",
                ],
                "filter_status_map": {
                    "single_piece_free_shipping": {
                        "status": "applied",
                        "mapping_stage": "ui_automation",
                        "verification_detail": {
                            "verification_mode": "dom_toggle_action",
                            "panel_term_selected_after_action": True,
                            "result_signature_changed": True,
                            "semantic_verification_stage": "direct_entry_result_shift_observed",
                        },
                    },
                    "encrypted_waybill": {
                        "status": "applied",
                        "mapping_stage": "ui_automation",
                        "verification_detail": {
                            "verification_mode": "dom_panel_action",
                            "panel_term_selected_after_action": True,
                            "result_signature_changed": False,
                        },
                    },
                    "selected_distributors": {
                        "status": "unapplied",
                        "reason": "ui_apply_not_observed",
                        "mapping_stage": "mixed",
                        "verification_detail": {
                            "verification_mode": "dom_toggle_action",
                            "entry_click_attempted": True,
                            "entry_click_succeeded": True,
                            "panel_term_selected_after_action": False,
                            "result_signature_changed": False,
                        },
                    },
                },
                "mapping_stage": "mixed",
            },
        }
    )
    by_key = {item["filter_key"]: item for item in report["filters"]}
    _assert(
        report["report_type"] == "single_runtime_audit",
        "单文件审计报告应声明 report_type，便于消费方区分报告形态",
    )
    _assert(
        report["report_schema_version"] == AUDIT_REPORT_SCHEMA_VERSION,
        "单文件审计报告应声明稳定 schema version",
    )
    _assert(
        report["filter_labels"]["single_piece_free_shipping"] == "1件代发包邮",
        "审计报告应保留 snapshot 投影出的中文筛选标签",
    )
    _assert(
        by_key["encrypted_waybill"]["label"] == "密文面单",
        "审计分类明细应带出中文标签，便于人读报告定位缺口",
    )
    _assert(
        by_key["single_piece_free_shipping"]["evidence_level"] == "site_strong",
        "审计分类器应把独立入口选中且结果签名变化的组合语义项判为强站点证据",
    )
    _assert(
        by_key["single_piece_free_shipping"]["can_close_real_site_gap"] is True,
        "独立入口已选中且结果变化时，可关闭 single_piece_free_shipping 的真实站点缺口",
    )
    _assert(
        by_key["encrypted_waybill"]["evidence_level"] == "panel_action_applied_without_result_shift",
        "密文面单只选中但无结果变化时，不能误判为真实闭环",
    )
    _assert(
        by_key["encrypted_waybill"]["can_close_real_site_gap"] is False,
        "密文面单缺少结果签名变化时仍应保持待验证",
    )
    _assert(
        by_key["selected_distributors"]["evidence_level"] == "action_attempted_not_applied",
        "普通 checkbox 点击后未选中时应明确归为动作尝试失败",
    )
    _assert(
        report["strong_evidence_filter_keys"] == ["single_piece_free_shipping"],
        "审计报告只应把真正具备强站点证据的项放入 strong_evidence_filter_keys",
    )
    _assert(
        report["pending_filter_count"] == 2,
        "未形成强站点证据的项必须继续进入 pending_filters",
    )


def validate_semantic_dependency_pair_runtime_closure() -> None:
    runtime_snapshot = settings.normalize_channel_search_filter_snapshot(
        {
            "channel_id": "ali1688",
            "channel_type": "ali1688",
            "configured_filters": {
                "single_piece_drop_shipping": True,
                "free_shipping": True,
                "single_piece_free_shipping": True,
            },
            "configured_enabled_filter_keys": [
                "single_piece_drop_shipping",
                "free_shipping",
                "single_piece_free_shipping",
            ],
            "filter_status_map": {
                "single_piece_drop_shipping": {
                    "status": "applied",
                    "mapping_stage": "query_mapped",
                    "verification_detail": {
                        "verification_mode": "post_navigation_url",
                        "matched_values": ["1988226"],
                    },
                },
                "free_shipping": {
                    "status": "applied",
                    "mapping_stage": "query_mapped",
                    "verification_detail": {
                        "verification_mode": "post_navigation_url",
                        "matched_values": ["1"],
                    },
                },
                "single_piece_free_shipping": {
                    "status": "unapplied",
                    "reason": "semantic_combo_not_confirmed",
                    "mapping_stage": "snapshot_only",
                    "verification_detail": {
                        "semantic_dependencies": ["single_piece_drop_shipping", "free_shipping"],
                    },
                },
            },
        }
    )
    next_snapshot = _mark_runtime_snapshot_semantic_dependency_combos(runtime_snapshot)
    semantic_meta = next_snapshot["filter_status_map"]["single_piece_free_shipping"]
    _assert(
        semantic_meta["status"] == "applied",
        "依赖 query 项均有 URL 强证据时，组合语义项应标记为 applied",
    )
    _assert(
        semantic_meta["verification_detail"]["verification_mode"] == "semantic_dependency_pair",
        "组合语义项应记录 semantic_dependency_pair 验证模式",
    )
    _assert(
        semantic_meta["semantic_conclusion"] == "dependency_pair_strong_verified",
        "组合语义项应投影 dependency_pair_strong_verified 结论",
    )

    report = build_runtime_audit_report({"stage": "summary_written", "snapshot": next_snapshot})
    by_key = {item["filter_key"]: item for item in report["filters"]}
    _assert(
        by_key["single_piece_free_shipping"]["can_close_real_site_gap"] is True,
        "审计分类器应接受依赖对强证据闭环 1件代发包邮",
    )
    _assert(
        "single_piece_free_shipping" in report["strong_evidence_filter_keys"],
        "依赖对强证据闭环后应进入 strong_evidence_filter_keys",
    )


def validate_runtime_audit_batch_report_contract() -> None:
    strong_payload = {
        "stage": "summary_written",
        "audit_generated_at_epoch": 1000,
        "audit_run_id": "run-a",
        "snapshot": {
            "channel_id": "ali1688-a",
            "channel_type": "ali1688",
            "configured_filters": {
                "selected_distributors": True,
            },
            "configured_enabled_filter_keys": ["selected_distributors"],
            "filter_status_map": {
                "selected_distributors": {
                    "status": "applied",
                    "mapping_stage": "ui_automation",
                    "verification_detail": {
                        "verification_mode": "dom_toggle_action",
                        "panel_term_selected_after_action": True,
                        "result_signature_changed": True,
                    },
                },
            },
            "mapping_stage": "ui_automation",
        },
    }
    pending_payload = {
        "stage": "special_panel_candidates_checked",
        "audit_generated_at_epoch": 1100,
        "audit_run_id": "run-b",
        "snapshot": {
            "channel_id": "ali1688-b",
            "channel_type": "ali1688",
            "configured_filters": {
                "encrypted_waybill": True,
            },
            "configured_enabled_filter_keys": ["encrypted_waybill"],
            "filter_status_map": {
                "encrypted_waybill": {
                    "status": "unapplied",
                    "reason": "special_panel_open_failed",
                    "mapping_stage": "mixed",
                    "verification_detail": {
                        "verification_mode": "dom_panel_action",
                        "panel_trigger_clicked": True,
                        "entry_click_attempted": True,
                        "panel_term_selected_after_action": False,
                        "result_signature_changed": False,
                    },
                },
            },
            "mapping_stage": "mixed",
        },
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        first_dir = root / "task-a"
        second_dir = root / "nested" / "task-b"
        first_dir.mkdir(parents=True)
        second_dir.mkdir(parents=True)
        (first_dir / AUDIT_FILE_NAME).write_text(json.dumps(strong_payload, ensure_ascii=False), encoding="utf-8")
        (second_dir / AUDIT_FILE_NAME).write_text(json.dumps(pending_payload, ensure_ascii=False), encoding="utf-8")

        direct_report = build_runtime_audit_batch_report([first_dir, second_dir], recursive=False)
        _assert(
            direct_report["report_type"] == "runtime_audit_batch",
            "批量审计报告应声明 report_type，便于消费方识别聚合报告",
        )
        _assert(
            direct_report["report_schema_version"] == AUDIT_REPORT_SCHEMA_VERSION,
            "批量审计报告应声明稳定 schema version",
        )
        _assert(direct_report["audit_file_count"] == 2, "批量审计应支持多个显式输出目录")
        _assert(
            direct_report["strong_evidence_filter_keys"] == ["selected_distributors"],
            "批量审计应汇总所有真实强证据筛选项",
        )
        _assert(
            direct_report["strong_evidence_filter_keys_by_channel"] == {
                "ali1688-a": ["selected_distributors"],
                "ali1688-b": [],
            },
            "批量审计应按渠道保留强证据索引，不能只依赖全局 key 汇总",
        )
        _assert(
            direct_report["filter_labels"]["selected_distributors"] == "分销严选",
            "批量审计应聚合快照中的中文筛选标签",
        )
        _assert(
            direct_report["filter_labels"]["encrypted_waybill"] == "密文面单",
            "批量审计应保留待验证项的中文筛选标签",
        )
        _assert(
            direct_report["audit_run_ids"] == ["run-a", "run-b"],
            "批量审计应聚合审计运行 ID，方便区分真实运行批次",
        )
        _assert(
            direct_report["audit_generated_at_epochs"] == [1000.0, 1100.0],
            "批量审计应聚合审计生成时间，方便判断证据来源时间",
        )
        _assert(direct_report["pending_filter_count"] == 1, "批量审计应保留待验证项数量")
        _assert(
            direct_report["pending_filters"][0]["filter_key"] == "encrypted_waybill",
            "批量审计应保留待验证筛选项 key",
        )
        _assert(
            direct_report["pending_filters"][0]["channel_id"] == "ali1688-b",
            "批量审计待验证项必须保留来源渠道，便于后续按渠道解释缺口",
        )
        _assert(
            direct_report["pending_filters_by_channel"] == {
                "ali1688-a": [],
                "ali1688-b": [
                    {
                        "filter_key": "encrypted_waybill",
                        "evidence_level": "panel_action_attempted_not_applied",
                        "pending_reason": "special_panel_open_failed",
                        "audit_file": str(second_dir / AUDIT_FILE_NAME),
                    }
                ],
            },
            "批量审计应按渠道保留待验证项索引，便于详情页按渠道解释缺口",
        )
        _assert(
            direct_report["pending_filters"][0]["audit_file"].endswith(AUDIT_FILE_NAME),
            "批量审计应保留待验证项来源审计文件",
        )

        recursive_report = build_runtime_audit_batch_report([root], recursive=True)
        _assert(recursive_report["audit_file_count"] == 2, "递归审计应能发现嵌套输出目录中的审计文件")
        _assert(
            recursive_report["strong_evidence_filter_keys"] == ["selected_distributors"],
            "递归审计不应丢失强证据项",
        )
        _assert(
            recursive_report["strong_evidence_filter_keys_by_channel"]["ali1688-a"] == ["selected_distributors"],
            "递归审计不应丢失渠道级强证据索引",
        )
        _assert(
            recursive_report["pending_filters_by_channel"]["ali1688-b"][0]["filter_key"] == "encrypted_waybill",
            "递归审计不应丢失渠道级待验证项索引",
        )

        first_audit_file = first_dir / AUDIT_FILE_NAME
        second_audit_file = second_dir / AUDIT_FILE_NAME
        os.utime(first_audit_file, (1990, 1990))
        os.utime(second_audit_file, (1000, 1000))
        freshness_report = build_runtime_audit_batch_report(
            [root],
            recursive=True,
            max_age_seconds=60,
            now_epoch=2000,
        )
        _assert(freshness_report["audit_file_count"] == 2, "新鲜度检查不应隐藏总审计文件数量")
        _assert(freshness_report["fresh_audit_file_count"] == 1, "新鲜度检查应统计可用于 gate 的新鲜审计文件数量")
        _assert(freshness_report["stale_audit_file_count"] == 1, "新鲜度检查应统计超龄审计文件数量")
        _assert(
            freshness_report["stale_audit_files"] == [str(second_audit_file)],
            "新鲜度检查应列出超龄审计文件路径，便于定位旧证据",
        )
        _assert(
            freshness_report["pending_filter_count"] == 0,
            "超龄审计文件不应继续贡献 pending 证据，避免旧证据影响缺口判断",
        )
        stale_scoped_gate = build_runtime_audit_gate_report(
            freshness_report,
            required_filter_keys=["encrypted_waybill"],
            required_channel_id="ali1688-b",
        )
        _assert(
            stale_scoped_gate["gate_failure_reasons"] == ["scoped_audit_files_stale", "missing_strong_evidence"],
            "指定渠道只有超龄审计文件时，gate 应明确标记 scoped_audit_files_stale",
        )
        _assert(
            stale_scoped_gate["scoped_total_audit_file_count"] == 1
            and stale_scoped_gate["scoped_stale_audit_file_count"] == 1
            and stale_scoped_gate["scoped_audit_file_count"] == 0,
            "渠道 gate 应同时暴露总文件数、超龄文件数与可用新鲜文件数",
        )
        stale_required_run_report = build_runtime_audit_batch_report(
            [root],
            recursive=True,
            max_age_seconds=60,
            now_epoch=2000,
            required_audit_run_id="run-b",
        )
        stale_required_run_gate = build_runtime_audit_gate_report(
            stale_required_run_report,
            required_filter_keys=["encrypted_waybill"],
        )
        _assert(
            stale_required_run_gate["gate_failure_reasons"] == ["audit_run_files_stale", "missing_strong_evidence"],
            "指定运行批次存在但该批次审计文件超龄时，gate 应明确标记 audit_run_files_stale",
        )
        _assert(
            stale_required_run_gate["matched_audit_run_file_count"] == 1
            and stale_required_run_gate["matched_stale_audit_run_file_count"] == 1,
            "指定运行批次超龄时，gate 应暴露匹配批次文件数与匹配批次超龄文件数",
        )
        stale_required_scoped_run_gate = build_runtime_audit_gate_report(
            stale_required_run_report,
            required_filter_keys=["encrypted_waybill"],
            required_channel_id="ali1688-b",
        )
        _assert(
            stale_required_scoped_run_gate["gate_failure_reasons"] == [
                "scoped_audit_run_files_stale",
                "missing_strong_evidence",
            ],
            "指定渠道内运行批次存在但超龄时，gate 应明确标记 scoped_audit_run_files_stale",
        )

        run_scoped_report = build_runtime_audit_batch_report(
            [root],
            recursive=True,
            required_audit_run_id="run-a",
        )
        _assert(
            run_scoped_report["required_audit_run_id"] == "run-a",
            "批量审计应保留指定运行批次 ID，便于 gate 解释证据范围",
        )
        _assert(
            run_scoped_report["matched_audit_run_file_count"] == 1
            and run_scoped_report["unmatched_audit_run_file_count"] == 1,
            "指定运行批次时，批量审计应分别统计匹配与非匹配审计文件",
        )
        _assert(
            run_scoped_report["unmatched_audit_run_files"] == [str(second_audit_file)],
            "指定运行批次时，批量审计应列出非匹配审计文件路径",
        )
        _assert(
            run_scoped_report["strong_evidence_filter_keys"] == ["selected_distributors"],
            "指定运行批次时，匹配批次的强证据仍应可用于 gate",
        )
        _assert(
            run_scoped_report["pending_filter_count"] == 0,
            "指定运行批次时，非匹配批次不应贡献 pending 证据",
        )
        missing_run_report = build_runtime_audit_batch_report(
            [root],
            recursive=True,
            required_audit_run_id="run-missing",
        )
        missing_run_gate = build_runtime_audit_gate_report(
            missing_run_report,
            required_filter_keys=["selected_distributors"],
        )
        _assert(
            missing_run_gate["gate_failure_reasons"] == ["audit_run_id_not_found", "missing_strong_evidence"],
            "指定不存在的运行批次时，gate 应明确标记 audit_run_id_not_found",
        )
        missing_scoped_run_gate = build_runtime_audit_gate_report(
            missing_run_report,
            required_filter_keys=["selected_distributors"],
            required_channel_id="ali1688-a",
        )
        _assert(
            missing_scoped_run_gate["gate_failure_reasons"] == [
                "scoped_audit_run_id_not_found",
                "missing_strong_evidence",
            ],
            "指定渠道下不存在运行批次时，gate 应明确标记 scoped_audit_run_id_not_found",
        )

        latest_run_report = build_runtime_audit_batch_report(
            [root],
            recursive=True,
            latest_audit_run_only=True,
        )
        _assert(
            latest_run_report["latest_audit_run_id"] == "run-b"
            and latest_run_report["required_audit_run_id"] == "run-b",
            "自动选择最新运行批次时，应使用 audit_generated_at_epoch 最大的 audit_run_id 作为 gate 范围",
        )
        _assert(
            latest_run_report["matched_audit_run_file_count"] == 1
            and latest_run_report["unmatched_audit_run_file_count"] == 1,
            "自动选择最新运行批次时，仍应统计匹配与非匹配审计文件数量",
        )
        _assert(
            latest_run_report["pending_filter_count"] == 1
            and latest_run_report["pending_filters"][0]["filter_key"] == "encrypted_waybill",
            "自动选择最新运行批次时，只能保留最新批次自己的 pending 证据",
        )
        channel_latest_run_report = build_runtime_audit_batch_report(
            [root],
            recursive=True,
            latest_audit_run_only=True,
            latest_audit_run_channel_id="ali1688-a",
        )
        _assert(
            channel_latest_run_report["latest_audit_run_channel_id"] == "ali1688-a"
            and channel_latest_run_report["latest_audit_run_id"] == "run-a"
            and channel_latest_run_report["required_audit_run_id"] == "run-a",
            "按渠道要求自动选择最新运行批次时，应只在该渠道自己的审计文件中选择 latest audit_run_id",
        )
        _assert(
            channel_latest_run_report["strong_evidence_filter_keys"] == ["selected_distributors"]
            and channel_latest_run_report["pending_filter_count"] == 0,
            "按渠道选择最新运行批次时，其他渠道的 pending 证据不能进入当前 gate 范围",
        )

        missing_run_id_dir = root / "missing-run-id"
        missing_run_id_dir.mkdir()
        (missing_run_id_dir / AUDIT_FILE_NAME).write_text(
            json.dumps(
                {
                    "stage": "summary_written",
                    "snapshot": {
                        "channel_id": "ali1688-missing-run",
                        "channel_type": "ali1688",
                        "configured_filters": {"selected_distributors": True},
                        "configured_enabled_filter_keys": ["selected_distributors"],
                        "filter_status_map": {
                            "selected_distributors": {
                                "status": "applied",
                                "mapping_stage": "ui_automation",
                                "verification_detail": {
                                    "verification_mode": "dom_toggle_action",
                                    "panel_term_selected_after_action": True,
                                    "result_signature_changed": True,
                                },
                            }
                        },
                        "mapping_stage": "ui_automation",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        latest_missing_run_id_report = build_runtime_audit_batch_report(
            [missing_run_id_dir],
            latest_audit_run_only=True,
        )
        latest_missing_run_id_gate = build_runtime_audit_gate_report(
            latest_missing_run_id_report,
            required_filter_keys=["selected_distributors"],
        )
        _assert(
            latest_missing_run_id_gate["gate_failure_reasons"] == [
                "latest_audit_run_id_missing",
                "missing_strong_evidence",
            ],
            "自动选择最新运行批次但审计文件缺少 audit_run_id 时，gate 必须失败而不能退化成全部文件可用",
        )


def validate_runtime_audit_gate_report_contract() -> None:
    batch_report = {
        "audit_file_count": 2,
        "strong_evidence_filter_keys": ["selected_distributors", "free_shipping"],
        "filter_labels": {
            "selected_distributors": "分销严选",
            "free_shipping": "包邮",
            "encrypted_waybill": "密文面单",
        },
        "pending_filter_count": 1,
        "pending_filters": [
            {
                "filter_key": "encrypted_waybill",
                "evidence_level": "panel_action_applied_without_result_shift",
                "pending_reason": "panel_action_selected_but_result_shift_not_observed",
            }
        ],
        "reports": [
            {
                "audit_file": "runtime-audit.json",
                "audit_file_fresh": True,
                "audit_run_id_matched": True,
                "filter_labels": {
                    "selected_distributors": "分销严选",
                    "free_shipping": "包邮",
                },
            },
            {
                "audit_file": "runtime-audit-2.json",
                "audit_file_fresh": True,
                "audit_run_id_matched": True,
                "filter_labels": {},
            }
        ],
    }
    passed_report = build_runtime_audit_gate_report(
        batch_report,
        required_filter_keys=["selected_distributors", "selected_distributors", "free_shipping"],
    )
    _assert(
        passed_report["report_type"] == "runtime_audit_gate",
        "gate 审计报告应声明 report_type，便于自动化消费方识别验收报告",
    )
    _assert(
        passed_report["report_schema_version"] == AUDIT_REPORT_SCHEMA_VERSION,
        "gate 审计报告应声明稳定 schema version",
    )
    _assert(
        passed_report["required_filter_source"] == "manual",
        "默认直接传入 required filters 时，gate 报告应声明来源为 manual",
    )
    _assert(
        passed_report["required_filter_config_channel_id"] == "",
        "默认直接传入 required filters 时，不应伪造配置渠道来源",
    )
    _assert(passed_report["passed"] is True, "所有 required filters 都进入强证据集合时，验收门槛应通过")
    _assert(
        passed_report["required_filter_keys"] == ["selected_distributors", "free_shipping"],
        "验收门槛应去重 required filters，避免重复 key 干扰结果",
    )
    _assert(
        passed_report["required_filter_labels"] == {
            "selected_distributors": "分销严选",
            "free_shipping": "包邮",
        },
        "验收门槛应提供所有 required filters 的中文标签映射",
    )
    _assert(passed_report["missing_strong_filter_keys"] == [], "通过时不应保留缺失强证据项")
    _assert(passed_report["gate_failure_reasons"] == [], "通过报告不应包含失败原因")
    _assert(
        passed_report["can_close_required_filter_gaps"] is True,
        "通过报告应提供可直接关闭 required filter 缺口的布尔字段",
    )
    _assert(
        passed_report["closure_blockers"] == [],
        "通过报告不应包含 required filter 缺口关闭阻塞项",
    )
    _assert(
        passed_report["closure_summary"] == {
            "can_close_required_filter_gaps": True,
            "closure_blockers": [],
            "strong_required_filter_keys": ["selected_distributors", "free_shipping"],
            "pending_required_filter_keys": [],
            "missing_required_filter_keys": [],
        },
        "通过报告应提供机器可消费的 required filter 缺口关闭摘要",
    )
    _assert(
        passed_report["required_filter_gap_todos"] == [],
        "通过报告不应生成 required filter 缺口待办项",
    )
    passed_todo_report = build_runtime_audit_todo_report(passed_report)
    expected_passed_todo_items = {
        "report_type": "runtime_audit_gate_todos",
        "report_schema_version": AUDIT_REPORT_SCHEMA_VERSION,
        "passed": True,
        "can_close_required_filter_gaps": True,
        "required_channel_id": "",
        "required_filter_source": "manual",
        "required_filter_config_channel_id": "",
        "required_filter_keys": ["selected_distributors", "free_shipping"],
        "required_filter_labels": {
            "selected_distributors": "分销严选",
            "free_shipping": "包邮",
        },
        "closure_blockers": [],
        "freshness_check": {},
        "fresh_audit_file_count": 0,
        "stale_audit_file_count": 0,
        "stale_audit_files": [],
        "required_audit_run_id": "",
        "matched_audit_run_file_count": 0,
        "unmatched_audit_run_file_count": 0,
        "unmatched_audit_run_files": [],
        "scoped_audit_file_count": 2,
        "scoped_total_audit_file_count": 2,
        "scoped_stale_audit_file_count": 0,
        "scoped_unmatched_audit_run_file_count": 0,
        "required_filter_gap_todos": [],
    }
    for key, expected in expected_passed_todo_items.items():
        _assert(passed_todo_report.get(key) == expected, f"todo 报告通过结构字段 {key} 不符合预期")
    _assert(
        passed_report["required_filter_status_map"]["selected_distributors"]["status"] == "strong",
        "required filter 已形成强证据时，状态映射应标记为 strong",
    )
    _assert(
        passed_report["required_filter_status_map"]["selected_distributors"]["label"] == "分销严选",
        "required filter 状态映射应带中文标签，便于直接展示 gate 结果",
    )
    _assert(
        passed_report["required_filter_status_counts"] == {"strong": 2, "pending": 0, "missing": 0},
        "通过报告应汇总 required filter 状态计数",
    )
    _assert(
        passed_report["required_filter_next_actions"][0]["action"] == "none",
        "已形成强证据的 required filter 不应再提示额外动作",
    )

    failed_report = build_runtime_audit_gate_report(
        batch_report,
        required_filter_keys=["selected_distributors", "encrypted_waybill"],
    )
    _assert(failed_report["passed"] is False, "required filter 缺少强证据时，验收门槛必须失败")
    _assert(
        failed_report["missing_strong_filter_keys"] == ["encrypted_waybill"],
        "验收门槛必须明确列出缺失强证据的筛选项",
    )
    _assert(
        failed_report["required_filter_labels"] == {
            "selected_distributors": "分销严选",
            "encrypted_waybill": "密文面单",
        },
        "失败报告也应提供所有 required filters 的中文标签映射",
    )
    _assert(
        failed_report["missing_strong_filter_labels"] == {"encrypted_waybill": "密文面单"},
        "验收门槛应同时提供缺失强证据项的中文标签",
    )
    _assert(
        failed_report["gate_failure_reasons"] == ["missing_strong_evidence"],
        "缺少 required filter 强证据时，失败原因应标记 missing_strong_evidence",
    )
    _assert(
        failed_report["can_close_required_filter_gaps"] is False,
        "缺少强证据时，不允许关闭 required filter 缺口",
    )
    _assert(
        failed_report["closure_blockers"] == ["missing_strong_evidence"],
        "缺少强证据时，关闭阻塞项应直接暴露 missing_strong_evidence",
    )
    _assert(
        failed_report["closure_summary"]["strong_required_filter_keys"] == ["selected_distributors"],
        "关闭摘要应列出已满足强证据的 required filters",
    )
    _assert(
        failed_report["closure_summary"]["pending_required_filter_keys"] == ["encrypted_waybill"],
        "关闭摘要应列出仍停留在 pending 的 required filters",
    )
    _assert(
        failed_report["closure_summary"]["missing_required_filter_keys"] == [],
        "pending 项不应被重复计入 missing required filters",
    )
    _assert(
        failed_report["missing_filter_diagnostics"] == [
            {
                "filter_key": "encrypted_waybill",
                "label": "密文面单",
                "diagnosis": "pending_without_strong_evidence",
                "pending_matches": [
                    {
                        "evidence_level": "panel_action_applied_without_result_shift",
                        "pending_reason": "panel_action_selected_but_result_shift_not_observed",
                        "audit_file": "",
                        "channel_id": "",
                    }
                ],
            }
        ],
        "缺失强证据项若已有 pending 记录，应在诊断中带出 pending reason",
    )
    _assert(
        failed_report["required_filter_status_map"]["selected_distributors"]["status"] == "strong",
        "失败报告中已具备强证据的 required filter 仍应标记为 strong",
    )
    _assert(
        failed_report["required_filter_status_map"]["encrypted_waybill"]["status"] == "pending",
        "失败报告中只有 pending 证据的 required filter 应标记为 pending",
    )
    _assert(
        failed_report["required_filter_status_map"]["encrypted_waybill"]["diagnosis"] == "pending_without_strong_evidence",
        "pending 状态应保留缺失诊断原因",
    )
    _assert(
        failed_report["required_filter_next_actions"][1]["label"] == "密文面单",
        "下一步建议应带中文标签，避免自动化报告只暴露内部 key",
    )
    _assert(
        failed_report["required_filter_status_counts"] == {"strong": 1, "pending": 1, "missing": 0},
        "失败报告应汇总 strong / pending / missing 的 required filter 数量",
    )
    _assert(
        failed_report["required_filter_next_actions"][1]["action"] == "inspect_pending_audit_file",
        "只有 pending 证据的 required filter 应提示检查 pending 审计文件",
    )
    _assert(
        failed_report["required_filter_gap_todos"] == [
            {
                "filter_key": "encrypted_waybill",
                "label": "密文面单",
                "status": "pending",
                "required_channel_id": "",
                "action": "inspect_pending_audit_file",
                "reason": "pending_without_strong_evidence",
                "blocking_reasons": ["missing_strong_evidence"],
                "pending_audit_files": [],
            }
        ],
        "只有 pending 证据的 required filter 应生成可执行待办项，指导检查 pending 审计文件",
    )
    failed_todo_report = build_runtime_audit_todo_report(failed_report)
    _assert(
        failed_todo_report["report_type"] == "runtime_audit_gate_todos",
        "todo 报告应声明独立 report_type",
    )
    _assert(
        failed_todo_report["passed"] is False
        and failed_todo_report["can_close_required_filter_gaps"] is False,
        "todo 报告应保留 gate 通过状态和缺口关闭状态",
    )
    _assert(
        failed_todo_report["closure_blockers"] == ["missing_strong_evidence"],
        "todo 报告应保留阻塞原因，便于 CI 直接展示",
    )
    _assert(
        failed_todo_report["required_filter_gap_todos"] == failed_report["required_filter_gap_todos"],
        "todo 报告应直接透出可执行缺口待办",
    )

    empty_report = build_runtime_audit_gate_report(
        {
            "audit_file_count": 0,
            "strong_evidence_filter_keys": ["selected_distributors"],
            "filter_labels": {
                "selected_distributors": "分销严选",
            },
            "pending_filter_count": 0,
            "pending_filters": [],
            "reports": [],
        },
        required_filter_keys=["selected_distributors"],
    )
    _assert(empty_report["passed"] is False, "没有任何审计文件时，即使传入强证据 key 也不能通过验收")
    _assert(
        empty_report["required_filter_labels"] == {"selected_distributors": "分销严选"},
        "没有任何审计文件时，required filter 标签仍应从共享定义或传入标签中解析",
    )
    _assert(
        empty_report["gate_failure_reasons"] == ["audit_files_empty"],
        "没有任何审计文件时，失败原因应标记 audit_files_empty",
    )
    _assert(
        empty_report["closure_summary"] == {
            "can_close_required_filter_gaps": False,
            "closure_blockers": ["audit_files_empty"],
            "strong_required_filter_keys": ["selected_distributors"],
            "pending_required_filter_keys": [],
            "missing_required_filter_keys": [],
        },
        "没有审计文件时，即使 batch 中存在强证据 key，关闭摘要也必须保留审计文件缺失阻塞项",
    )

    empty_shared_label_report = build_runtime_audit_gate_report(
        {
            "audit_file_count": 0,
            "strong_evidence_filter_keys": [],
            "pending_filter_count": 0,
            "pending_filters": [],
            "reports": [],
        },
        required_filter_keys=["encrypted_waybill"],
    )
    _assert(
        empty_shared_label_report["required_filter_labels"] == {"encrypted_waybill": "密文面单"},
        "没有审计文件且没有 batch 标签时，required filter 标签应回退到共享筛选定义",
    )

    no_required_report = build_runtime_audit_gate_report(
        {
            "audit_file_count": 1,
            "strong_evidence_filter_keys": ["selected_distributors"],
            "filter_labels": {
                "selected_distributors": "分销严选",
            },
            "pending_filter_count": 0,
            "pending_filters": [],
            "reports": [
                {
                    "audit_file": "runtime-audit.json",
                    "audit_file_fresh": True,
                    "audit_run_id_matched": True,
                }
            ],
        },
        required_filter_keys=[],
    )
    _assert(no_required_report["required_filter_keys"] == [], "显式请求门槛但未解析到 required filters 时，应保留空 required 列表")
    _assert(no_required_report["passed"] is False, "显式请求门槛但 required filters 为空时不能通过验收")
    _assert(
        no_required_report["gate_failure_reasons"] == ["required_filters_empty"],
        "显式请求门槛但 required filters 为空时，失败原因应标记 required_filters_empty",
    )
    _assert(
        no_required_report["closure_summary"] == {
            "can_close_required_filter_gaps": False,
            "closure_blockers": ["required_filters_empty"],
            "strong_required_filter_keys": [],
            "pending_required_filter_keys": [],
            "missing_required_filter_keys": [],
        },
        "空 required filters 报告也应提供稳定关闭摘要，便于自动化消费",
    )
    _assert(
        no_required_report["required_filter_gap_todos"] == [],
        "空 required filters 没有具体筛选项，不应生成缺口待办项",
    )

    scoped_batch_report = {
        "audit_file_count": 2,
        "strong_evidence_filter_keys": ["selected_distributors", "free_shipping"],
        "filter_labels": {
            "selected_distributors": "分销严选",
            "free_shipping": "包邮",
        },
        "pending_filter_count": 0,
        "pending_filters": [],
        "pending_filters_by_channel": {
            "ali1688-a": [],
            "ali1688-b": [
                {
                    "filter_key": "selected_distributors",
                    "evidence_level": "action_attempted_not_applied",
                    "pending_reason": "ui_apply_not_observed",
                    "audit_file": "/tmp/b/_channel_filter_runtime_snapshot.json",
                }
            ],
        },
        "reports": [
            {
                "channel_id": "ali1688-a",
                "strong_evidence_filter_keys": ["selected_distributors"],
            },
            {
                "channel_id": "ali1688-b",
                "strong_evidence_filter_keys": ["free_shipping"],
            },
        ],
    }
    scoped_passed_report = build_runtime_audit_gate_report(
        scoped_batch_report,
        required_filter_keys=["selected_distributors"],
        required_channel_id="ali1688-a",
    )
    _assert(scoped_passed_report["passed"] is True, "指定渠道拥有 required filter 强证据时，渠道作用域门槛应通过")
    _assert(
        scoped_passed_report["scoped_strong_evidence_filter_keys"] == ["selected_distributors"],
        "渠道作用域门槛只应汇总指定渠道自己的强证据",
    )
    scoped_failed_report = build_runtime_audit_gate_report(
        scoped_batch_report,
        required_filter_keys=["selected_distributors"],
        required_channel_id="ali1688-b",
    )
    _assert(scoped_failed_report["passed"] is False, "B 渠道不能借用 A 渠道的 required filter 强证据")
    _assert(
        scoped_failed_report["missing_strong_filter_keys"] == ["selected_distributors"],
        "渠道作用域门槛必须指出指定渠道缺少的强证据项",
    )
    _assert(
        scoped_failed_report["missing_filter_diagnostics"][0]["diagnosis"] == "pending_without_strong_evidence",
        "渠道作用域缺失项若在该渠道 pending 中出现，应标记为 pending_without_strong_evidence",
    )
    _assert(
        scoped_failed_report["missing_filter_diagnostics"][0]["pending_matches"][0]["channel_id"] == "ali1688-b",
        "渠道作用域缺失诊断应补齐当前 required_channel_id",
    )
    scoped_missing_channel_report = build_runtime_audit_gate_report(
        scoped_batch_report,
        required_filter_keys=["selected_distributors"],
        required_channel_id="ali1688-missing",
    )
    _assert(scoped_missing_channel_report["scoped_audit_file_count"] == 0, "缺少指定渠道审计文件时，作用域计数必须为 0")
    _assert(scoped_missing_channel_report["passed"] is False, "缺少指定渠道审计文件时不能通过门槛")
    _assert(
        scoped_missing_channel_report["gate_failure_reasons"] == ["scoped_audit_files_empty", "missing_strong_evidence"],
        "缺少指定渠道审计文件且缺强证据时，失败原因应同时保留作用域审计缺失与强证据缺失",
    )
    _assert(
        scoped_missing_channel_report["closure_summary"] == {
            "can_close_required_filter_gaps": False,
            "closure_blockers": ["scoped_audit_files_empty", "missing_strong_evidence"],
            "strong_required_filter_keys": [],
            "pending_required_filter_keys": [],
            "missing_required_filter_keys": ["selected_distributors"],
        },
        "指定渠道缺少审计文件时，关闭摘要应同时暴露渠道作用域阻塞与 missing required filters",
    )
    _assert(
        scoped_missing_channel_report["missing_filter_diagnostics"] == [
            {
                "filter_key": "selected_distributors",
                "label": "分销严选",
                "diagnosis": "not_observed_in_audit",
                "pending_matches": [],
            }
        ],
        "缺少指定渠道审计文件时，缺失诊断应明确为 not_observed_in_audit",
    )
    _assert(
        scoped_missing_channel_report["required_filter_status_map"]["selected_distributors"]["status"] == "missing",
        "缺少指定渠道审计文件时，required filter 状态应标记为 missing",
    )
    _assert(
        scoped_missing_channel_report["required_filter_status_counts"] == {"strong": 0, "pending": 0, "missing": 1},
        "缺少指定渠道审计文件时，状态计数应体现 missing",
    )
    _assert(
        scoped_missing_channel_report["required_filter_next_actions"][0]["action"] == "run_real_crawl_and_generate_audit",
        "完全未观察到的 required filter 应提示重新跑真实爬取并生成审计产物",
    )
    _assert(
        scoped_missing_channel_report["required_filter_gap_todos"] == [
            {
                "filter_key": "selected_distributors",
                "label": "分销严选",
                "status": "missing",
                "required_channel_id": "ali1688-missing",
                "action": "run_real_crawl_and_generate_audit",
                "reason": "not_observed_in_audit",
                "blocking_reasons": ["scoped_audit_files_empty", "missing_strong_evidence"],
                "pending_audit_files": [],
            }
        ],
        "指定渠道缺少审计文件时，应生成带渠道 ID 的缺口待办项",
    )

    _assert(runtime_audit_gate_exit_code(passed_report, strict=False) == 0, "非 strict 模式下，通过报告应返回 0")
    _assert(runtime_audit_gate_exit_code(failed_report, strict=False) == 0, "非 strict 模式下，失败报告也应保持兼容返回 0")
    _assert(runtime_audit_gate_exit_code(passed_report, strict=True) == 0, "strict 模式下，通过报告应返回 0")
    _assert(runtime_audit_gate_exit_code(failed_report, strict=True) == 1, "strict 模式下，失败报告必须返回非 0")
    _assert(runtime_audit_gate_exit_code(no_required_report, strict=True) == 1, "strict 模式下，空 required filters 必须返回非 0")


def validate_runtime_audit_required_filters_from_config_contract() -> None:
    source_channels_cfg = normalize_source_channels_config(
        {
            "active_channel_id": "ali1688-a",
            "channels": [
                {
                    "channel_id": "ali1688-a",
                    "channel_type": "ali1688",
                    "label": "1688 A",
                    "enabled": True,
                    "accounts": [{"account_id": "a1", "label": "A1", "enabled": True}],
                },
                {
                    "channel_id": "ali1688-b",
                    "channel_type": "ali1688",
                    "label": "1688 B",
                    "enabled": True,
                    "accounts": [{"account_id": "b1", "label": "B1", "enabled": True}],
                },
            ],
        }
    )
    crawl_cfg = settings.normalize_crawl_config(
        {
            "channel_search_filters": [
                {
                    "channel_id": "ali1688-a",
                    "filters": {
                        "single_piece_free_shipping": True,
                        "encrypted_waybill": True,
                    },
                },
                {
                    "channel_id": "ali1688-b",
                    "filters": {
                        "selected_distributors": True,
                    },
                },
            ],
        },
        source_channels_cfg=source_channels_cfg,
    )
    required_a = load_required_filters_from_config(
        "ali1688-a",
        crawl_cfg=crawl_cfg,
        source_channels_cfg=source_channels_cfg,
    )
    required_b = load_required_filters_from_config(
        "ali1688-b",
        crawl_cfg=crawl_cfg,
        source_channels_cfg=source_channels_cfg,
    )
    _assert(
        required_a == ["single_piece_free_shipping", "encrypted_waybill"],
        "按渠道读取 required filters 时，ali1688-a 只能包含自己的启用筛选项",
    )
    _assert(
        required_b == ["selected_distributors"],
        "按渠道读取 required filters 时，ali1688-b 不能串用 ali1688-a 的筛选项",
    )
    gate_report = build_runtime_audit_gate_report(
        {
            "audit_file_count": 0,
            "strong_evidence_filter_keys": [],
            "pending_filter_count": 0,
            "pending_filters": [],
            "reports": [],
        },
        required_filter_keys=required_a,
        required_channel_id="ali1688-a",
        required_filter_source="config",
        required_filter_config_channel_id="ali1688-a",
    )
    _assert(
        gate_report["required_filter_source"] == "config",
        "配置驱动 required filters 时，gate 报告应声明来源为 config",
    )
    _assert(
        gate_report["required_filter_config_channel_id"] == "ali1688-a",
        "配置驱动 required filters 时，gate 报告应保留配置来源渠道 ID",
    )
    todo_report = build_runtime_audit_todo_report(gate_report)
    _assert(
        todo_report["required_filter_source"] == "config",
        "配置驱动 required filters 的 todo 报告应保留来源为 config",
    )
    _assert(
        todo_report["required_filter_config_channel_id"] == "ali1688-a",
        "配置驱动 required filters 的 todo 报告应保留配置来源渠道 ID",
    )
    _assert(
        todo_report["required_filter_gap_todos"][0]["required_channel_id"] == "ali1688-a",
        "配置驱动 required filters 的 todo 报告应保留待办所属渠道",
    )


def validate_runtime_audit_todo_report_cli_contract() -> None:
    script_path = BASE_DIR / "scripts" / "inspect_channel_filter_runtime_audit.py"
    env = {"PYTHONPATH": str(SRC_DIR)}

    invalid = subprocess.run(
        [sys.executable, str(script_path), "--todo-report", "outputs", "scratch"],
        cwd=BASE_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    _assert(invalid.returncode != 0, "--todo-report 未请求 gate 报告时必须返回非 0，避免输出无意义待办")
    _assert(
        "--todo-report requires --required-filter or --require-configured-channel" in invalid.stderr,
        "--todo-report 未搭配 required filter 时应给出明确 parser 错误",
    )

    with tempfile.TemporaryDirectory() as empty_tmpdir:
        non_strict = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--recursive",
                "--required-filter",
                "encrypted_waybill",
                "--todo-report",
                empty_tmpdir,
            ],
            cwd=BASE_DIR,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
    _assert(non_strict.returncode == 0, "非 strict 模式下，失败 gate 的 todo 报告仍应保持兼容返回 0")
    non_strict_payload = json.loads(non_strict.stdout)
    _assert(
        non_strict_payload["report_type"] == "runtime_audit_gate_todos",
        "CLI --todo-report 应输出精简待办报告，而不是完整 gate 报告",
    )
    _assert(non_strict_payload["passed"] is False, "缺少真实审计强证据时，todo 报告应保留 passed=false")

    with tempfile.TemporaryDirectory() as empty_tmpdir:
        strict = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--recursive",
                "--required-filter",
                "encrypted_waybill",
                "--todo-report",
                "--strict-exit",
                empty_tmpdir,
            ],
            cwd=BASE_DIR,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
    _assert(strict.returncode == 1, "--todo-report 不能绕过 --strict-exit 的 gate 失败退出码")
    strict_payload = json.loads(strict.stdout)
    _assert(
        strict_payload["report_type"] == "runtime_audit_gate_todos" and strict_payload["passed"] is False,
        "strict 模式下仍应输出可读 todo 报告，供 CI 展示缺口",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        audit_dir = Path(tmpdir)
        audit_file = audit_dir / AUDIT_FILE_NAME
        audit_file.write_text(
            json.dumps(
                {
                    "stage": "summary_written",
                    "snapshot": {
                        "channel_id": "ali1688",
                        "channel_type": "ali1688",
                        "configured_filters": {"selected_distributors": True},
                        "configured_enabled_filter_keys": ["selected_distributors"],
                        "filter_status_map": {
                            "selected_distributors": {
                                "status": "applied",
                                "mapping_stage": "ui_automation",
                                "verification_detail": {
                                    "verification_mode": "dom_toggle_action",
                                    "panel_term_selected_after_action": True,
                                    "result_signature_changed": True,
                                },
                            }
                        },
                        "mapping_stage": "ui_automation",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        os.utime(audit_file, (1000, 1000))
        stale = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--required-filter",
                "selected_distributors",
                "--max-age-minutes",
                "1",
                str(audit_dir),
            ],
            cwd=BASE_DIR,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        stale_todo = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--required-filter",
                "selected_distributors",
                "--max-age-minutes",
                "1",
                "--todo-report",
                str(audit_dir),
            ],
            cwd=BASE_DIR,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
    _assert(stale.returncode == 0, "非 strict 模式下，超龄 gate 报告仍应兼容返回 0")
    stale_payload = json.loads(stale.stdout)
    _assert(stale_payload["passed"] is False, "CLI 新鲜度检查应阻止超龄强证据通过 gate")
    _assert(
        stale_payload["gate_failure_reasons"] == ["stale_audit_files_only", "missing_strong_evidence"],
        "CLI 新鲜度检查应明确指出只有超龄审计文件可用",
    )
    _assert(stale_todo.returncode == 0, "非 strict 模式下，超龄 todo 报告仍应兼容返回 0")
    stale_todo_payload = json.loads(stale_todo.stdout)
    _assert(
        stale_todo_payload["report_type"] == "runtime_audit_gate_todos",
        "新鲜度门槛下 --todo-report 仍应输出精简待办报告",
    )
    _assert(
        stale_todo_payload["freshness_check"]["enabled"] is True
        and stale_todo_payload["stale_audit_file_count"] == 1
        and stale_todo_payload["stale_audit_files"] == [str(audit_file)],
        "新鲜度门槛下 todo 报告应透出超龄审计文件，避免 CI 只看到失败原因",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        run_a_dir = root / "run-a"
        run_b_dir = root / "run-b"
        run_a_dir.mkdir()
        run_b_dir.mkdir()
        (run_a_dir / AUDIT_FILE_NAME).write_text(
            json.dumps(
                {
                    "stage": "summary_written",
                    "audit_run_id": "run-a",
                    "snapshot": {
                        "channel_id": "ali1688-a",
                        "channel_type": "ali1688",
                        "configured_filters": {"selected_distributors": True},
                        "configured_enabled_filter_keys": ["selected_distributors"],
                        "filter_status_map": {
                            "selected_distributors": {
                                "status": "applied",
                                "mapping_stage": "ui_automation",
                                "verification_detail": {
                                    "verification_mode": "dom_toggle_action",
                                    "panel_term_selected_after_action": True,
                                    "result_signature_changed": True,
                                },
                            }
                        },
                        "mapping_stage": "ui_automation",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (run_b_dir / AUDIT_FILE_NAME).write_text(
            json.dumps(
                {
                    "stage": "special_panel_candidates_checked",
                    "audit_run_id": "run-b",
                    "snapshot": {
                        "channel_id": "ali1688-b",
                        "channel_type": "ali1688",
                        "configured_filters": {"encrypted_waybill": True},
                        "configured_enabled_filter_keys": ["encrypted_waybill"],
                        "filter_status_map": {
                            "encrypted_waybill": {
                                "status": "unapplied",
                                "reason": "special_panel_open_failed",
                                "mapping_stage": "mixed",
                                "verification_detail": {
                                    "verification_mode": "dom_panel_action",
                                    "panel_trigger_clicked": True,
                                    "entry_click_attempted": True,
                                    "panel_term_selected_after_action": False,
                                    "result_signature_changed": False,
                                },
                            }
                        },
                        "mapping_stage": "mixed",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        matching_run = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--recursive",
                "--required-filter",
                "selected_distributors",
                "--require-audit-run-id",
                "run-a",
                str(root),
            ],
            cwd=BASE_DIR,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        missing_run_todo = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--recursive",
                "--required-filter",
                "selected_distributors",
                "--require-audit-run-id",
                "run-missing",
                "--todo-report",
                str(root),
            ],
            cwd=BASE_DIR,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
    _assert(matching_run.returncode == 0, "匹配运行批次且具备强证据时，CLI gate 应保持通过")
    matching_run_payload = json.loads(matching_run.stdout)
    _assert(
        matching_run_payload["passed"] is True
        and matching_run_payload["matched_audit_run_file_count"] == 1
        and matching_run_payload["unmatched_audit_run_file_count"] == 1,
        "CLI 指定运行批次时应只使用匹配批次证据，并报告非匹配审计文件数量",
    )
    _assert(missing_run_todo.returncode == 0, "非 strict 模式下，缺失运行批次的 todo 报告仍应兼容返回 0")
    missing_run_todo_payload = json.loads(missing_run_todo.stdout)
    _assert(
        missing_run_todo_payload["closure_blockers"] == ["audit_run_id_not_found", "missing_strong_evidence"],
        "CLI 指定不存在运行批次时，todo 报告应明确指出 audit_run_id_not_found",
    )
    _assert(
        missing_run_todo_payload["required_audit_run_id"] == "run-missing"
        and missing_run_todo_payload["unmatched_audit_run_file_count"] == 2,
        "CLI todo 报告应透出运行批次限定条件和非匹配审计文件数量",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        older_dir = root / "older"
        latest_dir = root / "latest"
        older_dir.mkdir()
        latest_dir.mkdir()
        (older_dir / AUDIT_FILE_NAME).write_text(
            json.dumps(
                {
                    "stage": "summary_written",
                    "audit_generated_at_epoch": 1000,
                    "audit_run_id": "older-run",
                    "snapshot": {
                        "channel_id": "ali1688-a",
                        "channel_type": "ali1688",
                        "configured_filters": {"selected_distributors": True},
                        "configured_enabled_filter_keys": ["selected_distributors"],
                        "filter_status_map": {
                            "selected_distributors": {
                                "status": "applied",
                                "mapping_stage": "ui_automation",
                                "verification_detail": {
                                    "verification_mode": "dom_toggle_action",
                                    "panel_term_selected_after_action": True,
                                    "result_signature_changed": True,
                                },
                            }
                        },
                        "mapping_stage": "ui_automation",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (latest_dir / AUDIT_FILE_NAME).write_text(
            json.dumps(
                {
                    "stage": "special_panel_candidates_checked",
                    "audit_generated_at_epoch": 2000,
                    "audit_run_id": "latest-run",
                    "snapshot": {
                        "channel_id": "ali1688-b",
                        "channel_type": "ali1688",
                        "configured_filters": {"encrypted_waybill": True},
                        "configured_enabled_filter_keys": ["encrypted_waybill"],
                        "filter_status_map": {
                            "encrypted_waybill": {
                                "status": "unapplied",
                                "reason": "special_panel_open_failed",
                                "mapping_stage": "mixed",
                                "verification_detail": {
                                    "verification_mode": "dom_panel_action",
                                    "panel_trigger_clicked": True,
                                    "entry_click_attempted": True,
                                    "panel_term_selected_after_action": False,
                                    "result_signature_changed": False,
                                },
                            }
                        },
                        "mapping_stage": "mixed",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        os.utime(latest_dir / AUDIT_FILE_NAME, (1000, 1000))
        latest_run_todo = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--recursive",
                "--required-filter",
                "encrypted_waybill",
                "--latest-audit-run",
                "--todo-report",
                str(root),
            ],
            cwd=BASE_DIR,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        stale_latest_run_todo = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--recursive",
                "--required-filter",
                "encrypted_waybill",
                "--latest-audit-run",
                "--max-age-minutes",
                "1",
                "--todo-report",
                str(root),
            ],
            cwd=BASE_DIR,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        invalid_latest_combo = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--recursive",
                "--required-filter",
                "encrypted_waybill",
                "--latest-audit-run",
                "--require-audit-run-id",
                "latest-run",
                str(root),
            ],
            cwd=BASE_DIR,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
    _assert(latest_run_todo.returncode == 0, "非 strict 模式下，latest audit run todo 报告应兼容返回 0")
    latest_run_todo_payload = json.loads(latest_run_todo.stdout)
    _assert(
        latest_run_todo_payload["latest_audit_run_only"] is True
        and latest_run_todo_payload["latest_audit_run_id"] == "latest-run"
        and latest_run_todo_payload["required_audit_run_id"] == "latest-run",
        "CLI --latest-audit-run 应自动把最新 audit_run_id 作为 gate 范围并透出到 todo 报告",
    )
    _assert(
        latest_run_todo_payload["unmatched_audit_run_file_count"] == 1
        and latest_run_todo_payload["required_filter_gap_todos"][0]["status"] == "pending",
        "CLI --latest-audit-run 不能消费旧批次强证据，应保留最新批次 pending 待办",
    )
    _assert(stale_latest_run_todo.returncode == 0, "非 strict 模式下，最新批次超龄 todo 报告应兼容返回 0")
    stale_latest_run_todo_payload = json.loads(stale_latest_run_todo.stdout)
    _assert(
        stale_latest_run_todo_payload["closure_blockers"] == ["audit_run_files_stale", "missing_strong_evidence"],
        "CLI --latest-audit-run 搭配新鲜度门槛时，应明确指出最新运行批次证据超龄",
    )
    _assert(
        stale_latest_run_todo_payload["matched_audit_run_file_count"] == 1
        and stale_latest_run_todo_payload["matched_stale_audit_run_file_count"] == 1,
        "最新运行批次超龄 todo 报告应透出匹配批次文件数与匹配批次超龄文件数",
    )
    _assert(invalid_latest_combo.returncode != 0, "--latest-audit-run 不能与 --require-audit-run-id 同时使用")
    _assert(
        "--latest-audit-run cannot be combined with --require-audit-run-id" in invalid_latest_combo.stderr,
        "互斥运行批次参数应输出明确 parser 错误",
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
        ("channel_search_filters_per_channel_isolation", validate_channel_search_filters_per_channel_isolation),
        ("channel_search_filters_follow_active_channel_selection", validate_channel_search_filters_follow_active_channel_selection),
        ("channel_search_filters_unsupported_channel_stays_empty", validate_channel_search_filters_unsupported_channel_stays_empty),
        ("channel_search_filter_snapshot_normalization", validate_channel_search_filter_snapshot_normalization),
        ("channel_search_filter_runtime_state_projection", validate_channel_search_filter_runtime_state_projection),
        ("channel_search_filter_verification_detail_projection", validate_channel_search_filter_verification_detail_projection),
        ("semantic_combo_verification_detail_projection", validate_semantic_combo_verification_detail_projection),
        ("special_panel_verification_detail_projection", validate_special_panel_verification_detail_projection),
        ("special_panel_result_shift_observed_projection", validate_special_panel_result_shift_observed_projection),
        ("semantic_combo_no_result_shift_projection", validate_semantic_combo_no_result_shift_projection),
        ("special_panel_applied_no_result_shift_projection", validate_special_panel_applied_no_result_shift_projection),
        ("channel_search_filter_default_reason_by_mapping_type", validate_channel_search_filter_default_reason_by_mapping_type),
        ("shared_channel_search_filter_definition_contract", validate_shared_channel_search_filter_definition_contract),
        ("non_query_filter_runtime_html_probe", validate_non_query_filter_runtime_html_probe),
        ("non_query_filter_runtime_html_probe_without_dependencies", validate_non_query_filter_runtime_html_probe_without_dependencies),
        ("visible_filter_toggle_runtime_apply_for_ui_checkbox", validate_visible_filter_toggle_runtime_apply_for_ui_checkbox),
        ("visible_filter_toggle_runtime_apply_for_url_change_without_selected_state", validate_visible_filter_toggle_runtime_apply_for_url_change_without_selected_state),
        ("visible_filter_toggle_runtime_apply_for_semantic_combo", validate_visible_filter_toggle_runtime_apply_for_semantic_combo),
        ("visible_filter_toggle_runtime_open_failed_for_ui_checkbox", validate_visible_filter_toggle_runtime_open_failed_for_ui_checkbox),
        ("visible_filter_toggle_runtime_apply_for_standard_search_layout", validate_visible_filter_toggle_runtime_apply_for_standard_search_layout),
        ("visible_filter_toggle_runtime_apply_for_standard_search_checkbox_group", validate_visible_filter_toggle_runtime_apply_for_standard_search_checkbox_group),
        ("visible_filter_toggle_runtime_apply_for_standard_select_item", validate_visible_filter_toggle_runtime_apply_for_standard_select_item),
        ("visible_filter_toggle_runtime_apply_for_standard_col_item", validate_visible_filter_toggle_runtime_apply_for_standard_col_item),
        ("standard_layout_selector_priority_over_text_fallback", validate_standard_layout_selector_priority_over_text_fallback),
        ("image_layout_selector_priority_over_text_fallback", validate_image_layout_selector_priority_over_text_fallback),
        ("special_panel_candidate_runtime_apply", validate_special_panel_candidate_runtime_apply),
        ("special_panel_candidate_runtime_apply_on_image_result_layout", validate_special_panel_candidate_runtime_apply_on_image_result_layout),
        ("special_panel_candidate_runtime_apply_from_active_condition", validate_special_panel_candidate_runtime_apply_from_active_condition),
        ("special_panel_candidate_runtime_open_failed", validate_special_panel_candidate_runtime_open_failed),
        ("ali1688_query_filter_definition_contract", validate_ali1688_query_filter_definition_contract),
        ("ali1688_query_filter_param_merging", validate_ali1688_query_filter_param_merging),
        ("ali1688_query_filter_url_verification", validate_ali1688_query_filter_url_verification),
        ("query_filter_in_place_runtime_verification", validate_query_filter_in_place_runtime_verification),
        ("query_filter_multi_item_mixed_runtime_verification", validate_query_filter_multi_item_mixed_runtime_verification),
        ("detail_channel_sorting_contract", validate_detail_channel_sorting_contract),
        ("detail_sort_filter_ui_semantics_contract", validate_detail_sort_filter_ui_semantics_contract),
        ("detail_filter_conclusion_label_contract", validate_detail_filter_conclusion_label_contract),
        ("detail_filter_runtime_diagnostics_label_contract", validate_detail_filter_runtime_diagnostics_label_contract),
        ("detail_channel_filter_summary_contract", validate_detail_channel_filter_summary_contract),
        ("detail_source_filter_summary_contract", validate_detail_source_filter_summary_contract),
        ("task_channel_summary_contract", validate_task_channel_summary_contract),
        ("ali1688_list_metrics_extraction_contract", validate_ali1688_list_metrics_extraction_contract),
        ("query_filter_repeated_query_param_verification", validate_query_filter_repeated_query_param_verification),
        ("query_filter_navigation_failed_runtime_projection", validate_query_filter_navigation_failed_runtime_projection),
        ("runtime_filter_snapshot_audit_file_contract", validate_runtime_filter_snapshot_audit_file_contract),
        ("full_pipeline_runtime_filter_audit_precedence", validate_full_pipeline_runtime_filter_audit_precedence),
        ("runtime_audit_evidence_classifier_contract", validate_runtime_audit_evidence_classifier_contract),
        ("semantic_dependency_pair_runtime_closure", validate_semantic_dependency_pair_runtime_closure),
        ("runtime_audit_batch_report_contract", validate_runtime_audit_batch_report_contract),
        ("runtime_audit_gate_report_contract", validate_runtime_audit_gate_report_contract),
        ("runtime_audit_required_filters_from_config_contract", validate_runtime_audit_required_filters_from_config_contract),
        ("runtime_audit_todo_report_cli_contract", validate_runtime_audit_todo_report_cli_contract),
    ]
    results = []
    for name, validator in validators:
        validator()
        results.append({"name": name, "status": "passed"})

    print(json.dumps({"status": "passed", "checks": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
