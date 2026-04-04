from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re


def slugify_keyword(keyword: str) -> str:
    text = re.sub(r"\s+", "_", keyword.strip())
    text = re.sub(r'[\\/:*?"<>|]+', "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "keyword"


def build_keyword_output_dir(output_root: str | Path, keyword: str, *, now: datetime | None = None) -> Path:
    now = now or datetime.now()
    date_part = now.strftime("%Y%m%d")
    return Path(output_root) / f"{slugify_keyword(keyword)}_{date_part}"
