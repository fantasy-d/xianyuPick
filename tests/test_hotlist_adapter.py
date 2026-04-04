import importlib.util
import json
import sys
from pathlib import Path

from xianyu_tools.hotlist_adapter import FixtureHotlistAdapter


def test_fixture_hotlist_adapter_loads_hot_items(tmp_path) -> None:
    fixture_file = tmp_path / "hot_items.json"
    fixture_file.write_text(
        json.dumps(
            {
                "hot_items": [
                    {
                        "hot_item_id": "pdd-001",
                        "platform": "pinduoduo",
                        "title": "爆款耳机",
                        "price": 29.9,
                        "sales_volume": 9000,
                        "hot_score": 95,
                        "item_url": "https://example.com/pdd-001",
                        "source_snapshot": {"rank": 1},
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    adapter = FixtureHotlistAdapter.from_file(fixture_file)
    items = adapter.list_hot_items(limit=5)
    assert len(items) == 1
    assert items[0].hot_item_id == "pdd-001"
    assert items[0].platform == "pinduoduo"
    assert items[0].sales_volume == 9000
    assert items[0].metadata["rank"] == 1


def test_fixture_hotlist_adapter_filters_by_platform(tmp_path) -> None:
    fixture_file = tmp_path / "hot_items.json"
    fixture_file.write_text(
        json.dumps(
            [
                {"hot_item_id": "pdd-001", "platform": "pinduoduo", "title": "A", "price": 10},
                {"hot_item_id": "jd-001", "platform": "jd", "title": "B", "price": 20},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    adapter = FixtureHotlistAdapter.from_file(fixture_file)
    items = adapter.list_hot_items(platform="jd", limit=5)
    assert len(items) == 1
    assert items[0].hot_item_id == "jd-001"


def test_run_hotlist_scan_outputs_hot_items_bundle(monkeypatch, capsys, tmp_path) -> None:
    script_path = Path("/Users/mac/PycharmProjects/mytools/xianyu-tools/scripts/run_hotlist_scan.py")
    spec = importlib.util.spec_from_file_location("run_hotlist_scan_script", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    fixture_file = tmp_path / "hot_items.json"
    fixture_file.write_text(
        json.dumps(
            {"hot_items": [{"hot_item_id": "tb-001", "platform": "taobao", "title": "爆品", "price": 19.9}]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_hotlist_scan.py", "--fixture-file", str(fixture_file), "--limit", "5"],
    )
    assert module.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["hot_items"][0]["hot_item_id"] == "tb-001"
