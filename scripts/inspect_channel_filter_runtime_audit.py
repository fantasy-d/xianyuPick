from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from xianyu_tools.config import settings
from xianyu_tools.channel_search_filters import get_ali1688_channel_search_filter_meta


AUDIT_FILE_NAME = "_channel_filter_runtime_snapshot.json"
AUDIT_REPORT_SCHEMA_VERSION = 1


def _load_audit_payload(path: Path) -> dict[str, Any]:
    resolved = path
    if path.is_dir():
        resolved = path / AUDIT_FILE_NAME
    if not resolved.exists():
        raise FileNotFoundError(f"runtime audit file not found: {resolved}")
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"runtime audit payload must be a JSON object: {resolved}")
    return payload


def discover_audit_files(path: Path, *, recursive: bool = False) -> list[Path]:
    if path.is_file():
        return [path] if path.name == AUDIT_FILE_NAME else []
    if not path.is_dir():
        return []
    direct = path / AUDIT_FILE_NAME
    if direct.exists():
        return [direct]
    if recursive:
        return sorted(item for item in path.rglob(AUDIT_FILE_NAME) if item.is_file())
    return []


def _truthy_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) and value else []


def _classify_filter_evidence(filter_key: str, meta: dict[str, Any]) -> dict[str, Any]:
    label = str(meta.get("label") or filter_key).strip() or filter_key
    mapping_type = str(meta.get("mapping_type") or "").strip()
    status = str(meta.get("status") or "").strip()
    reason = str(meta.get("reason") or "").strip()
    detail = dict(meta.get("verification_detail") or {})
    verification_mode = str(detail.get("verification_mode") or "").strip()
    result_signature_changed = detail.get("result_signature_changed") is True
    result_url_changed = detail.get("result_url_changed") is True
    selected_after = detail.get("panel_term_selected_after_action") is True
    selected_via_after = str(detail.get("panel_term_selected_via_after_action") or "").strip()
    active_condition_observed = selected_after and selected_via_after == "active_condition_text"
    semantic_conclusion = str(meta.get("semantic_conclusion") or detail.get("semantic_conclusion") or "").strip()
    special_panel_conclusion = str(meta.get("special_panel_conclusion") or detail.get("special_panel_conclusion") or "").strip()

    evidence_level = "not_verified"
    can_close_real_site_gap = False
    pending_reason = reason or "runtime_evidence_missing"

    if mapping_type == "query_candidate":
        matched_values = _truthy_list(detail.get("matched_values"))
        if status == "applied" and verification_mode == "post_navigation_url" and matched_values:
            evidence_level = "site_strong"
            can_close_real_site_gap = True
            pending_reason = ""
        elif status == "query_injected_pending_verification":
            evidence_level = "query_injected_pending_result_validation"
            pending_reason = reason or "query_filter_injected_pending_result_validation"
    elif mapping_type in {"ui_checkbox_candidate", "semantic_combo_candidate"}:
        if (
            mapping_type == "semantic_combo_candidate"
            and status == "applied"
            and verification_mode == "semantic_dependency_pair"
            and semantic_conclusion == "dependency_pair_strong_verified"
        ):
            evidence_level = "site_strong"
            can_close_real_site_gap = True
            pending_reason = ""
        elif status == "applied" and verification_mode == "dom_toggle_action" and (selected_after or result_url_changed) and (result_signature_changed or result_url_changed):
            evidence_level = "site_strong"
            can_close_real_site_gap = True
            pending_reason = ""
        elif status == "applied" and verification_mode == "dom_toggle_action" and selected_after:
            evidence_level = "action_applied_without_result_shift"
            pending_reason = "dom_action_selected_but_result_shift_not_observed"
        elif detail.get("entry_click_attempted") is True:
            evidence_level = "action_attempted_not_applied"
            pending_reason = reason or "dom_action_attempted_but_not_applied"
        elif detail.get("panel_term_visible_before_action") is True or detail.get("independent_ui_entry_observed") is True:
            evidence_level = "entry_observed_pending_action"
            pending_reason = reason or "entry_observed_pending_runtime_action"

        if mapping_type == "semantic_combo_candidate":
            if semantic_conclusion in {
                "independent_entry_result_shift_observed",
                "dependency_pair_strong_verified",
            } and can_close_real_site_gap:
                pending_reason = ""
            elif semantic_conclusion:
                can_close_real_site_gap = False
                if evidence_level == "site_strong":
                    evidence_level = "semantic_conclusion_requires_review"
                pending_reason = pending_reason or semantic_conclusion
    elif mapping_type == "special_panel_candidate":
        if (
            status == "applied"
            and verification_mode == "dom_panel_action"
            and (
                ((selected_after or result_url_changed) and (result_signature_changed or result_url_changed))
                or active_condition_observed
            )
        ):
            evidence_level = "site_strong"
            can_close_real_site_gap = True
            pending_reason = ""
        elif status == "applied" and verification_mode == "dom_panel_action" and selected_after:
            evidence_level = "panel_action_applied_without_result_shift"
            pending_reason = "panel_action_selected_but_result_shift_not_observed"
        elif detail.get("panel_trigger_clicked") is True or detail.get("entry_click_attempted") is True:
            evidence_level = "panel_action_attempted_not_applied"
            pending_reason = reason or "panel_action_attempted_but_not_applied"
        elif detail.get("entry_signal_detected") is True:
            evidence_level = "entry_signal_observed_pending_panel_action"
            pending_reason = reason or "entry_signal_detected_pending_panel_mapping"

        if special_panel_conclusion == "panel_action_result_shift_observed" and evidence_level == "site_strong":
            pending_reason = ""
        elif special_panel_conclusion and not can_close_real_site_gap:
            pending_reason = pending_reason or special_panel_conclusion

    return {
        "filter_key": filter_key,
        "label": label,
        "mapping_type": mapping_type,
        "status": status,
        "reason": reason,
        "verification_mode": verification_mode,
        "semantic_conclusion": semantic_conclusion,
        "special_panel_conclusion": special_panel_conclusion,
        "result_signature_changed": result_signature_changed,
        "result_url_changed": result_url_changed,
        "selected_after_action": selected_after,
        "selected_via_after_action": selected_via_after,
        "evidence_level": evidence_level,
        "can_close_real_site_gap": can_close_real_site_gap,
        "pending_reason": pending_reason,
    }


def build_runtime_audit_report(payload: dict[str, Any]) -> dict[str, Any]:
    snapshot = payload.get("snapshot") if isinstance(payload.get("snapshot"), dict) else payload
    normalized = settings.normalize_channel_search_filter_snapshot(snapshot)
    filter_status_map = dict(normalized.get("filter_status_map") or {})
    filters = [
        _classify_filter_evidence(key, dict(meta or {}))
        for key, meta in filter_status_map.items()
    ]
    strong_keys = [item["filter_key"] for item in filters if item["can_close_real_site_gap"]]
    pending = [
        {
            "filter_key": item["filter_key"],
            "evidence_level": item["evidence_level"],
            "pending_reason": item["pending_reason"],
        }
        for item in filters
        if not item["can_close_real_site_gap"]
    ]
    return {
        "report_type": "single_runtime_audit",
        "report_schema_version": AUDIT_REPORT_SCHEMA_VERSION,
        "channel_id": normalized.get("channel_id") or payload.get("channel_id") or "",
        "channel_type": normalized.get("channel_type") or payload.get("channel_type") or "",
        "audit_run_id": str(payload.get("audit_run_id") or "").strip(),
        "audit_generated_at_epoch": float(payload.get("audit_generated_at_epoch") or 0),
        "runtime_audit_stage": normalized.get("runtime_audit_stage") or payload.get("stage") or "",
        "mapping_stage": normalized.get("mapping_stage") or payload.get("mapping_stage") or "",
        "configured_enabled_filter_keys": normalized.get("configured_enabled_filter_keys") or [],
        "filter_labels": dict(normalized.get("filter_labels") or {}),
        "strong_evidence_filter_keys": strong_keys,
        "pending_filter_count": len(pending),
        "pending_filters": pending,
        "filters": filters,
    }


def build_runtime_audit_batch_report(
    paths: list[Path],
    *,
    recursive: bool = False,
    max_age_seconds: int | None = None,
    now_epoch: float | None = None,
    required_audit_run_id: str | None = None,
    latest_audit_run_only: bool = False,
    latest_audit_run_channel_id: str | None = None,
) -> dict[str, Any]:
    audit_files: list[Path] = []
    for path in paths:
        for audit_file in discover_audit_files(path, recursive=recursive):
            if audit_file not in audit_files:
                audit_files.append(audit_file)

    freshness_enabled = max_age_seconds is not None
    normalized_max_age_seconds = max(0, int(max_age_seconds or 0))
    normalized_now_epoch = float(now_epoch if now_epoch is not None else time.time())
    normalized_required_audit_run_id = str(required_audit_run_id or "").strip()
    normalized_latest_audit_run_channel_id = str(latest_audit_run_channel_id or "").strip()
    reports = []
    for audit_file in audit_files:
        report = build_runtime_audit_report(_load_audit_payload(audit_file))
        report["audit_file"] = str(audit_file)
        mtime_epoch = audit_file.stat().st_mtime
        age_seconds = max(0.0, normalized_now_epoch - mtime_epoch)
        is_fresh = not freshness_enabled or age_seconds <= normalized_max_age_seconds
        report["audit_file_mtime_epoch"] = mtime_epoch
        report["audit_file_age_seconds"] = age_seconds
        report["audit_file_fresh"] = is_fresh
        reports.append(report)

    latest_audit_run_report = None
    for report in reports:
        if (
            normalized_latest_audit_run_channel_id
            and str(report.get("channel_id") or "").strip() != normalized_latest_audit_run_channel_id
        ):
            continue
        audit_run_id = str(report.get("audit_run_id") or "").strip()
        if not audit_run_id:
            continue
        generated_epoch = float(report.get("audit_generated_at_epoch") or 0)
        sort_epoch = generated_epoch if generated_epoch > 0 else float(report.get("audit_file_mtime_epoch") or 0)
        current_sort_epoch = -1.0
        if latest_audit_run_report is not None:
            current_generated_epoch = float(latest_audit_run_report.get("audit_generated_at_epoch") or 0)
            current_sort_epoch = (
                current_generated_epoch
                if current_generated_epoch > 0
                else float(latest_audit_run_report.get("audit_file_mtime_epoch") or 0)
            )
        if latest_audit_run_report is None or sort_epoch > current_sort_epoch:
            latest_audit_run_report = report
    latest_audit_run_id = str(dict(latest_audit_run_report or {}).get("audit_run_id") or "").strip()
    latest_audit_file = str(dict(latest_audit_run_report or {}).get("audit_file") or "").strip()
    latest_audit_generated_at_epoch = float(dict(latest_audit_run_report or {}).get("audit_generated_at_epoch") or 0)
    if latest_audit_run_only and not normalized_required_audit_run_id:
        normalized_required_audit_run_id = latest_audit_run_id
    for report in reports:
        audit_run_id = str(report.get("audit_run_id") or "").strip()
        if latest_audit_run_only and not normalized_required_audit_run_id:
            audit_run_id_matched = False
        else:
            audit_run_id_matched = not normalized_required_audit_run_id or audit_run_id == normalized_required_audit_run_id
        report["audit_run_id_matched"] = audit_run_id_matched

    strong_filter_keys: list[str] = []
    strong_filter_keys_by_channel: dict[str, list[str]] = {}
    filter_labels: dict[str, str] = {}
    pending_filters: list[dict[str, Any]] = []
    pending_filters_by_channel: dict[str, list[dict[str, Any]]] = {}
    for report in reports:
        channel_id = str(report.get("channel_id") or "").strip()
        for key, label in dict(report.get("filter_labels") or {}).items():
            normalized_key = str(key or "").strip()
            normalized_label = str(label or "").strip()
            if normalized_key and normalized_label and normalized_key not in filter_labels:
                filter_labels[normalized_key] = normalized_label
        if channel_id and channel_id not in strong_filter_keys_by_channel:
            strong_filter_keys_by_channel[channel_id] = []
        if channel_id and channel_id not in pending_filters_by_channel:
            pending_filters_by_channel[channel_id] = []
        if report.get("audit_file_fresh") is False:
            continue
        if report.get("audit_run_id_matched") is False:
            continue
        for key in report.get("strong_evidence_filter_keys") or []:
            if key not in strong_filter_keys:
                strong_filter_keys.append(key)
            if channel_id and key not in strong_filter_keys_by_channel[channel_id]:
                strong_filter_keys_by_channel[channel_id].append(key)
        for item in report.get("pending_filters") or []:
            pending_item = dict(item)
            pending_item["audit_file"] = report.get("audit_file") or ""
            pending_item["channel_id"] = channel_id
            if pending_item not in pending_filters:
                pending_filters.append(pending_item)
            if channel_id:
                channel_pending_item = dict(item)
                channel_pending_item["audit_file"] = report.get("audit_file") or ""
                if channel_pending_item not in pending_filters_by_channel[channel_id]:
                    pending_filters_by_channel[channel_id].append(channel_pending_item)

    return {
        "report_type": "runtime_audit_batch",
        "report_schema_version": AUDIT_REPORT_SCHEMA_VERSION,
        "audit_file_count": len(audit_files),
        "fresh_audit_file_count": len([report for report in reports if report.get("audit_file_fresh") is not False]),
        "stale_audit_file_count": len([report for report in reports if report.get("audit_file_fresh") is False]),
        "stale_audit_files": [
            str(report.get("audit_file") or "")
            for report in reports
            if report.get("audit_file_fresh") is False
        ],
        "required_audit_run_id": normalized_required_audit_run_id,
        "latest_audit_run_only": latest_audit_run_only,
        "latest_audit_run_channel_id": normalized_latest_audit_run_channel_id,
        "latest_audit_run_id": latest_audit_run_id,
        "latest_audit_run_available": bool(latest_audit_run_id),
        "latest_audit_file": latest_audit_file,
        "latest_audit_generated_at_epoch": latest_audit_generated_at_epoch,
        "matched_audit_run_file_count": len([
            report for report in reports
            if report.get("audit_run_id_matched") is not False
        ]),
        "matched_stale_audit_run_file_count": len([
            report for report in reports
            if report.get("audit_run_id_matched") is not False
            and report.get("audit_file_fresh") is False
        ]),
        "unmatched_audit_run_file_count": len([
            report for report in reports
            if report.get("audit_run_id_matched") is False
        ]),
        "unmatched_audit_run_files": [
            str(report.get("audit_file") or "")
            for report in reports
            if report.get("audit_run_id_matched") is False
        ],
        "audit_run_ids": [
            str(report.get("audit_run_id") or "")
            for report in reports
            if str(report.get("audit_run_id") or "").strip()
        ],
        "audit_generated_at_epochs": [
            float(report.get("audit_generated_at_epoch") or 0)
            for report in reports
            if float(report.get("audit_generated_at_epoch") or 0) > 0
        ],
        "freshness_check": {
            "enabled": freshness_enabled,
            "max_age_seconds": normalized_max_age_seconds if freshness_enabled else 0,
            "now_epoch": normalized_now_epoch if freshness_enabled else 0,
        },
        "strong_evidence_filter_keys": strong_filter_keys,
        "strong_evidence_filter_keys_by_channel": strong_filter_keys_by_channel,
        "filter_labels": filter_labels,
        "pending_filter_count": len(pending_filters),
        "pending_filters": pending_filters,
        "pending_filters_by_channel": pending_filters_by_channel,
        "reports": reports,
    }


def build_runtime_audit_gate_report(
    batch_report: dict[str, Any],
    *,
    required_filter_keys: list[str] | None = None,
    required_channel_id: str | None = None,
    required_filter_source: str | None = None,
    required_filter_config_channel_id: str | None = None,
) -> dict[str, Any]:
    required_keys = []
    for key in required_filter_keys or []:
        normalized = str(key or "").strip()
        if normalized and normalized not in required_keys:
            required_keys.append(normalized)
    scoped_channel_id = str(required_channel_id or "").strip()
    normalized_required_filter_source = str(required_filter_source or "manual").strip() or "manual"
    normalized_config_channel_id = str(required_filter_config_channel_id or "").strip()
    normalized_required_audit_run_id = str(batch_report.get("required_audit_run_id") or "").strip()
    scoped_reports = []
    if scoped_channel_id:
        scoped_reports = [
            dict(report or {})
            for report in batch_report.get("reports") or []
            if str(dict(report or {}).get("channel_id") or "").strip() == scoped_channel_id
        ]
        strong_source = []
        freshness_enabled = bool(dict(batch_report.get("freshness_check") or {}).get("enabled"))
        eligible_scoped_reports = [
            report for report in scoped_reports
            if (not freshness_enabled or report.get("audit_file_fresh") is not False)
            and report.get("audit_run_id_matched") is not False
        ]
        for report in eligible_scoped_reports:
            strong_source.extend(report.get("strong_evidence_filter_keys") or [])
        audit_file_count = len(eligible_scoped_reports)
        total_scoped_audit_file_count = len(scoped_reports)
        stale_scoped_audit_file_count = len([
            report for report in scoped_reports
            if freshness_enabled and report.get("audit_file_fresh") is False
        ])
        matched_scoped_audit_run_file_count = len([
            report for report in scoped_reports
            if report.get("audit_run_id_matched") is not False
        ])
        matched_stale_scoped_audit_run_file_count = len([
            report for report in scoped_reports
            if report.get("audit_run_id_matched") is not False
            and freshness_enabled
            and report.get("audit_file_fresh") is False
        ])
        unmatched_scoped_audit_run_file_count = len([
            report for report in scoped_reports
            if report.get("audit_run_id_matched") is False
        ])
    else:
        strong_source = batch_report.get("strong_evidence_filter_keys") or []
        freshness_enabled = bool(dict(batch_report.get("freshness_check") or {}).get("enabled"))
        audit_file_count = len([
            report for report in batch_report.get("reports") or []
            if (not freshness_enabled or dict(report or {}).get("audit_file_fresh") is not False)
            and dict(report or {}).get("audit_run_id_matched") is not False
        ])
        total_scoped_audit_file_count = int(batch_report.get("audit_file_count") or 0)
        stale_scoped_audit_file_count = int(batch_report.get("stale_audit_file_count") or 0)
        matched_scoped_audit_run_file_count = int(batch_report.get("matched_audit_run_file_count") or 0)
        matched_stale_scoped_audit_run_file_count = int(batch_report.get("matched_stale_audit_run_file_count") or 0)
        unmatched_scoped_audit_run_file_count = int(batch_report.get("unmatched_audit_run_file_count") or 0)
    label_source: dict[str, str] = dict(batch_report.get("filter_labels") or {})
    for report in scoped_reports:
        for key, label in dict(report.get("filter_labels") or {}).items():
            normalized_key = str(key or "").strip()
            normalized_label = str(label or "").strip()
            if normalized_key and normalized_label:
                label_source[normalized_key] = normalized_label
    def label_for_key(key: str) -> str:
        normalized_key = str(key or "").strip()
        configured_label = str(label_source.get(normalized_key) or "").strip()
        if configured_label:
            return configured_label
        shared_meta = get_ali1688_channel_search_filter_meta(normalized_key)
        return str(shared_meta.get("label") or normalized_key).strip() or normalized_key
    strong_keys = []
    for key in strong_source:
        normalized = str(key or "").strip()
        if normalized and normalized not in strong_keys:
            strong_keys.append(normalized)
    missing = [key for key in required_keys if key not in strong_keys]
    if scoped_channel_id:
        pending_source = list((batch_report.get("pending_filters_by_channel") or {}).get(scoped_channel_id) or [])
    else:
        pending_source = list(batch_report.get("pending_filters") or [])
    missing_diagnostics = []
    for key in missing:
        pending_matches = [
            {
                "evidence_level": str(dict(item or {}).get("evidence_level") or "").strip(),
                "pending_reason": str(dict(item or {}).get("pending_reason") or "").strip(),
                "audit_file": str(dict(item or {}).get("audit_file") or "").strip(),
                "channel_id": str(dict(item or {}).get("channel_id") or scoped_channel_id or "").strip(),
            }
            for item in pending_source
            if str(dict(item or {}).get("filter_key") or "").strip() == key
        ]
        missing_diagnostics.append(
            {
                "filter_key": key,
                "label": label_for_key(key),
                "diagnosis": "pending_without_strong_evidence" if pending_matches else "not_observed_in_audit",
                "pending_matches": pending_matches,
            }
        )
    diagnostics_by_key = {
        str(item.get("filter_key") or "").strip(): dict(item)
        for item in missing_diagnostics
        if str(item.get("filter_key") or "").strip()
    }
    required_status_map = {}
    for key in required_keys:
        if key in strong_keys:
            required_status_map[key] = {
                "label": label_for_key(key),
                "status": "strong",
                "diagnosis": "",
                "pending_matches": [],
            }
        else:
            diagnostic = diagnostics_by_key.get(key) or {}
            required_status_map[key] = {
                "label": label_for_key(key),
                "status": "pending" if diagnostic.get("diagnosis") == "pending_without_strong_evidence" else "missing",
                "diagnosis": str(diagnostic.get("diagnosis") or "not_observed_in_audit"),
                "pending_matches": list(diagnostic.get("pending_matches") or []),
            }
    required_status_counts = {"strong": 0, "pending": 0, "missing": 0}
    required_next_actions = []
    for key, status_item in required_status_map.items():
        status = str(status_item.get("status") or "missing").strip()
        if status not in required_status_counts:
            required_status_counts[status] = 0
        required_status_counts[status] += 1
        if status == "strong":
            action = "none"
            reason = "strong_real_site_evidence_observed"
        elif status == "pending":
            action = "inspect_pending_audit_file"
            reason = str(status_item.get("diagnosis") or "pending_without_strong_evidence")
        else:
            action = "run_real_crawl_and_generate_audit"
            reason = str(status_item.get("diagnosis") or "not_observed_in_audit")
        required_next_actions.append(
            {
                "filter_key": key,
                "label": label_for_key(key),
                "status": status,
                "action": action,
                "reason": reason,
            }
        )
    failure_reasons = []
    if not required_keys:
        failure_reasons.append("required_filters_empty")
    if audit_file_count <= 0:
        if (
            freshness_enabled
            and normalized_required_audit_run_id
            and matched_scoped_audit_run_file_count > 0
            and matched_stale_scoped_audit_run_file_count == matched_scoped_audit_run_file_count
        ):
            failure_reasons.append("scoped_audit_run_files_stale" if scoped_channel_id else "audit_run_files_stale")
        elif freshness_enabled and total_scoped_audit_file_count > 0 and stale_scoped_audit_file_count == total_scoped_audit_file_count:
            failure_reasons.append("scoped_audit_files_stale" if scoped_channel_id else "stale_audit_files_only")
        elif batch_report.get("latest_audit_run_only") is True and total_scoped_audit_file_count > 0 and not str(batch_report.get("latest_audit_run_id") or "").strip():
            failure_reasons.append("latest_audit_run_id_missing")
        elif normalized_required_audit_run_id and total_scoped_audit_file_count > 0 and unmatched_scoped_audit_run_file_count == total_scoped_audit_file_count:
            failure_reasons.append("scoped_audit_run_id_not_found" if scoped_channel_id else "audit_run_id_not_found")
        else:
            failure_reasons.append("scoped_audit_files_empty" if scoped_channel_id else "audit_files_empty")
    if missing:
        failure_reasons.append("missing_strong_evidence")
    passed = bool(required_keys) and not missing and audit_file_count > 0
    strong_required_filter_keys = [
        key for key, item in required_status_map.items()
        if str(dict(item or {}).get("status") or "").strip() == "strong"
    ]
    pending_required_filter_keys = [
        key for key, item in required_status_map.items()
        if str(dict(item or {}).get("status") or "").strip() == "pending"
    ]
    missing_required_filter_keys = [
        key for key, item in required_status_map.items()
        if str(dict(item or {}).get("status") or "").strip() == "missing"
    ]
    closure_summary = {
        "can_close_required_filter_gaps": passed,
        "closure_blockers": failure_reasons,
        "strong_required_filter_keys": strong_required_filter_keys,
        "pending_required_filter_keys": pending_required_filter_keys,
        "missing_required_filter_keys": missing_required_filter_keys,
    }
    required_filter_gap_todos = []
    for item in required_next_actions:
        action = str(dict(item or {}).get("action") or "").strip()
        if not action or action == "none":
            continue
        filter_key = str(dict(item or {}).get("filter_key") or "").strip()
        status_item = dict(required_status_map.get(filter_key) or {})
        pending_matches = list(status_item.get("pending_matches") or [])
        required_filter_gap_todos.append(
            {
                "filter_key": filter_key,
                "label": label_for_key(filter_key),
                "status": str(dict(item or {}).get("status") or "").strip(),
                "required_channel_id": scoped_channel_id,
                "action": action,
                "reason": str(dict(item or {}).get("reason") or "").strip(),
                "blocking_reasons": list(failure_reasons),
                "pending_audit_files": [
                    str(dict(match or {}).get("audit_file") or "").strip()
                    for match in pending_matches
                    if str(dict(match or {}).get("audit_file") or "").strip()
                ],
            }
        )
    return {
        **batch_report,
        "report_type": "runtime_audit_gate",
        "report_schema_version": AUDIT_REPORT_SCHEMA_VERSION,
        "required_channel_id": scoped_channel_id,
        "required_filter_source": normalized_required_filter_source,
        "required_filter_config_channel_id": normalized_config_channel_id,
        "scoped_audit_file_count": audit_file_count,
        "scoped_total_audit_file_count": total_scoped_audit_file_count,
        "scoped_stale_audit_file_count": stale_scoped_audit_file_count,
        "scoped_matched_audit_run_file_count": matched_scoped_audit_run_file_count,
        "scoped_matched_stale_audit_run_file_count": matched_stale_scoped_audit_run_file_count,
        "scoped_unmatched_audit_run_file_count": unmatched_scoped_audit_run_file_count,
        "scoped_strong_evidence_filter_keys": strong_keys,
        "required_filter_keys": required_keys,
        "required_filter_labels": {key: label_for_key(key) for key in required_keys},
        "missing_strong_filter_keys": missing,
        "missing_strong_filter_labels": {key: label_for_key(key) for key in missing},
        "missing_filter_diagnostics": missing_diagnostics,
        "required_filter_status_map": required_status_map,
        "required_filter_status_counts": required_status_counts,
        "required_filter_next_actions": required_next_actions,
        "gate_failure_reasons": failure_reasons,
        "can_close_required_filter_gaps": passed,
        "closure_blockers": failure_reasons,
        "closure_summary": closure_summary,
        "required_filter_gap_todos": required_filter_gap_todos,
        "passed": passed,
    }


def runtime_audit_gate_exit_code(gate_report: dict[str, Any], *, strict: bool = False) -> int:
    if not strict:
        return 0
    return 0 if gate_report.get("passed") is True else 1


def build_runtime_audit_todo_report(gate_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "report_type": "runtime_audit_gate_todos",
        "report_schema_version": AUDIT_REPORT_SCHEMA_VERSION,
        "passed": gate_report.get("passed") is True,
        "can_close_required_filter_gaps": gate_report.get("can_close_required_filter_gaps") is True,
        "required_channel_id": str(gate_report.get("required_channel_id") or "").strip(),
        "required_filter_source": str(gate_report.get("required_filter_source") or "").strip(),
        "required_filter_config_channel_id": str(gate_report.get("required_filter_config_channel_id") or "").strip(),
        "required_filter_keys": list(gate_report.get("required_filter_keys") or []),
        "required_filter_labels": dict(gate_report.get("required_filter_labels") or {}),
        "closure_blockers": list(gate_report.get("closure_blockers") or []),
        "freshness_check": dict(gate_report.get("freshness_check") or {}),
        "fresh_audit_file_count": int(gate_report.get("fresh_audit_file_count") or 0),
        "stale_audit_file_count": int(gate_report.get("stale_audit_file_count") or 0),
        "stale_audit_files": list(gate_report.get("stale_audit_files") or []),
        "required_audit_run_id": str(gate_report.get("required_audit_run_id") or "").strip(),
        "latest_audit_run_only": gate_report.get("latest_audit_run_only") is True,
        "latest_audit_run_channel_id": str(gate_report.get("latest_audit_run_channel_id") or "").strip(),
        "latest_audit_run_id": str(gate_report.get("latest_audit_run_id") or "").strip(),
        "latest_audit_run_available": gate_report.get("latest_audit_run_available") is True,
        "latest_audit_file": str(gate_report.get("latest_audit_file") or "").strip(),
        "latest_audit_generated_at_epoch": float(gate_report.get("latest_audit_generated_at_epoch") or 0),
        "matched_audit_run_file_count": int(gate_report.get("matched_audit_run_file_count") or 0),
        "matched_stale_audit_run_file_count": int(gate_report.get("matched_stale_audit_run_file_count") or 0),
        "unmatched_audit_run_file_count": int(gate_report.get("unmatched_audit_run_file_count") or 0),
        "unmatched_audit_run_files": list(gate_report.get("unmatched_audit_run_files") or []),
        "scoped_audit_file_count": int(gate_report.get("scoped_audit_file_count") or 0),
        "scoped_total_audit_file_count": int(gate_report.get("scoped_total_audit_file_count") or 0),
        "scoped_stale_audit_file_count": int(gate_report.get("scoped_stale_audit_file_count") or 0),
        "scoped_matched_audit_run_file_count": int(gate_report.get("scoped_matched_audit_run_file_count") or 0),
        "scoped_matched_stale_audit_run_file_count": int(gate_report.get("scoped_matched_stale_audit_run_file_count") or 0),
        "scoped_unmatched_audit_run_file_count": int(gate_report.get("scoped_unmatched_audit_run_file_count") or 0),
        "required_filter_gap_todos": list(gate_report.get("required_filter_gap_todos") or []),
    }


def load_required_filters_from_config(
    channel_id: str | None,
    *,
    crawl_cfg: dict[str, Any] | None = None,
    source_channels_cfg: dict[str, Any] | None = None,
) -> list[str]:
    snapshot = settings.get_channel_search_filter_snapshot(
        channel_id=channel_id,
        channel_type="ali1688",
        crawl_cfg=crawl_cfg,
        source_channels_cfg=source_channels_cfg,
    )
    return [
        str(key or "").strip()
        for key in snapshot.get("configured_enabled_filter_keys") or []
        if str(key or "").strip()
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect 1688 channel filter runtime audit evidence.")
    parser.add_argument("path", nargs="+", help="Output directory or _channel_filter_runtime_snapshot.json path")
    parser.add_argument("--recursive", action="store_true", help="Recursively scan directories for runtime audit files")
    parser.add_argument(
        "--required-filter",
        action="append",
        default=[],
        help="Filter key that must have strong real-site evidence. Can be repeated.",
    )
    parser.add_argument(
        "--require-configured-channel",
        default="",
        help="Load required filter keys from current crawl config for the given ali1688 channel_id.",
    )
    parser.add_argument(
        "--strict-exit",
        action="store_true",
        help="Exit with status 1 when a requested gate report does not pass.",
    )
    parser.add_argument(
        "--todo-report",
        action="store_true",
        help="When a gate report is requested, print only the actionable required-filter todo report.",
    )
    parser.add_argument(
        "--max-age-minutes",
        type=int,
        default=0,
        help="When positive, only fresh audit files within this many minutes can satisfy gate evidence.",
    )
    parser.add_argument(
        "--require-audit-run-id",
        default="",
        help="Only audit files from this audit_run_id can satisfy gate evidence.",
    )
    parser.add_argument(
        "--latest-audit-run",
        action="store_true",
        help="Only the latest discovered audit_run_id can satisfy gate evidence.",
    )
    args = parser.parse_args()
    if args.require_audit_run_id and args.latest_audit_run:
        parser.error("--latest-audit-run cannot be combined with --require-audit-run-id")
    paths = [Path(item) for item in args.path]
    required_filters = list(args.required_filter or [])
    gate_requested = bool(required_filters or args.require_configured_channel)
    if args.todo_report and not gate_requested:
        parser.error("--todo-report requires --required-filter or --require-configured-channel")
    required_filter_source = "manual"
    if args.require_configured_channel:
        required_filters.extend(load_required_filters_from_config(args.require_configured_channel))
        required_filter_source = "manual_and_config" if args.required_filter else "config"
    if len(paths) == 1 and not args.recursive and not gate_requested:
        payload = _load_audit_payload(paths[0])
        print(json.dumps(build_runtime_audit_report(payload), ensure_ascii=False, indent=2))
        return
    batch_report = build_runtime_audit_batch_report(
        paths,
        recursive=args.recursive,
        max_age_seconds=args.max_age_minutes * 60 if args.max_age_minutes > 0 else None,
        required_audit_run_id=args.require_audit_run_id,
        latest_audit_run_only=args.latest_audit_run,
        latest_audit_run_channel_id=args.require_configured_channel if args.latest_audit_run else "",
    )
    if gate_requested:
        gate_report = build_runtime_audit_gate_report(
            batch_report,
            required_filter_keys=required_filters,
            required_channel_id=args.require_configured_channel,
            required_filter_source=required_filter_source,
            required_filter_config_channel_id=args.require_configured_channel,
        )
        output_report = build_runtime_audit_todo_report(gate_report) if args.todo_report else gate_report
        print(json.dumps(output_report, ensure_ascii=False, indent=2))
        sys.exit(runtime_audit_gate_exit_code(gate_report, strict=args.strict_exit))
        return
    print(json.dumps(batch_report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
