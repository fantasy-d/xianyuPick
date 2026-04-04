import json
import importlib.util
import subprocess
import sys
from pathlib import Path


def test_search_script_exists() -> None:
    path = Path("/Users/mac/PycharmProjects/mytools/xianyu-tools/scripts/run_xianyu_search.py")
    assert path.exists()


def test_sourcing_script_exists() -> None:
    path = Path("/Users/mac/PycharmProjects/mytools/xianyu-tools/scripts/run_xianyu_sourcing.py")
    assert path.exists()


def test_workflow_script_exists() -> None:
    path = Path("/Users/mac/PycharmProjects/mytools/xianyu-tools/scripts/run_xianyu_workflow.py")
    assert path.exists()


def test_xianyu_hot_items_script_exists() -> None:
    path = Path("/Users/mac/PycharmProjects/mytools/xianyu-tools/scripts/run_xianyu_hot_items.py")
    assert path.exists()


def test_ali1688_result_url_script_exists() -> None:
    path = Path("/Users/mac/PycharmProjects/mytools/xianyu-tools/scripts/run_ali1688_result_url.py")
    assert path.exists()


def test_run_ali1688_slow_flow_script_exists() -> None:
    path = Path("/Users/mac/PycharmProjects/mytools/xianyu-tools/scripts/run_ali1688_slow_flow.py")
    assert path.exists()


def test_source_resolution_from_urls_script_exists() -> None:
    path = Path("/Users/mac/PycharmProjects/mytools/xianyu-tools/scripts/run_source_resolution_from_urls.py")
    assert path.exists()


def test_source_resolution_from_browser_runs_script_exists() -> None:
    path = Path("/Users/mac/PycharmProjects/mytools/xianyu-tools/scripts/run_source_resolution_from_browser_runs.py")
    assert path.exists()


def test_generate_ali1688_result_url_map_script_exists() -> None:
    path = Path("/Users/mac/PycharmProjects/mytools/xianyu-tools/scripts/generate_ali1688_result_url_map.py")
    assert path.exists()


def test_generate_ali1688_result_url_map_via_browser_script_exists() -> None:
    path = Path("/Users/mac/PycharmProjects/mytools/xianyu-tools/scripts/generate_ali1688_result_url_map_via_browser.py")
    assert path.exists()


def test_generate_ali1688_suggested_result_urls_script_exists() -> None:
    path = Path("/Users/mac/PycharmProjects/mytools/xianyu-tools/scripts/generate_ali1688_suggested_result_urls.py")
    assert path.exists()


def test_run_profit_analysis_script_exists() -> None:
    path = Path("/Users/mac/PycharmProjects/mytools/xianyu-tools/scripts/run_profit_analysis.py")
    assert path.exists()


def test_run_listing_candidates_script_exists() -> None:
    path = Path("/Users/mac/PycharmProjects/mytools/xianyu-tools/scripts/run_listing_candidates.py")
    assert path.exists()


def test_run_category_pipeline_from_urls_script_exists() -> None:
    path = Path("/Users/mac/PycharmProjects/mytools/xianyu-tools/scripts/run_category_pipeline_from_urls.py")
    assert path.exists()


def test_export_pipeline_excel_script_exists() -> None:
    path = Path("/Users/mac/PycharmProjects/mytools/xianyu-tools/scripts/export_pipeline_excel.py")
    assert path.exists()


def test_inspect_state_script_strict_exit_code(tmp_path) -> None:
    state_file = tmp_path / "xianyu_state.json"
    state_file.write_text(json.dumps({"cookies": [], "origins": []}), encoding="utf-8")
    repo_root = Path("/Users/mac/PycharmProjects/mytools/xianyu-tools")
    result = subprocess.run(
        [
            sys.executable,
            "scripts/inspect_xianyu_state.py",
            "--state-file",
            str(state_file),
            "--strict",
        ],
        cwd=repo_root,
        env={"PYTHONPATH": "src"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "missing_cookies" in result.stdout


def test_run_xianyu_search_outputs_bundle_shape(monkeypatch, capsys) -> None:
    script_path = Path("/Users/mac/PycharmProjects/mytools/xianyu-tools/scripts/run_xianyu_search.py")
    spec = importlib.util.spec_from_file_location("run_xianyu_search_script", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    from xianyu_tools.models import XianyuSearchItem

    class FakeAdapter:
        def search(self, keyword: str, page: int = 1):
            return [
                XianyuSearchItem(
                    item_id="xy-001",
                    title="iPhone 15 Pro Max",
                    price=5999.0,
                    item_url="https://www.goofish.com/item?id=xy-001",
                    area="上海",
                )
            ]

    class FakeFactory:
        @staticmethod
        def from_browser(config):
            return FakeAdapter()

    monkeypatch.setattr(module, "PlaywrightXianyuAdapter", FakeFactory)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_xianyu_search.py",
            "--keyword",
            "iphone",
            "--state-file",
            "./xianyu_state.json",
        ],
    )
    assert module.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["search_returned_count"] == 1
    assert output["search_items"][0]["item_id"] == "xy-001"


def test_run_xianyu_hot_items_passes_launch_args(monkeypatch, capsys) -> None:
    script_path = Path("/Users/mac/PycharmProjects/mytools/xianyu-tools/scripts/run_xianyu_hot_items.py")
    spec = importlib.util.spec_from_file_location("run_xianyu_hot_items_script", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    captured = {}

    class FakeAdapter:
        pass

    class FakeFactory:
        @staticmethod
        def from_browser(config):
            captured["config"] = config
            return FakeAdapter()

    def fake_scan(keyword, *, xianyu_adapter, top_n, max_pages, require_chaozan_fish_shop):
        return {"hot_items": [], "xianyu_market": {"category_keyword": keyword}}

    monkeypatch.setattr(module, "PlaywrightXianyuAdapter", FakeFactory)
    monkeypatch.setattr(module, "scan_xianyu_market", fake_scan)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_xianyu_hot_items.py",
            "--keyword",
            "升降桌",
            "--state-file",
            "./xianyu_state.json",
            "--launch-arg=--start-maximized",
        ],
    )
    assert module.main() == 0
    assert "--start-maximized" in captured["config"].launch_args
    output = json.loads(capsys.readouterr().out)
    assert output["xianyu_market"]["category_keyword"] == "升降桌"


def test_run_source_resolution_from_urls_outputs_summary(monkeypatch, capsys, tmp_path) -> None:
    script_path = Path(
        "/Users/mac/PycharmProjects/mytools/xianyu-tools/scripts/run_source_resolution_from_urls.py"
    )
    spec = importlib.util.spec_from_file_location("run_source_resolution_from_urls_script", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    hot_items_file = tmp_path / "hot_items.json"
    hot_items_file.write_text(
        json.dumps(
            {
                "hot_items": [
                    {
                        "hot_item_id": "xy-001",
                        "platform": "xianyu",
                        "title": "升降桌",
                        "price": 99.0,
                        "want_count": 123,
                        "item_url": "https://www.goofish.com/item?id=xy-001",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    result_url_map_file = tmp_path / "result_url_map.json"
    result_url_map_file.write_text(
        json.dumps({"xy-001": "https://s.1688.com/selloffer/offer_search.htm?keywords=test"}),
        encoding="utf-8",
    )

    def fake_resolve(hot_items, *, result_urls_by_hot_item_id, adapter=None, limit_per_item=10):
        assert hot_items[0].hot_item_id == "xy-001"
        assert result_urls_by_hot_item_id["xy-001"].startswith("https://s.1688.com/")
        assert limit_per_item == 8
        return {
            "source_resolution": [
                {
                    "hot_item_id": "xy-001",
                    "resolved": True,
                    "source_item_ids": ["src-001"],
                    "resolution_reason": "matched_source_items",
                    "source_query": "升降桌",
                    "metadata": {"candidate_count": 1},
                }
            ],
            "source_items": [
                {
                    "source_platform": "1688",
                    "source_item_id": "src-001",
                    "title": "升降桌厂家直发",
                    "price": 66.0,
                    "item_url": "https://detail.1688.com/offer/src-001.html",
                    "shop_name": "源头工厂",
                    "sales": 300,
                    "metadata": {"hot_item_id": "xy-001"},
                }
            ],
        }

    monkeypatch.setattr(module, "resolve_hot_items_to_ali1688_urls", fake_resolve)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_source_resolution_from_urls.py",
            "--hot-items-file",
            str(hot_items_file),
            "--result-url-map-file",
            str(result_url_map_file),
            "--limit-per-item",
            "8",
            "--summary-only",
        ],
    )
    assert module.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["hot_items"][0]["hot_item_id"] == "xy-001"
    assert output["hot_items"][0]["source_resolution"]["resolved"] is True
    assert output["hot_items"][0]["source_items"][0]["source_item_id"] == "src-001"


def test_generate_ali1688_result_url_map_writes_template(monkeypatch, capsys, tmp_path) -> None:
    script_path = Path(
        "/Users/mac/PycharmProjects/mytools/xianyu-tools/scripts/generate_ali1688_result_url_map.py"
    )
    spec = importlib.util.spec_from_file_location("generate_ali1688_result_url_map_script", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    hot_items_file = tmp_path / "hot_items.json"
    hot_items_file.write_text(
        json.dumps(
            {
                "hot_items": [
                    {"hot_item_id": "xy-001", "title": "升降桌"},
                    {"hot_item_id": "xy-002", "title": "电竞椅"},
                ]
            }
        ),
        encoding="utf-8",
    )
    output_file = tmp_path / "result_url_map.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate_ali1688_result_url_map.py",
            "--hot-items-file",
            str(hot_items_file),
            "--output-file",
            str(output_file),
        ],
    )
    assert module.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["count"] == 2
    result = json.loads(output_file.read_text(encoding="utf-8"))
    assert result == {"xy-001": "", "xy-002": ""}


def test_generate_ali1688_suggested_result_urls_writes_mapping(monkeypatch, capsys, tmp_path) -> None:
    script_path = Path(
        "/Users/mac/PycharmProjects/mytools/xianyu-tools/scripts/generate_ali1688_suggested_result_urls.py"
    )
    spec = importlib.util.spec_from_file_location("generate_ali1688_suggested_result_urls_script", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    hot_items_file = tmp_path / "hot_items.json"
    hot_items_file.write_text(
        json.dumps(
            {
                "hot_items": [
                    {"hot_item_id": "xy-001", "platform": "xianyu", "title": "升降桌", "price": 99.0},
                ]
            }
        ),
        encoding="utf-8",
    )
    output_file = tmp_path / "suggested_result_urls.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate_ali1688_suggested_result_urls.py",
            "--hot-items-file",
            str(hot_items_file),
            "--output-file",
            str(output_file),
        ],
    )
    assert module.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["count"] == 1
    result = json.loads(output_file.read_text(encoding="utf-8"))
    assert "xy-001" in result
    assert result["xy-001"].startswith("https://s.1688.com/selloffer/offer_search.htm?keywords=")


def test_run_profit_analysis_outputs_rows(monkeypatch, capsys, tmp_path) -> None:
    script_path = Path("/Users/mac/PycharmProjects/mytools/xianyu-tools/scripts/run_profit_analysis.py")
    spec = importlib.util.spec_from_file_location("run_profit_analysis_script", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    source_bundle_file = tmp_path / "source_bundle.json"
    source_bundle_file.write_text(
        json.dumps(
            {
                "hot_items": [
                    {
                        "hot_item_id": "xy-001",
                        "platform": "xianyu",
                        "title": "升降桌",
                        "price": 99.0,
                    }
                ],
                "source_items": [
                    {
                        "source_platform": "1688",
                        "source_item_id": "src-001",
                        "title": "升降桌工厂直发",
                        "price": 60.0,
                        "shipping_fee": 5.0,
                        "item_url": "https://detail.1688.com/offer/src-001.html",
                        "sales": 150,
                        "metadata": {"hot_item_id": "xy-001"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_profit_analysis.py",
            "--source-bundle-file",
            str(source_bundle_file),
        ],
    )
    assert module.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["profit_analysis"][0]["hot_item_id"] == "xy-001"
    assert output["profit_analysis"][0]["source_item_id"] == "src-001"


def test_run_listing_candidates_outputs_decisions(monkeypatch, capsys, tmp_path) -> None:
    script_path = Path("/Users/mac/PycharmProjects/mytools/xianyu-tools/scripts/run_listing_candidates.py")
    spec = importlib.util.spec_from_file_location("run_listing_candidates_script", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    source_bundle_file = tmp_path / "source_bundle.json"
    source_bundle_file.write_text(
        json.dumps(
            {
                "hot_items": [{"hot_item_id": "xy-001", "title": "升降桌", "price": 99.0}],
                "source_items": [{"source_item_id": "src-001", "title": "升降桌工厂直发"}],
            }
        ),
        encoding="utf-8",
    )
    profit_analysis_file = tmp_path / "profit_analysis.json"
    profit_analysis_file.write_text(
        json.dumps(
            {
                "profit_analysis": [
                    {
                        "hot_item_id": "xy-001",
                        "source_item_id": "src-001",
                        "estimated_margin": 12.0,
                        "gross_margin_rate": 0.22,
                        "cost_profit_rate": 0.4,
                        "risk_flags": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_listing_candidates.py",
            "--source-bundle-file",
            str(source_bundle_file),
            "--profit-analysis-file",
            str(profit_analysis_file),
        ],
    )
    assert module.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["listing_candidates"][0]["is_recommended"] is True


def test_export_pipeline_excel_outputs_workbook(tmp_path) -> None:
    from openpyxl import load_workbook

    hot_items_file = tmp_path / "hot_items.json"
    hot_items_file.write_text(
        json.dumps(
            {
                "hot_items": [
                    {
                        "hot_item_id": "xy-001",
                        "platform": "xianyu",
                        "title": "升降桌",
                        "price": 299.0,
                        "want_count": 1234,
                        "seller_name": "店主A",
                        "area": "杭州",
                        "image_url": "https://img.example.com/1.jpg",
                        "item_url": "https://www.goofish.com/item?id=xy-001",
                        "metadata": {"publish_time": "1小时前", "tags": ["包邮"]},
                    }
                ],
                "xianyu_market": {
                    "category_keyword": "升降桌",
                    "result_count": 54,
                    "filtered_by": ["超赞鱼小铺"],
                    "sorted_by": "want_count_desc",
                    "top_n": 10,
                    "top10_price_stats": {"min": 199.0, "max": 399.0, "median": 299.0},
                },
            }
        ),
        encoding="utf-8",
    )
    source_bundle_file = tmp_path / "source_bundle.json"
    source_bundle_file.write_text(
        json.dumps(
            {
                "hot_items": json.loads(hot_items_file.read_text(encoding="utf-8"))["hot_items"],
                "source_resolution": [
                    {
                        "hot_item_id": "xy-001",
                        "resolved": True,
                        "source_item_ids": ["src-001"],
                        "resolution_reason": "matched_source_items",
                    }
                ],
                "source_items": [
                    {
                        "hot_item_id": "xy-001",
                        "source_item_id": "src-001",
                        "source_platform": "1688",
                        "title": "升降桌工厂直发",
                        "price": 120.0,
                        "item_url": "https://detail.1688.com/offer/src-001.html",
                        "shop_name": "源头工厂",
                        "sales": 88,
                        "image_url": "https://img.example.com/src.jpg",
                        "shipping_fee": 0.0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    profit_analysis_file = tmp_path / "profit_analysis.json"
    profit_analysis_file.write_text(
        json.dumps(
            {
                "profit_analysis": [
                    {
                        "hot_item_id": "xy-001",
                        "source_item_id": "src-001",
                        "source_cost": 121.5,
                        "target_xianyu_price": 299.0,
                        "estimated_margin": 150.0,
                        "gross_margin_rate": 0.5,
                        "cost_profit_rate": 1.235,
                        "risk_flags": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    listing_candidates_file = tmp_path / "listing_candidates.json"
    listing_candidates_file.write_text(
        json.dumps(
            {
                "listing_candidates": [
                    {
                        "hot_item_id": "xy-001",
                        "source_item_id": "src-001",
                        "estimated_margin": 150.0,
                        "gross_margin_rate": 0.5,
                        "cost_profit_rate": 1.235,
                        "is_recommended": True,
                        "reasons": ["margin_ok"],
                        "blocked_by": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    output_file = tmp_path / "pipeline.xlsx"
    repo_root = Path("/Users/mac/PycharmProjects/mytools/xianyu-tools")
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_pipeline_excel.py",
            "--hot-items-file",
            str(hot_items_file),
            "--source-bundle-file",
            str(source_bundle_file),
            "--profit-analysis-file",
            str(profit_analysis_file),
            "--listing-candidates-file",
            str(listing_candidates_file),
            "--output-file",
            str(output_file),
        ],
        cwd=repo_root,
        env={"PYTHONPATH": "src"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    workbook = load_workbook(output_file)
    assert "汇总" in workbook.sheetnames
    assert "筛选总览" in workbook.sheetnames
    overview = workbook["筛选总览"]
    assert overview["A2"].value == "xy-001"


def test_run_category_pipeline_from_urls_writes_outputs(monkeypatch, capsys, tmp_path) -> None:
    script_path = Path("/Users/mac/PycharmProjects/mytools/xianyu-tools/scripts/run_category_pipeline_from_urls.py")
    spec = importlib.util.spec_from_file_location("run_category_pipeline_from_urls_script", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    hot_items_file = tmp_path / "hot_items.json"
    hot_items_file.write_text(
        json.dumps(
            {
                "hot_items": [
                    {
                        "hot_item_id": "xy-001",
                        "platform": "xianyu",
                        "title": "升降桌",
                        "price": 99.0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    result_url_map_file = tmp_path / "result_url_map.json"
    result_url_map_file.write_text(json.dumps({"xy-001": "https://s.1688.com/selloffer/offer_search.htm?keywords=x"}), encoding="utf-8")
    output_dir = tmp_path / "out"

    def fake_resolve(hot_items, *, result_urls_by_hot_item_id, adapter=None, limit_per_item=10):
        return {
            "source_resolution": [
                {
                    "hot_item_id": "xy-001",
                    "resolved": True,
                    "source_item_ids": ["src-001"],
                    "resolution_reason": "matched_source_items",
                }
            ],
            "source_items": [
                {
                    "source_platform": "1688",
                    "source_item_id": "src-001",
                    "title": "升降桌工厂直发",
                    "price": 60.0,
                    "shipping_fee": 5.0,
                    "item_url": "https://detail.1688.com/offer/src-001.html",
                    "sales": 120,
                    "metadata": {"hot_item_id": "xy-001"},
                }
            ],
        }

    monkeypatch.setattr(module, "resolve_hot_items_to_ali1688_urls", fake_resolve)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_category_pipeline_from_urls.py",
            "--hot-items-file",
            str(hot_items_file),
            "--result-url-map-file",
            str(result_url_map_file),
            "--output-dir",
            str(output_dir),
        ],
    )
    assert module.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert Path(output["source_bundle_file"]).exists()
    assert Path(output["profit_analysis_file"]).exists()
    assert Path(output["listing_candidates_file"]).exists()
