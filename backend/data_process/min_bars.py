from __future__ import annotations

"""分钟 K 复权加工：当日 adj_factor 作用于该日全部 bar（点时=bar_time）。"""

from typing import Any


def build_min_processed_rows(
    bars: list[dict[str, Any]],
    *,
    factors: dict[tuple[str, str], float],
    factor_type: str,
    process_batch_id: str,
    processed_at: str,
) -> tuple[list[dict[str, Any]], int]:
    """
    factors: (symbol, trade_date) -> factor
    缺因子的 bar 跳过并计数。
    """
    out: list[dict[str, Any]] = []
    skipped = 0
    for b in bars:
        symbol = str(b["symbol"])
        bar_time = str(b["bar_time"])
        trade_date = bar_time[:10]
        freq = str(b["freq"])
        fac = factors.get((symbol, trade_date))
        if fac is None or fac == 0:
            skipped += 1
            continue
        o = b.get("open")
        h = b.get("high")
        l = b.get("low")
        c = b.get("close")
        out.append(
            {
                "process_batch_id": process_batch_id,
                "symbol": symbol,
                "bar_time": bar_time,
                "freq": freq,
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "volume": b.get("volume"),
                "amount": b.get("amount"),
                "adj_factor": float(fac),
                "factor_type": factor_type,
                "adj_open": None if o is None else float(o) * float(fac),
                "adj_high": None if h is None else float(h) * float(fac),
                "adj_low": None if l is None else float(l) * float(fac),
                "adj_close": None if c is None else float(c) * float(fac),
                "source": str(b.get("source") or "akshare"),
                "processed_at": processed_at,
            }
        )
    return out, skipped
