from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

_NUM_RE = re.compile(r"[^\d.]")


def as_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "nat", "--"}:
        return ""
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text in {"--", "nan", "None"}:
        return None
    text = _NUM_RE.sub("", text)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def col_by_keywords(columns: Any, *groups: tuple[str, ...]) -> Any | None:
    """按关键词组优先级找列名；组内任一关键词命中即可。"""
    cols = list(columns)
    for group in groups:
        for c in cols:
            cs = str(c)
            if any(k in cs for k in group):
                return c
    return None


def board_from_code(code: str, exchange: str) -> str:
    if exchange == "BSE":
        return "北交所"
    if exchange == "SSE":
        if code.startswith("688"):
            return "科创板"
        return "主板"
    if code.startswith(("300", "301")):
        return "创业板"
    return "主板"


def infer_st_type(name: str) -> str | None:
    upper = name.upper()
    if "*ST" in upper or "＊ST" in name:
        return "*ST"
    if "ST" in upper:
        return "ST"
    if "退" in name:
        return "DELIST_ARRANGE"
    return None
