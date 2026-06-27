from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pymysql

from xianyu_tools.config import settings


FIXTURE_TASK_ID = "mch62401"
FIXTURE_KEYWORD = "多渠道联调样本"


def get_db_conn():
    db_cfg = dict(settings.get_database_config() or {})
    db_cfg["cursorclass"] = pymysql.cursors.DictCursor
    return pymysql.connect(**db_cfg)


def ensure_fixture() -> dict:
    now = datetime.now()
    version = now.strftime("%Y%m%d")
    root_dir = str((Path(__file__).resolve().parents[1] / "outputs" / f"{FIXTURE_KEYWORD}_{version}").resolve())

    conn = get_db_conn()
    try:
        cursor = conn.cursor()

        cursor.execute("DELETE FROM ali1688_sources WHERE task_id = %s", (FIXTURE_TASK_ID,))
        cursor.execute("DELETE FROM xianyu_items WHERE task_id = %s", (FIXTURE_TASK_ID,))
        cursor.execute("DELETE FROM tasks WHERE id = %s", (FIXTURE_TASK_ID,))

        cursor.execute(
            """
            INSERT INTO tasks (id, keyword, status, progress, msg, created_at, root_dir, version, is_deleted, input_type, total_tokens)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, %s, %s)
            """,
            (
                FIXTURE_TASK_ID,
                FIXTURE_KEYWORD,
                "已完成",
                100,
                "多渠道联调验证样本",
                now,
                root_dir,
                version,
                "keyword",
                0,
            ),
        )

        cursor.execute(
            """
            INSERT INTO xianyu_items (task_id, rank_index, title, price, image_url, want_count, item_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                FIXTURE_TASK_ID,
                1,
                "多渠道联调验证商品：便携随身喷雾花露水 195ml",
                19.9,
                "https://img.alicdn.com/imgextra/i4/2200000000000/O1CN01testValidation.jpg",
                256,
                "https://www.goofish.com/item?id=multichannel-validation-sample",
            ),
        )
        item_id = cursor.lastrowid

        source_rows = [
            {
                "title": "1688 源头样本：经典花露水玻璃瓶 195ml",
                "offer_id": "VALIDATION-1688-001",
                "min_price": 7.8,
                "sku_count": 3,
                "source_url": "https://detail.1688.com/offer/validation-1688-001.html",
                "images": json.dumps(["https://example.com/1688-source-1.jpg"], ensure_ascii=False),
                "drop_reason": "",
                "html_path": "",
                "source_channel_id": "ali1688",
                "source_channel_label": "1688 货源渠道",
                "source_account_id": "ali1688-account-1",
                "source_account_label": "1688 账号 1",
            },
            {
                "title": "义乌 渠道样本：驱蚊清凉喷雾 180ml",
                "offer_id": "VALIDATION-YIWU-001",
                "min_price": 8.6,
                "sku_count": 2,
                "source_url": "https://source.example.com/yiwu/validation-001",
                "images": json.dumps(["https://example.com/yiwu-source-1.jpg"], ensure_ascii=False),
                "drop_reason": "",
                "html_path": "",
                "source_channel_id": "yiwu-market",
                "source_channel_type": "ali1688",
                "source_channel_label": "义乌渠道",
                "source_account_id": "yiwu-account-1",
                "source_account_label": "义乌 账号 1",
            },
        ]

        for row in source_rows:
            cursor.execute(
                """
                INSERT INTO ali1688_sources (
                    item_id, task_id, title, offer_id, min_price, sku_count, source_url, images,
                    drop_reason, html_path, source_channel_id, source_channel_type, source_channel_label, source_account_id, source_account_label
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    item_id,
                    FIXTURE_TASK_ID,
                    row["title"],
                    row["offer_id"],
                    row["min_price"],
                    row["sku_count"],
                    row["source_url"],
                    row["images"],
                    row["drop_reason"],
                    row["html_path"],
                    row["source_channel_id"],
                    row["source_channel_type"],
                    row["source_channel_label"],
                    row["source_account_id"],
                    row["source_account_label"],
                ),
            )

        conn.commit()
        return {
            "task_id": FIXTURE_TASK_ID,
            "keyword": FIXTURE_KEYWORD,
            "item_id": item_id,
            "source_channels": [row["source_channel_label"] for row in source_rows],
        }
    finally:
        conn.close()


def main() -> None:
    result = ensure_fixture()
    print(json.dumps({"status": "success", "fixture": result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
