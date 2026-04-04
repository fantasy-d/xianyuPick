from datetime import datetime
from pathlib import Path

from xianyu_tools.keyword_pipeline import build_keyword_output_dir, slugify_keyword
from xianyu_tools.ali1688_session import looks_like_login_url
from xianyu_tools.pipeline_summary import build_pipeline_summary


def test_slugify_keyword_keeps_chinese_and_replaces_unsafe_chars():
    assert slugify_keyword("蚊帐/宫廷 风") == "蚊帐_宫廷_风"


def test_build_keyword_output_dir_uses_keyword_and_date():
    path = build_keyword_output_dir(Path("/tmp/outputs"), "蚊帐", now=datetime(2026, 4, 4, 18, 30, 0))
    assert path == Path("/tmp/outputs/蚊帐_20260404")


def test_looks_like_login_url_detects_taobao_and_1688_login():
    assert looks_like_login_url("https://login.taobao.com/member/login.jhtml")
    assert looks_like_login_url("https://login.1688.com/member/signin.htm")
    assert not looks_like_login_url("https://www.1688.com/")


def test_build_pipeline_summary_counts_and_recommended_items():
    summary = build_pipeline_summary(
        keyword="蚊帐",
        hot_payload={
            "xianyu_market": {"category_keyword": "蚊帐", "result_count": 12, "top_n": 10, "top10_price_stats": {"min": 10}},
            "hot_items": [{"hot_item_id": "x1"}],
        },
        source_bundle={
            "source_resolution": [{"hot_item_id": "x1", "resolution_reason": "matched_source_items"}],
            "source_items": [
                {"candidate_status": "accepted"},
                {"candidate_status": "filtered"},
            ],
        },
        profit_payload={"profit_analysis": [{"hot_item_id": "x1", "source_item_id": "s1"}]},
        listing_payload={
            "listing_candidates": [
                {
                    "hot_item_id": "x1",
                    "source_item_id": "s1",
                    "is_recommended": True,
                    "estimated_margin": 12.3,
                    "gross_margin_rate": 0.4,
                    "cost_profit_rate": 0.8,
                    "reasons": ["margin_ok"],
                    "blocked_by": [],
                }
            ]
        },
    )
    assert summary["counts"]["hot_items"] == 1
    assert summary["counts"]["accepted_source_items"] == 1
    assert summary["counts"]["filtered_source_items"] == 1
    assert summary["counts"]["recommended_listing_candidates"] == 1
    assert summary["recommended_items"][0]["hot_item_id"] == "x1"
