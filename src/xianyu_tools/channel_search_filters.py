from __future__ import annotations

from typing import Any

ALI1688_CHANNEL_SEARCH_FILTER_DEFINITIONS: dict[str, dict[str, Any]] = {
    "rapid_invoice": {
        "mapping_type": "query_candidate",
        "group": "service_capability",
        "query_param": "complexTags",
        "query_values": ["1013"],
        "verify_alias_params": ["complexTags"],
    },
    "selected_distributors": {
        "mapping_type": "ui_checkbox_candidate",
        "group": "distribution_capability",
        "probe_terms": ["分销严选"],
        "verification_entry": "search_result_checkbox",
        "mapping_hint": "当前依赖 1688 搜索结果页筛选区 checkbox，需先确认 selector 稳定后再验证真实生效。",
    },
    "single_piece_drop_shipping": {
        "mapping_type": "query_candidate",
        "group": "distribution_capability",
        "query_param": "filtOfferTags",
        "query_values": ["1988226", "98306", "235906"],
        "verify_alias_params": ["filtOfferTags", "offerTags"],
    },
    "seven_day_return": {
        "mapping_type": "ui_checkbox_candidate",
        "group": "after_sales_capability",
        "probe_terms": ["7天无理由"],
        "verification_entry": "search_result_checkbox",
        "mapping_hint": "当前依赖结果页售后保障筛选 checkbox，需观察选中态与结果变化是否稳定。",
    },
    "single_piece_free_shipping": {
        "mapping_type": "semantic_combo_candidate",
        "group": "distribution_capability",
        "probe_terms": ["1件代发包邮"],
        "semantic_dependencies": ["single_piece_drop_shipping", "free_shipping"],
        "verification_entry": "search_result_semantic_combo",
        "mapping_hint": "需先验证是否等价于“一件代发 + 包邮”的组合语义，再决定是否保留独立映射。",
    },
    "free_shipping": {
        "mapping_type": "query_candidate",
        "group": "service_capability",
        "query_param": "freeShipping",
        "query_values": ["1"],
        "verify_alias_params": ["freeShipping"],
    },
    "freight_insurance_return": {
        "mapping_type": "query_candidate",
        "group": "after_sales_capability",
        "query_param": "complexTags",
        "query_values": ["1001"],
        "verify_alias_params": ["complexTags"],
    },
    "real_factory_verified": {
        "mapping_type": "ui_checkbox_candidate",
        "group": "qualification_capability",
        "probe_terms": ["真实工厂认证"],
        "verification_entry": "search_result_checkbox",
        "mapping_hint": "当前依赖结果页资质认证筛选 checkbox，需先完成稳定 selector 定位。",
    },
    "strength_verified": {
        "mapping_type": "ui_checkbox_candidate",
        "group": "qualification_capability",
        "probe_terms": ["实力认证"],
        "verification_entry": "search_result_checkbox",
        "mapping_hint": "当前依赖结果页资质认证筛选 checkbox，需验证勾选后是否存在稳定结果变化。",
    },
    "official_logistics": {
        "mapping_type": "query_candidate",
        "group": "service_capability",
        "query_param": "filtOfferTags",
        "query_values": ["2484802"],
        "verify_alias_params": ["filtOfferTags", "offerTags"],
    },
    "encrypted_waybill": {
        "mapping_type": "special_panel_candidate",
        "group": "service_capability",
        "probe_terms": ["密文面单"],
        "verification_entry": "config_filter_panel",
        "mapping_hint": "当前更像二级配置面板入口，需要先确认主搜索页能否稳定打开对应配置面板。",
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


def get_ali1688_channel_search_filter_meta(filter_key: str) -> dict[str, Any]:
    key = str(filter_key or "").strip()
    raw_meta = ALI1688_CHANNEL_SEARCH_FILTER_DEFINITIONS.get(key) or {}
    return {
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
        "verification_entry": str(raw_meta.get("verification_entry") or "").strip(),
        "mapping_hint": str(raw_meta.get("mapping_hint") or "").strip(),
        "probe_terms": [
            str(item).strip()
            for item in raw_meta.get("probe_terms") or []
            if str(item).strip()
        ],
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
