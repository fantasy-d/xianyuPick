from __future__ import annotations

import json

from xianyu_tools.config import settings

DEFAULT_SOURCE_CHANNEL_ACCOUNT = {
    "account_id": "ali1688-account-1",
    "label": "1688 账号 1",
    "enabled": True,
    "notes": "",
}

DEFAULT_SOURCE_CHANNEL = {
    "channel_id": "ali1688",
    "channel_type": "ali1688",
    "label": "1688 货源渠道",
    "enabled": True,
    "active_account_id": "ali1688-account-1",
    "active_account_ids": ["ali1688-account-1"],
    "accounts": [DEFAULT_SOURCE_CHANNEL_ACCOUNT],
}


def build_source_channel_account_runtime(channel_type: str | None, channel_id: str | None, account_id: str | None) -> dict:
    return settings.build_source_channel_account_runtime(channel_type, channel_id, account_id)


def normalize_active_source_account_ids(accounts: list[dict] | None, raw_ids, fallback_id: str | None = None) -> list[str]:
    account_ids = [item.get("account_id") for item in (accounts or []) if item.get("account_id")]
    requested_ids = raw_ids if isinstance(raw_ids, list) else [raw_ids] if raw_ids else []
    normalized_ids: list[str] = []
    for account_id in requested_ids:
        if account_id in account_ids and account_id not in normalized_ids:
            normalized_ids.append(account_id)

    if not normalized_ids and fallback_id in account_ids:
        normalized_ids.append(fallback_id)
    if not normalized_ids and account_ids:
        normalized_ids.append(account_ids[0])
    return normalized_ids


def normalize_source_channels_config(raw_cfg: dict | None) -> dict:
    raw_cfg = dict(raw_cfg or {})
    channels = raw_cfg.get("channels")
    normalized_channels = []

    if isinstance(channels, list) and channels:
        for c_index, channel in enumerate(channels, start=1):
            merged_channel = json.loads(json.dumps(DEFAULT_SOURCE_CHANNEL, ensure_ascii=False))
            incoming_channel = dict(channel or {})
            merged_channel.update({k: v for k, v in incoming_channel.items() if k != "accounts"})
            merged_channel["channel_id"] = merged_channel.get("channel_id") or f"channel-{c_index}"
            merged_channel["channel_type"] = merged_channel.get("channel_type") or "custom"
            merged_channel["label"] = merged_channel.get("label") or f"货源渠道 {c_index}"

            incoming_accounts = incoming_channel.get("accounts")
            normalized_accounts = []
            if isinstance(incoming_accounts, list) and incoming_accounts:
                for a_index, account in enumerate(incoming_accounts, start=1):
                    merged_account = json.loads(json.dumps(DEFAULT_SOURCE_CHANNEL_ACCOUNT, ensure_ascii=False))
                    incoming_account = dict(account or {})
                    merged_account.update(incoming_account)
                    merged_account["account_id"] = merged_account.get("account_id") or f"{merged_channel['channel_id']}-account-{a_index}"
                    merged_account["label"] = merged_account.get("label") or f"{merged_channel['label']} 账号 {a_index}"
                    merged_account["notes"] = merged_account.get("notes") or ""
                    runtime_cfg = build_source_channel_account_runtime(
                        merged_channel.get("channel_type"),
                        merged_channel.get("channel_id"),
                        merged_account.get("account_id"),
                    )
                    merged_account.update(runtime_cfg)
                    normalized_accounts.append(merged_account)
            else:
                fallback_account = json.loads(json.dumps(DEFAULT_SOURCE_CHANNEL_ACCOUNT, ensure_ascii=False))
                fallback_account["account_id"] = f"{merged_channel['channel_id']}-account-1"
                fallback_account["label"] = f"{merged_channel['label']} 账号 1"
                fallback_account.update(
                    build_source_channel_account_runtime(
                        merged_channel.get("channel_type"),
                        merged_channel.get("channel_id"),
                        fallback_account.get("account_id"),
                    )
                )
                normalized_accounts.append(fallback_account)

            merged_channel["accounts"] = normalized_accounts
            active_account_ids = normalize_active_source_account_ids(
                normalized_accounts,
                merged_channel.get("active_account_ids"),
                fallback_id=merged_channel.get("active_account_id"),
            )
            active_account_id = active_account_ids[0] if active_account_ids else normalized_accounts[0]["account_id"]
            merged_channel["active_account_ids"] = active_account_ids
            merged_channel["active_account_id"] = active_account_id
            normalized_channels.append(merged_channel)
    else:
        fallback_channel = json.loads(json.dumps(DEFAULT_SOURCE_CHANNEL, ensure_ascii=False))
        fallback_account = fallback_channel["accounts"][0]
        fallback_account.update(
            build_source_channel_account_runtime(
                fallback_channel.get("channel_type"),
                fallback_channel.get("channel_id"),
                fallback_account.get("account_id"),
            )
        )
        normalized_channels = [fallback_channel]

    active_channel_id = raw_cfg.get("active_channel_id") or normalized_channels[0]["channel_id"]
    if not any(item["channel_id"] == active_channel_id for item in normalized_channels):
        active_channel_id = normalized_channels[0]["channel_id"]
    return {"active_channel_id": active_channel_id, "channels": normalized_channels}


def strip_source_channel_runtime_fields(raw_cfg: dict | None) -> dict:
    normalized = normalize_source_channels_config(raw_cfg)
    cleaned_channels = []
    for channel in normalized.get("channels", []):
        active_account_ids = normalize_active_source_account_ids(
            channel.get("accounts") or [],
            channel.get("active_account_ids"),
            fallback_id=channel.get("active_account_id"),
        )
        cleaned_channel = {
            "channel_id": channel.get("channel_id"),
            "channel_type": channel.get("channel_type"),
            "label": channel.get("label"),
            "enabled": bool(channel.get("enabled", True)),
            "active_account_ids": active_account_ids,
            "active_account_id": active_account_ids[0] if active_account_ids else "",
            "accounts": [],
        }
        for account in channel.get("accounts", []):
            cleaned_channel["accounts"].append(
                {
                    "account_id": account.get("account_id"),
                    "label": account.get("label"),
                    "enabled": bool(account.get("enabled", True)),
                    "notes": account.get("notes") or "",
                }
            )
        cleaned_channels.append(cleaned_channel)
    return {
        "active_channel_id": normalized.get("active_channel_id"),
        "channels": cleaned_channels,
    }


def get_source_channel(raw_cfg: dict | None, channel_id: str | None = None) -> dict:
    normalized = normalize_source_channels_config(raw_cfg)
    target_id = channel_id or normalized.get("active_channel_id")
    selected = next((item for item in normalized["channels"] if item["channel_id"] == target_id), None)
    return selected or normalized["channels"][0]


def get_source_channel_account(raw_cfg: dict | None, channel_id: str | None = None, account_id: str | None = None) -> dict:
    channel = get_source_channel(raw_cfg, channel_id)
    accounts = channel.get("accounts") or []
    active_account_ids = normalize_active_source_account_ids(
        accounts,
        channel.get("active_account_ids"),
        fallback_id=channel.get("active_account_id"),
    )
    target_id = account_id or (active_account_ids[0] if active_account_ids else None) or channel.get("active_account_id")
    selected = next((item for item in accounts if item["account_id"] == target_id), None)
    return selected or (accounts[0] if accounts else {})
