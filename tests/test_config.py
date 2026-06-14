import json

from xianyu_tools.config import ConfigManager


def build_manager(tmp_path, payload):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    ConfigManager._instance = None
    ConfigManager._initialized = False
    ConfigManager._config_data = {}
    ConfigManager._db_cache = {}
    manager = ConfigManager()
    manager.config_file = config_path
    manager.load()
    manager._db_cache = {}
    manager._read_config_from_db = lambda key: None
    return manager


def test_get_openapi_config_returns_empty_when_multi_account_config_missing(tmp_path):
    manager = build_manager(
        tmp_path,
        {
            "openapi": {
                "base_url": "https://open.goofish.pro",
                "appid": "legacy-appid",
                "app_secret": "legacy-secret",
                "default_config": {"user_name": "legacy-user"},
            }
        },
    )

    cfg = manager.get_openapi_config()

    assert cfg == {}


def test_get_openapi_config_uses_active_multi_account(tmp_path):
    manager = build_manager(
        tmp_path,
        {
            "openapi": {
                "active_account_id": "acc-2",
                "accounts": [
                    {"id": "acc-1", "appid": "appid-1", "default_config": {"user_name": "user-1"}},
                    {"id": "acc-2", "appid": "appid-2", "default_config": {"user_name": "user-2"}},
                ],
            }
        },
    )

    cfg = manager.get_openapi_config()

    assert cfg["id"] == "acc-2"
    assert cfg["appid"] == "appid-2"
    assert cfg["default_config"]["user_name"] == "user-2"


def test_get_openapi_config_can_select_specific_account(tmp_path):
    manager = build_manager(
        tmp_path,
        {
            "openapi": {
                "active_account_id": "acc-1",
                "accounts": [
                    {"id": "acc-1", "appid": "appid-1"},
                    {"id": "acc-2", "appid": "appid-2", "default_config": {"province": 310000}},
                ],
            }
        },
    )

    cfg = manager.get_openapi_config("acc-2")

    assert cfg["id"] == "acc-2"
    assert cfg["appid"] == "appid-2"
    assert cfg["default_config"]["province"] == 310000
