import json

from xianyu_tools.xianyu_adapter.state_inspector import inspect_state_file


def test_inspect_state_file_reports_extension_snapshot(tmp_path) -> None:
    state_file = tmp_path / "xianyu_state.json"
    state_file.write_text(
        json.dumps(
            {
                "cookies": [{"name": "cna", "value": "abc", "domain": ".goofish.com", "path": "/"}],
                "origins": [],
                "headers": {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"},
                "env": {
                    "navigator": {"userAgent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)", "maxTouchPoints": 5},
                    "screen": {"width": 393, "height": 852, "devicePixelRatio": 3},
                    "intl": {"timeZone": "Asia/Shanghai"},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    report = inspect_state_file(state_file)
    assert report["exists"] is True
    assert report["cookie_count"] == 1
    assert report["has_headers"] is True
    assert report["context_overrides"]["is_mobile"] is True
    assert report["is_usable"] is True
    assert report["issues"] == []


def test_inspect_state_file_reports_missing_file(tmp_path) -> None:
    report = inspect_state_file(tmp_path / "missing.json")
    assert report["exists"] is False
    assert report["is_usable"] is False
    assert "state_file_missing" in report["issues"]


def test_inspect_state_file_reports_missing_cookies(tmp_path) -> None:
    state_file = tmp_path / "xianyu_state.json"
    state_file.write_text(
        json.dumps(
            {
                "cookies": [],
                "origins": [],
                "headers": {"User-Agent": "Mozilla/5.0"},
                "env": {"navigator": {"userAgent": "Mozilla/5.0"}, "screen": {}, "intl": {}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    report = inspect_state_file(state_file)
    assert report["is_usable"] is False
    assert "missing_cookies" in report["issues"]
