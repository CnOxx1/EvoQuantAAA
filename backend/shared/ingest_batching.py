from __future__ import annotations

"""Ingest 批量辅助：Universe 解析 + 分块（无业务编排语义）。"""

from calendar import monthrange
from datetime import date

from shared.db import get_conn
from shared.universe_resolve import resolve_universe_symbols


def chunk_symbols(symbols: list[str], chunk_size: int) -> list[list[str]]:
    if chunk_size < 1:
        raise ValueError("chunk_size 必须 >= 1")
    if not symbols:
        return []
    return [symbols[i : i + chunk_size] for i in range(0, len(symbols), chunk_size)]


def chunk_date_ranges(
    start: str,
    end: str,
    *,
    months: int = 1,
) -> list[tuple[str, str]]:
    """按月（或 N 个月）切分 [start, end] 闭区间。"""
    if months < 1:
        raise ValueError("months 必须 >= 1")
    s = date.fromisoformat(start[:10])
    e = date.fromisoformat(end[:10])
    if e < s:
        raise ValueError("end 必须 >= start")
    out: list[tuple[str, str]] = []
    y, m = s.year, s.month
    while True:
        first = date(y, m, 1)
        # 覆盖 months 个月
        ey, em = y, m + months - 1
        while em > 12:
            ey += 1
            em -= 12
        last = date(ey, em, monthrange(ey, em)[1])
        seg_start = max(first, s)
        seg_end = min(last, e)
        if seg_start <= seg_end:
            out.append((seg_start.isoformat(), seg_end.isoformat()))
        if seg_end >= e:
            break
        m += months
        while m > 12:
            y += 1
            m -= 12
    return out


def covered_dates(
    table: str,
    date_col: str,
    start: str,
    end: str,
    *,
    source: str | None = None,
) -> set[str]:
    """区间内已有数据的去重日期集合。"""
    start, end = start[:10], end[:10]
    sql = (
        f"SELECT DISTINCT {date_col} AS d FROM {table} "
        f"WHERE {date_col}>=? AND {date_col}<=?"
    )
    params: list[str] = [start, end]
    if source:
        sql += " AND source=?"
        params.append(source)
    with get_conn() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    return {str(r["d"])[:10] for r in rows if r["d"]}


def missing_date_ranges(
    table: str,
    date_col: str,
    start: str,
    end: str,
    *,
    months: int = 1,
    source: str | None = None,
    min_days: int = 1,
) -> list[tuple[str, str]]:
    """
    返回仍需补数的月块：块内已有日期数 < min_days 则保留。
    用于 suspend/limit 等按日 kind 的断点续跑。
    """
    ranges = chunk_date_ranges(start, end, months=months)
    covered = covered_dates(table, date_col, start, end, source=source)
    missing: list[tuple[str, str]] = []
    for s, e in ranges:
        n = sum(1 for d in covered if s <= d <= e)
        if n < min_days:
            missing.append((s, e))
    return missing


def should_chunk(
    symbols: list[str],
    *,
    chunked: bool = False,
    universe: str | None = None,
    chunk_size: int = 15,
    auto_threshold: int = 30,
) -> bool:
    """universe / 显式 --chunked / 标的数超阈值时启用分块。"""
    if not symbols:
        return False
    if chunked or universe:
        return True
    return len(symbols) > auto_threshold


def resolve_symbols_from_args(
    *,
    universe: str | None,
    symbols: list[str],
    as_of: str | None,
    as_of_end: str | None = None,
) -> tuple[str | None, list[str]]:
    """
    解析最终标的列表。
    - 无 universe：返回清洗后的显式 symbols
    - 有 universe：需要 as_of；可与显式 symbols 求交
    """
    cleaned = [s.strip() for s in symbols if s and s.strip()]
    if not universe:
        return None, cleaned
    if not as_of:
        raise ValueError("--universe 需要 --start 或 --universe-as-of 作为点时")
    sid, uni_symbols = resolve_universe_symbols(
        universe_code=universe,
        as_of=as_of,
        as_of_end=as_of_end,
    )
    if not uni_symbols:
        raise ValueError(f"Universe {universe} 无成员快照")
    if cleaned:
        want = set(cleaned)
        uni_symbols = [s for s in uni_symbols if s in want]
    return sid, uni_symbols
