from __future__ import annotations

"""从价格推导涨跌停（raw_limit_board 缺失时的回退）。"""

from collections import defaultdict
from typing import Any


def limit_threshold(symbol: str, *, is_st: bool) -> float:
    if is_st:
        return 0.05
    if symbol.startswith(("30", "68")):
        return 0.20
    return 0.10


def is_st_on_date(
    st_intervals: list[dict[str, Any]], *, symbol: str, trade_date: str
) -> bool:
    d = trade_date[:10]
    for r in st_intervals:
        if str(r["symbol"]) != symbol:
            continue
        eff = str(r.get("effective_date") or "")[:10]
        end = (r.get("end_date") or "")[:10] or None
        if not eff or eff > d:
            continue
        if end and end <= d:
            continue
        return True
    return False


def derive_limit_keys(
    *,
    bars: list[dict[str, Any]],
    st_rows: list[dict[str, Any]],
    existing_up: set[tuple[str, str]],
    existing_down: set[tuple[str, str]],
    tolerance: float = 0.002,
) -> tuple[set[tuple[str, str]], set[tuple[str, str]], set[tuple[str, str]]]:
    """
    返回 (limit_up, limit_down, derived_keys)。
    已在 raw_limit_board 的键不覆盖；其余用未复权 close vs 前收推断。
    """
    by_sym: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for b in bars:
        if b.get("close") is None:
            continue
        by_sym[str(b["symbol"])].append(b)

    up = set(existing_up)
    down = set(existing_down)
    derived: set[tuple[str, str]] = set()

    for sym, rows in by_sym.items():
        rows = sorted(rows, key=lambda r: str(r["trade_date"])[:10])
        prev_close: float | None = None
        for r in rows:
            d = str(r["trade_date"])[:10]
            close = float(r["close"])
            key = (sym, d)
            if prev_close is not None and prev_close > 0 and key not in existing_up and key not in existing_down:
                ret = close / prev_close - 1.0
                thr = limit_threshold(
                    sym, is_st=is_st_on_date(st_rows, symbol=sym, trade_date=d)
                )
                if ret >= thr - tolerance:
                    up.add(key)
                    derived.add(key)
                elif ret <= -(thr - tolerance):
                    down.add(key)
                    derived.add(key)
            prev_close = close
    return up, down, derived
