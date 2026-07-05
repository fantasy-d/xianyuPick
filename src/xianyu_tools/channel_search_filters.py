from __future__ import annotations

from typing import Any

ALI1688_CHANNEL_SEARCH_FILTER_DEFINITIONS: dict[str, dict[str, Any]] = {
    "rapid_invoice": {
        "label": "极速开票",
        "mapping_type": "query_candidate",
        "group": "service_capability",
        "query_param": "complexTags",
        "query_values": ["1013"],
        "verify_alias_params": ["complexTags"],
    },
    "selected_distributors": {
        "label": "分销严选",
        "mapping_type": "ui_checkbox_candidate",
        "group": "distribution_capability",
        "probe_terms": ["分销严选"],
        "verification_entry": "search_result_checkbox",
        "mapping_hint": "当前依赖 1688 搜索结果页筛选区 checkbox，需先确认 selector 稳定后再验证真实生效。",
    },
    "single_piece_drop_shipping": {
        "label": "一件代发",
        "mapping_type": "query_candidate",
        "group": "distribution_capability",
        "query_param": "filtOfferTags",
        "query_values": ["1988226", "98306", "235906"],
        "verify_alias_params": ["filtOfferTags", "offerTags"],
    },
    "seven_day_return": {
        "label": "7天无理由",
        "mapping_type": "ui_checkbox_candidate",
        "group": "after_sales_capability",
        "probe_terms": ["7天无理由"],
        "verification_entry": "search_result_checkbox",
        "mapping_hint": "当前依赖结果页售后保障筛选 checkbox，需观察选中态与结果变化是否稳定。",
    },
    "single_piece_free_shipping": {
        "label": "1件代发包邮",
        "mapping_type": "semantic_combo_candidate",
        "group": "distribution_capability",
        "probe_terms": ["1件代发包邮"],
        "semantic_dependencies": ["single_piece_drop_shipping", "free_shipping"],
        "verification_entry": "search_result_semantic_combo",
        "mapping_hint": "需先验证是否等价于“一件代发 + 包邮”的组合语义，再决定是否保留独立映射。",
    },
    "free_shipping": {
        "label": "包邮",
        "mapping_type": "query_candidate",
        "group": "service_capability",
        "query_param": "freeShipping",
        "query_values": ["1"],
        "verify_alias_params": ["freeShipping"],
    },
    "freight_insurance_return": {
        "label": "退货包运费",
        "mapping_type": "query_candidate",
        "group": "after_sales_capability",
        "query_param": "complexTags",
        "query_values": ["1001"],
        "verify_alias_params": ["complexTags"],
    },
    "real_factory_verified": {
        "label": "真实工厂认证",
        "mapping_type": "ui_checkbox_candidate",
        "group": "qualification_capability",
        "probe_terms": ["真实工厂认证"],
        "verification_entry": "search_result_checkbox",
        "mapping_hint": "当前依赖结果页资质认证筛选 checkbox，需先完成稳定 selector 定位。",
    },
    "strength_verified": {
        "label": "实力认证",
        "mapping_type": "ui_checkbox_candidate",
        "group": "qualification_capability",
        "probe_terms": ["实力认证"],
        "verification_entry": "search_result_checkbox",
        "mapping_hint": "当前依赖结果页资质认证筛选 checkbox，需验证勾选后是否存在稳定结果变化。",
    },
    "official_logistics": {
        "label": "官方物流",
        "mapping_type": "query_candidate",
        "group": "service_capability",
        "query_param": "filtOfferTags",
        "query_values": ["2484802"],
        "verify_alias_params": ["filtOfferTags", "offerTags"],
    },
    "encrypted_waybill": {
        "label": "密文面单",
        "mapping_type": "special_panel_candidate",
        "group": "service_capability",
        "is_configurable": False,
        "is_parent": True,
        "probe_terms": ["密文面单"],
        "verification_entry": "config_filter_panel",
        "mapping_hint": "密文面单是二级配置面板入口，本身不作为独立勾选项；需配置具体子选项。",
        "observation_scope": "result_page_text",
        "entry_signal_type": "text_term",
        "next_required_action": "panel_open_and_toggle",
    },
    "douyin_encrypted_waybill": {
        "label": "抖音面单",
        "mapping_type": "special_panel_candidate",
        "group": "service_capability",
        "parent_key": "encrypted_waybill",
        "parent_label": "密文面单",
        "probe_terms": ["密文面单", "抖音面单", "密文面单：抖音面单"],
        "verification_entry": "config_filter_panel",
        "mapping_hint": "1688 图搜页已选条件中会以“密文面单：抖音面单”形式出现，需按独立配置项纳入校验。",
        "observation_scope": "result_page_text",
        "entry_signal_type": "text_term",
        "next_required_action": "panel_open_and_toggle",
    },
}

ALI1688_QUERY_FILTER_KEY_ORDER = [
    "single_piece_drop_shipping",
    "official_logistics",
    "freight_insurance_return",
    "rapid_invoice",
    "free_shipping",
]


def get_ali1688_channel_search_filter_keys() -> list[str]:
    return list(ALI1688_CHANNEL_SEARCH_FILTER_DEFINITIONS.keys())


def get_ali1688_configurable_channel_search_filter_keys() -> list[str]:
    return [
        key
        for key in get_ali1688_channel_search_filter_keys()
        if get_ali1688_channel_search_filter_meta(key).get("is_configurable")
    ]


def get_ali1688_channel_search_filter_meta(filter_key: str) -> dict[str, Any]:
    key = str(filter_key or "").strip()
    raw_meta = ALI1688_CHANNEL_SEARCH_FILTER_DEFINITIONS.get(key) or {}
    return {
        "label": str(raw_meta.get("label") or key).strip() or key,
        "mapping_type": str(raw_meta.get("mapping_type") or "snapshot_only").strip() or "snapshot_only",
        "group": str(raw_meta.get("group") or "").strip(),
        "query_param": str(raw_meta.get("query_param") or "").strip(),
        "query_values": [
            str(item).strip()
            for item in raw_meta.get("query_values") or []
            if str(item).strip()
        ],
        "verify_alias_params": [
            str(item).strip()
            for item in raw_meta.get("verify_alias_params") or []
            if str(item).strip()
        ],
        "semantic_dependencies": [
            str(item).strip()
            for item in raw_meta.get("semantic_dependencies") or []
            if str(item).strip()
        ],
        "is_configurable": bool(raw_meta.get("is_configurable", True)),
        "is_parent": bool(raw_meta.get("is_parent", False)),
        "parent_key": str(raw_meta.get("parent_key") or "").strip(),
        "parent_label": str(raw_meta.get("parent_label") or "").strip(),
        "verification_entry": str(raw_meta.get("verification_entry") or "").strip(),
        "mapping_hint": str(raw_meta.get("mapping_hint") or "").strip(),
        "probe_terms": [
            str(item).strip()
            for item in raw_meta.get("probe_terms") or []
            if str(item).strip()
        ],
        "observation_scope": str(raw_meta.get("observation_scope") or "").strip(),
        "entry_signal_type": str(raw_meta.get("entry_signal_type") or "").strip(),
        "next_required_action": str(raw_meta.get("next_required_action") or "").strip(),
    }


def get_ali1688_query_filter_definitions() -> dict[str, dict[str, Any]]:
    definitions: dict[str, dict[str, Any]] = {}
    for key in ALI1688_QUERY_FILTER_KEY_ORDER:
        meta = get_ali1688_channel_search_filter_meta(key)
        if not meta.get("query_param") or not meta.get("query_values"):
            continue
        definitions[key] = {
            "mapping_type": meta["mapping_type"],
            "param": meta["query_param"],
            "values": list(meta["query_values"]),
            "verify_alias_params": list(meta["verify_alias_params"]) or [meta["query_param"]],
        }
    return definitions


def get_ali1688_query_mapped_filter_keys() -> list[str]:
    return list(get_ali1688_query_filter_definitions().keys())
