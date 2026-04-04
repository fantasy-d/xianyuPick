#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from xianyu_tools.pipeline_summary import build_pipeline_summary
from xianyu_tools.keyword_pipeline import build_keyword_output_dir


def _launch_arg_flags(launch_args: list[str]) -> list[str]:
    return [f"--launch-arg={value}" for value in launch_args]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the full keyword pipeline: Xianyu hot items -> 1688 image search -> source resolution -> profit -> Excel."
    )
    parser.add_argument("--keyword", required=True, help="Xianyu category keyword.")
    parser.add_argument("--state-file", required=True, help="Path to xianyu_state.json.")
    parser.add_argument("--browser-channel", default="chrome")
    parser.add_argument("--output-root", default="./outputs")
    parser.add_argument("--output-dir", help="Optional explicit output dir. Defaults to 搜索词_YYYYMMDD under output-root.")
    parser.add_argument("--xianyu-max-pages", type=int, default=2)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--ali1688-user-data-dir", default="./profiles/ali1688_chrome_profile")
    parser.add_argument("--ali1688-profile-directory")
    parser.add_argument("--skip-ali1688-precheck", action="store_true")
    parser.add_argument("--max-subjects", type=int, default=3)
    parser.add_argument("--min-wait-seconds", type=float, default=30.0)
    parser.add_argument("--max-wait-seconds", type=float, default=60.0)
    parser.add_argument("--limit-per-item", type=int, default=10)
    parser.add_argument("--packaging-cost", type=float, default=1.5)
    parser.add_argument("--platform-fee-rate", type=float, default=0.03)
    parser.add_argument("--payment-fee-rate", type=float, default=0.006)
    parser.add_argument("--aftersale-reserve-rate", type=float, default=0.02)
    parser.add_argument("--min-margin", type=float, default=8.0)
    parser.add_argument("--min-margin-rate", type=float, default=0.18)
    parser.add_argument("--max-risk-flags", type=int, default=2)
    parser.add_argument(
        "--launch-arg",
        action="append",
        default=[],
        help="Extra browser launch arg. Repeatable, e.g. --launch-arg=--start-maximized",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else build_keyword_output_dir(args.output_root, args.keyword)
    output_dir.mkdir(parents=True, exist_ok=True)
    browser_runs_dir = output_dir / "browser_runs"
    browser_runs_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = output_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    hot_items_file = output_dir / "hot_items.json"
    result_url_map_file = output_dir / "result_url_map.json"
    source_bundle_file = output_dir / "source_bundle.json"
    profit_analysis_file = output_dir / "profit_analysis.json"
    listing_candidates_file = output_dir / "listing_candidates.json"
    excel_file = output_dir / "filtering_report.xlsx"
    manifest_file = output_dir / "manifest.json"
    summary_file = output_dir / "summary.json"
    ali1688_session_file = output_dir / "ali1688_session.json"

    _run_json_to_file(
        [
            "scripts/run_xianyu_hot_items.py",
            "--keyword",
            args.keyword,
            "--state-file",
            args.state_file,
            "--browser-channel",
            args.browser_channel,
            "--max-pages",
            str(args.xianyu_max_pages),
            "--top-n",
            str(args.top_n),
            *_launch_arg_flags(args.launch_arg),
        ],
        hot_items_file,
        log_file=logs_dir / "01_xianyu_hot_items.log",
    )

    ali1688_session_payload = None
    if not args.skip_ali1688_precheck:
        precheck_cmd = [
            "scripts/inspect_ali1688_session.py",
            "--user-data-dir",
            args.ali1688_user_data_dir,
            "--browser-channel",
            args.browser_channel,
            *_launch_arg_flags(args.launch_arg),
        ]
        if args.ali1688_profile_directory:
            precheck_cmd.extend(["--profile-directory", args.ali1688_profile_directory])
        _run_json_to_file(
            precheck_cmd,
            ali1688_session_file,
            log_file=logs_dir / "02_ali1688_session_precheck.log",
        )
        ali1688_session_payload = json.loads(ali1688_session_file.read_text(encoding="utf-8"))
        if ali1688_session_payload.get("state") in {"login", "profile_locked", "unknown"}:
            manifest = {
                "keyword": args.keyword,
                "output_dir": str(output_dir),
                "status": "blocked_by_ali1688_session",
                "ali1688_session": ali1688_session_payload,
                "files": {
                    "hot_items_file": str(hot_items_file),
                    "ali1688_session_file": str(ali1688_session_file),
                },
                "logs": {
                    "xianyu_hot_items_log": str(logs_dir / "01_xianyu_hot_items.log"),
                    "ali1688_session_precheck_log": str(logs_dir / "02_ali1688_session_precheck.log"),
                },
            }
            manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(manifest, ensure_ascii=False, indent=2))
            return 1

    browser_cmd = [
        "scripts/generate_ali1688_result_url_map_via_browser_session.py",
        "--hot-items-file",
        str(hot_items_file),
        "--output-file",
        str(result_url_map_file),
        "--summary-dir",
        str(browser_runs_dir),
        "--browser-channel",
        args.browser_channel,
        "--user-data-dir",
        args.ali1688_user_data_dir,
        "--max-subjects",
        str(args.max_subjects),
        "--min-wait-seconds",
        str(args.min_wait_seconds),
        "--max-wait-seconds",
        str(args.max_wait_seconds),
        *_launch_arg_flags(args.launch_arg),
    ]
    if args.ali1688_profile_directory:
        browser_cmd.extend(["--profile-directory", args.ali1688_profile_directory])
    _run_stdout(
        browser_cmd,
        logs_dir / "03_ali1688_browser_session.log",
    )

    _run_json_to_file(
        [
            "scripts/run_source_resolution_from_browser_runs.py",
            "--hot-items-file",
            str(hot_items_file),
            "--browser-runs-dir",
            str(browser_runs_dir),
            "--limit-per-item",
            str(args.limit_per_item),
        ],
        source_bundle_file,
        log_file=logs_dir / "04_source_resolution.log",
    )
    _run_json_to_file(
        [
            "scripts/run_profit_analysis.py",
            "--source-bundle-file",
            str(source_bundle_file),
            "--packaging-cost",
            str(args.packaging_cost),
            "--platform-fee-rate",
            str(args.platform_fee_rate),
            "--payment-fee-rate",
            str(args.payment_fee_rate),
            "--aftersale-reserve-rate",
            str(args.aftersale_reserve_rate),
            "--min-margin",
            str(args.min_margin),
            "--min-margin-rate",
            str(args.min_margin_rate),
        ],
        profit_analysis_file,
        log_file=logs_dir / "05_profit_analysis.log",
    )
    _run_json_to_file(
        [
            "scripts/run_listing_candidates.py",
            "--source-bundle-file",
            str(source_bundle_file),
            "--profit-analysis-file",
            str(profit_analysis_file),
            "--min-margin",
            str(args.min_margin),
            "--min-margin-rate",
            str(args.min_margin_rate),
            "--max-risk-flags",
            str(args.max_risk_flags),
        ],
        listing_candidates_file,
        log_file=logs_dir / "06_listing_candidates.log",
    )
    _run_stdout(
        [
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
            str(excel_file),
        ],
        logs_dir / "07_export_excel.log",
    )

    hot_payload = json.loads(hot_items_file.read_text(encoding="utf-8"))
    source_bundle_payload = json.loads(source_bundle_file.read_text(encoding="utf-8"))
    profit_payload = json.loads(profit_analysis_file.read_text(encoding="utf-8"))
    listing_payload = json.loads(listing_candidates_file.read_text(encoding="utf-8"))
    summary_payload = build_pipeline_summary(
        keyword=args.keyword,
        hot_payload=hot_payload,
        source_bundle=source_bundle_payload,
        profit_payload=profit_payload,
        listing_payload=listing_payload,
    )
    summary_file.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest = {
        "keyword": args.keyword,
        "output_dir": str(output_dir),
        "browser_channel": args.browser_channel,
        "xianyu_max_pages": args.xianyu_max_pages,
        "top_n": args.top_n,
        "ali1688_user_data_dir": args.ali1688_user_data_dir,
        "ali1688_profile_directory": args.ali1688_profile_directory,
        "ali1688_session": ali1688_session_payload,
        "max_subjects": args.max_subjects,
        "min_wait_seconds": args.min_wait_seconds,
        "max_wait_seconds": args.max_wait_seconds,
        "limit_per_item": args.limit_per_item,
        "files": {
            "hot_items_file": str(hot_items_file),
            "ali1688_session_file": str(ali1688_session_file),
            "result_url_map_file": str(result_url_map_file),
            "source_bundle_file": str(source_bundle_file),
            "profit_analysis_file": str(profit_analysis_file),
            "listing_candidates_file": str(listing_candidates_file),
            "summary_file": str(summary_file),
            "excel_file": str(excel_file),
        },
        "logs": {
            "xianyu_hot_items_log": str(logs_dir / "01_xianyu_hot_items.log"),
            "ali1688_session_precheck_log": str(logs_dir / "02_ali1688_session_precheck.log"),
            "ali1688_browser_session_log": str(logs_dir / "03_ali1688_browser_session.log"),
            "source_resolution_log": str(logs_dir / "04_source_resolution.log"),
            "profit_analysis_log": str(logs_dir / "05_profit_analysis.log"),
            "listing_candidates_log": str(logs_dir / "06_listing_candidates.log"),
            "export_excel_log": str(logs_dir / "07_export_excel.log"),
        },
    }
    manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(manifest, ensure_ascii=False, indent=2)
    )
    return 0


def _run_json_to_file(script_args: list[str], output_file: Path, *, log_file: Path) -> None:
    result = subprocess.run(
        [sys.executable, *script_args],
        cwd=Path(__file__).resolve().parents[1],
        env={**dict(PYTHONPATH="src"), **_filtered_env()},
        capture_output=True,
        text=True,
        check=True,
    )
    output_file.write_text(result.stdout, encoding="utf-8")
    log_file.write_text(result.stderr or "", encoding="utf-8")


def _run_stdout(script_args: list[str], log_file: Path) -> None:
    result = subprocess.run(
        [sys.executable, *script_args],
        cwd=Path(__file__).resolve().parents[1],
        env={**dict(PYTHONPATH="src"), **_filtered_env()},
        capture_output=True,
        text=True,
        check=True,
    )
    log_text = result.stdout
    if result.stderr:
        log_text = f"{log_text}\n{result.stderr}" if log_text else result.stderr
    log_file.write_text(log_text, encoding="utf-8")


def _filtered_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = "src"
    return env


if __name__ == "__main__":
    sys.exit(main())
