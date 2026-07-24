from __future__ import annotations

"""从已提交 Universe 快照解析标的列表（跨模块只经库交接）。"""

from shared.db import get_conn


def resolve_universe_symbols(
    *,
    universe_code: str,
    as_of: str,
    as_of_end: str | None = None,
) -> tuple[str | None, list[str]]:
    """
    点时优先：as_of 当日或之前最近 committed 快照。
    若无且提供 as_of_end，则允许回退到 <= as_of_end 的最近快照（样本期便利）。
    """
    d0 = as_of[:10]
    with get_conn() as conn:
        head = conn.execute(
            """
            SELECT universe_snapshot_id, as_of_date FROM universe_snapshot
            WHERE universe_code=? AND as_of_date<=? AND status='committed'
            ORDER BY as_of_date DESC LIMIT 1
            """,
            (universe_code, d0),
        ).fetchone()
        if not head and as_of_end:
            head = conn.execute(
                """
                SELECT universe_snapshot_id, as_of_date FROM universe_snapshot
                WHERE universe_code=? AND as_of_date<=? AND status='committed'
                ORDER BY as_of_date DESC LIMIT 1
                """,
                (universe_code, as_of_end[:10]),
            ).fetchone()
        if not head:
            return None, []
        sid = str(head["universe_snapshot_id"])
        rows = conn.execute(
            """
            SELECT symbol FROM universe_snapshot_member
            WHERE universe_snapshot_id=? AND is_eligible=1
            ORDER BY symbol
            """,
            (sid,),
        ).fetchall()
    return sid, [str(r["symbol"]) for r in rows]


def symbols_missing_equity_bars(
    symbols: list[str],
    *,
    start: str,
    end: str,
    min_rows: int = 1,
) -> list[str]:
    """返回在 [start,end] 内 raw_equity_bar_1d 行数 < min_rows 的标的（用于增量补齐）。"""
    if not symbols:
        return []
    start, end = start[:10], end[:10]
    missing: list[str] = []
    # 分批查，避免超长 IN
    chunk = 200
    have: dict[str, int] = {}
    with get_conn() as conn:
        for i in range(0, len(symbols), chunk):
            part = symbols[i : i + chunk]
            ph = ",".join("?" * len(part))
            rows = conn.execute(
                f"""
                SELECT symbol, COUNT(*) AS n
                FROM raw_equity_bar_1d
                WHERE trade_date>=? AND trade_date<=?
                  AND symbol IN ({ph})
                GROUP BY symbol
                """,
                (start, end, *part),
            ).fetchall()
            for r in rows:
                have[str(r["symbol"])] = int(r["n"])
    for s in symbols:
        if have.get(s, 0) < min_rows:
            missing.append(s)
    return missing


def _symbols_missing_in_table(
    symbols: list[str],
    *,
    table: str,
    date_col: str,
    start: str,
    end: str,
    min_rows: int = 1,
) -> list[str]:
    """通用：返回在日期区间内指定表行数不足的标的。"""
    if not symbols:
        return []
    start, end = start[:10], end[:10]
    missing: list[str] = []
    chunk = 200
    have: dict[str, int] = {}
    with get_conn() as conn:
        for i in range(0, len(symbols), chunk):
            part = symbols[i : i + chunk]
            ph = ",".join("?" * len(part))
            rows = conn.execute(
                f"""
                SELECT symbol, COUNT(*) AS n
                FROM {table}
                WHERE {date_col}>=? AND {date_col}<=?
                  AND symbol IN ({ph})
                GROUP BY symbol
                """,
                (start, end, *part),
            ).fetchall()
            for r in rows:
                have[str(r["symbol"])] = int(r["n"])
    for s in symbols:
        if have.get(s, 0) < min_rows:
            missing.append(s)
    return missing


def symbols_missing_corp_action(
    symbols: list[str],
    *,
    start: str,
    end: str,
    min_rows: int = 1,
) -> list[str]:
    """返回 [start,end] 内 raw_corp_action 行数不足的标的。"""
    return _symbols_missing_in_table(
        symbols,
        table="raw_corp_action",
        date_col="ex_date",
        start=start,
        end=end,
        min_rows=min_rows,
    )


def symbols_missing_fund_statement(
    symbols: list[str],
    *,
    min_rows: int = 1,
) -> list[str]:
    """返回 raw_fund_statement 中尚无足够行的标的（不按日期，便于 P1 续跑）。"""
    if not symbols:
        return []
    missing: list[str] = []
    chunk = 200
    have: set[str] = set()
    with get_conn() as conn:
        for i in range(0, len(symbols), chunk):
            part = symbols[i : i + chunk]
            ph = ",".join("?" * len(part))
            counts = conn.execute(
                f"""
                SELECT symbol, COUNT(*) AS n FROM raw_fund_statement
                WHERE symbol IN ({ph})
                GROUP BY symbol
                """,
                tuple(part),
            ).fetchall()
            for r in counts:
                if int(r["n"]) >= min_rows:
                    have.add(str(r["symbol"]))
    for s in symbols:
        if s not in have:
            missing.append(s)
    return missing
