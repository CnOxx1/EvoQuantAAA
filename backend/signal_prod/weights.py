from __future__ import annotations

"""生产信号权重构建（纯函数；与回测 FACTOR_TOP_N 口径一致，禁止前视）。"""

from collections import defaultdict
from typing import Any


def build_factor_top_n_weights(
    *,
    trade_dates: list[str],
    symbols_by_date: dict[str, set[str]],
    factor_rows: list[dict[str, Any]],
    top_n: int,
    rebalance_days: int,
) -> list[dict[str, Any]]:
    """
    调仓日用「前一交易日」因子值取 top N 等权。
    返回行：trade_date / symbol / weight / signal_value
    """
    if top_n <= 0:
        raise ValueError("top_n 必须 > 0")
    if rebalance_days <= 0:
        raise ValueError("rebalance_days 必须 > 0")

    dates = sorted({d[:10] for d in trade_dates})
    if len(dates) < 2:
        return []

    factor_by_date: dict[str, dict[str, float]] = defaultdict(dict)
    for r in factor_rows:
        if r.get("value") is None:
            continue
        factor_by_date[str(r["trade_date"])[:10]][str(r["symbol"])] = float(r["value"])

    out: list[dict[str, Any]] = []
    entry_idx: int | None = None
    for i, d in enumerate(dates):
        if i == 0:
            continue
        prev = dates[i - 1]
        fmap = factor_by_date.get(prev) or {}
        eligible = symbols_by_date.get(d) or set()
        candidates = [(sym, val) for sym, val in fmap.items() if sym in eligible]
        if not candidates:
            continue
        if entry_idx is None:
            entry_idx = i
        elif (i - entry_idx) % rebalance_days != 0:
            continue
        candidates.sort(key=lambda x: x[1], reverse=True)
        picked = candidates[:top_n]
        if not picked:
            continue
        w = 1.0 / len(picked)
        for sym, val in picked:
            out.append(
                {
                    "trade_date": d,
                    "symbol": sym,
                    "weight": w,
                    "signal_value": val,
                }
            )
    return out
