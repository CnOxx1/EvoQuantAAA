from __future__ import annotations

"""数据覆盖度矩阵（只读）。"""

from collections import defaultdict
from typing import Any

from shared.db import get_conn


# (label, table, date_col, symbol_col or None)
_TABLES: tuple[tuple[str, str, str, str | None], ...] = (
    ("equity_1d", "raw_equity_bar_1d", "trade_date", "symbol"),
    ("adj_factor", "raw_adj_factor", "trade_date", "symbol"),
    ("suspend", "raw_suspend", "trade_date", "symbol"),
    ("limit", "raw_limit_board", "trade_date", "symbol"),
    ("index_1d", "raw_index_bar_1d", "trade_date", None),
    ("valuation", "raw_valuation_1d", "trade_date", "symbol"),
    ("money_flow", "raw_money_flow", "trade_date", None),
)


def _months(start: str, end: str) -> list[str]:
    y, m = int(start[:4]), int(start[5:7])
    ye, me = int(end[:4]), int(end[5:7])
    out: list[str] = []
    while (y, m) <= (ye, me):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


def build_coverage_matrix(
    *,
    start: str,
    end: str,
    symbols: list[str] | None = None,
) -> dict[str, Any]:
    start, end = start[:10], end[:10]
    months = _months(start, end)
    matrix: dict[str, dict[str, int]] = {
        lab: {m: 0 for m in months} for lab, *_ in _TABLES
    }

    with get_conn() as conn:
        for label, table, date_col, sym_col in _TABLES:
            # trade_date 多为 TEXT；用 substr 取 YYYY-MM
            sql = f"""
                SELECT substr(CAST({date_col} AS TEXT), 1, 7) AS ym, COUNT(*) AS n
                FROM {table}
                WHERE CAST({date_col} AS TEXT)>=? AND CAST({date_col} AS TEXT)<=?
            """
            params: list[Any] = [start, end]
            if symbols and sym_col:
                ph = ",".join("?" * len(symbols))
                sql += f" AND {sym_col} IN ({ph})"
                params.extend(symbols)
            sql += f" GROUP BY substr(CAST({date_col} AS TEXT), 1, 7)"
            rows = conn.execute(sql, tuple(params)).fetchall()
            for r in rows:
                ym = str(r["ym"])
                if ym in matrix[label]:
                    matrix[label][ym] = int(r["n"])

    gaps: dict[str, list[str]] = {}
    for label, series in matrix.items():
        gaps[label] = [m for m, n in series.items() if int(n) == 0]

    return {
        "start": start,
        "end": end,
        "symbol_count": len(symbols or []),
        "months": months,
        "matrix": matrix,
        "gap_months": gaps,
    }


def format_coverage_report(report: dict[str, Any]) -> str:
    months: list[str] = report["months"]
    lines = [
        f"coverage start={report['start']} end={report['end']} "
        f"symbols={report['symbol_count']}",
        "table | " + " | ".join(months) + " | gap_months",
    ]
    for label, *_ in _TABLES:
        series = report["matrix"].get(label) or {}
        cells = [str(series.get(m, 0)) for m in months]
        gaps = report["gap_months"].get(label) or []
        gap_s = ",".join(gaps[:6]) + ("…" if len(gaps) > 6 else "")
        lines.append(f"{label} | " + " | ".join(cells) + f" | {gap_s or '-'}")
    return "\n".join(lines)


def month_counts_from_rows(
    rows: list[dict[str, Any]], *, date_key: str = "trade_date"
) -> dict[str, int]:
    """纯函数：供单测。"""
    out: dict[str, int] = defaultdict(int)
    for r in rows:
        d = str(r.get(date_key) or "")[:7]
        if len(d) == 7:
            out[d] += 1
    return dict(out)
