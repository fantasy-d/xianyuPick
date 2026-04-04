import json

from xianyu_tools.xianyu_adapter.state_exporter import (
    PlaywrightStateExporter,
    StateExportConfig,
    build_snapshot,
    filter_env_data,
    filter_headers,
    normalize_cookies,
    prune_storage_entries,
)


def test_prune_storage_entries_matches_extension_limit() -> None:
    result = prune_storage_entries({"small": "ok", "big": "x" * 5000})
    assert result["data"] == {"small": "ok"}
    assert result["dropped"] == ["big"]


def test_filter_headers_keeps_extension_allow_list() -> None:
    headers = filter_headers({"User-Agent": "ua", "Cookie": "secret", "Accept-Language": "zh-CN"})
    assert headers == {"User-Agent": "ua", "Accept-Language": "zh-CN"}


def test_normalize_cookies_maps_same_site() -> None:
    cookies = normalize_cookies([{"name": "a", "value": "1", "sameSite": "no_restriction"}])
    assert cookies[0]["sameSite"] == "None"


def test_build_snapshot_uses_extension_shape() -> None:
    snapshot = build_snapshot(
        "https://www.goofish.com/",
        {
            "page": {"pageUrl": "https://www.goofish.com/"},
            "env": {"navigator": {"userAgent": "ua"}, "screen": {"width": 1}, "intl": {"timeZone": "Asia/Shanghai"}},
            "storage": {"local": {"a": "1"}, "session": {"b": "2"}},
        },
        {"User-Agent": "ua", "Cookie": "secret"},
        [{"name": "cna", "value": "abc", "sameSite": "lax"}],
    )
    assert snapshot["headers"] == {"User-Agent": "ua"}
    assert snapshot["storage"]["local"] == {"a": "1"}
    assert snapshot["cookies"][0]["sameSite"] == "Lax"


def test_filter_env_data_keeps_expected_fields() -> None:
    filtered = filter_env_data(
        {
            "navigator": {"userAgent": "ua", "vendor": "Google", "language": "zh-CN"},
            "screen": {"width": 393, "height": 852, "devicePixelRatio": 3},
            "intl": {"timeZone": "Asia/Shanghai", "locale": "zh-CN"},
        }
    )
    assert filtered["navigator"]["userAgent"] == "ua"
    assert "vendor" not in filtered["navigator"]
    assert filtered["screen"]["width"] == 393


def test_export_uses_persistent_profile_when_user_data_dir_provided(tmp_path) -> None:
    calls: dict[str, object] = {}

    class FakePage:
        url = "https://www.goofish.com/"

        async def goto(self, url: str, wait_until: str, timeout: int) -> None:
            calls["goto"] = {"url": url, "wait_until": wait_until, "timeout": timeout}

        def on(self, event: str, handler) -> None:
            return None

        def remove_listener(self, event: str, handler) -> None:
            return None

    class FakeContext:
        def __init__(self) -> None:
            self.pages = [FakePage()]

        async def cookies(self, page_url: str) -> list[dict]:
            calls["cookies_for"] = page_url
            return [{"name": "cna", "value": "abc", "sameSite": "lax"}]

        async def close(self) -> None:
            calls["context_closed"] = True

    class FakeChromium:
        async def launch_persistent_context(self, user_data_dir: str, **kwargs):
            calls["launch_persistent_context"] = {"user_data_dir": user_data_dir, "kwargs": kwargs}
            return FakeContext()

    class FakePlaywrightManager:
        async def __aenter__(self):
            return type("FakePlaywright", (), {"chromium": FakeChromium()})()

        async def __aexit__(self, exc_type, exc, tb):
            return None

    exporter = PlaywrightStateExporter(
        config=StateExportConfig(
            output_file=str(tmp_path / "xianyu_state.json"),
            user_data_dir="/tmp/chrome-user-data",
            profile_directory="Profile 2",
        ),
        async_playwright_factory=FakePlaywrightManager,
    )

    async def fake_capture_headers(page):
        return {"User-Agent": "ua"}

    async def fake_capture_page_data(page):
        return {
            "page": {"pageUrl": "https://www.goofish.com/"},
            "env": {"navigator": {"userAgent": "ua"}, "screen": {}, "intl": {}},
            "storage": {"local": {}, "session": {}},
        }

    exporter._capture_headers = fake_capture_headers
    exporter._capture_page_data = fake_capture_page_data

    snapshot = exporter.export()
    saved = json.loads((tmp_path / "xianyu_state.json").read_text(encoding="utf-8"))

    assert calls["launch_persistent_context"]["user_data_dir"] == "/tmp/chrome-user-data"
    launch_args = calls["launch_persistent_context"]["kwargs"]["args"]
    assert "--profile-directory=Profile 2" in launch_args
    assert "--disable-blink-features=AutomationControlled" in launch_args
    assert calls["cookies_for"] == "https://www.goofish.com/"
    assert calls["context_closed"] is True
    assert snapshot["headers"] == {"User-Agent": "ua"}
    assert saved["cookies"][0]["name"] == "cna"


def test_export_uses_cdp_browser_when_url_provided(tmp_path) -> None:
    calls: dict[str, object] = {}

    class FakePage:
        url = "https://www.goofish.com/"

        async def goto(self, url: str, wait_until: str, timeout: int) -> None:
            calls["goto"] = {"url": url, "wait_until": wait_until, "timeout": timeout}

        def on(self, event: str, handler) -> None:
            return None

        def remove_listener(self, event: str, handler) -> None:
            return None

    class FakeContext:
        def __init__(self) -> None:
            self.pages = [FakePage()]

        async def cookies(self, page_url: str) -> list[dict]:
            calls["cookies_for"] = page_url
            return [{"name": "unb", "value": "123", "sameSite": "strict"}]

    class FakeBrowser:
        def __init__(self) -> None:
            self.contexts = [FakeContext()]

        async def close(self) -> None:
            calls["browser_closed"] = True

    class FakeChromium:
        async def connect_over_cdp(self, cdp_url: str):
            calls["cdp_url"] = cdp_url
            return FakeBrowser()

    class FakePlaywrightManager:
        async def __aenter__(self):
            return type("FakePlaywright", (), {"chromium": FakeChromium()})()

        async def __aexit__(self, exc_type, exc, tb):
            return None

    exporter = PlaywrightStateExporter(
        config=StateExportConfig(
            output_file=str(tmp_path / "xianyu_state.json"),
            cdp_url="http://127.0.0.1:9222",
        ),
        async_playwright_factory=FakePlaywrightManager,
    )

    async def fake_capture_headers(page):
        return {"User-Agent": "ua"}

    async def fake_capture_page_data(page):
        return {
            "page": {"pageUrl": "https://www.goofish.com/"},
            "env": {"navigator": {"userAgent": "ua"}, "screen": {}, "intl": {}},
            "storage": {"local": {}, "session": {}},
        }

    exporter._capture_headers = fake_capture_headers
    exporter._capture_page_data = fake_capture_page_data

    snapshot = exporter.export()

    assert calls["cdp_url"] == "http://127.0.0.1:9222"
    assert calls["cookies_for"] == "https://www.goofish.com/"
    assert calls["browser_closed"] is True
    assert snapshot["cookies"][0]["sameSite"] == "Strict"
