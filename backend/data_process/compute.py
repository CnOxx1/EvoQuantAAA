from __future__ import annotations

from typing import Any, Iterable


def _f(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _mul(price: float | None, factor: float) -> float | None:
    if price is None:
        return None
    return price * factor


def build_equity_processed_rows(
    *,
    bars: list[dict[str, Any]],
    factors: dict[tuple[str, str], float],
    suspended: set[tuple[str, str]],
    limit_up: set[tuple[str, str]],
    limit_down: set[tuple[str, str]],
    factor_type: str,
    process_batch_id: str,
    processed_at: str,
) -> tuple[list[dict[str, Any]], int]:
    """
    将未复权日线 × 复权因子，并打上停牌/涨跌停可成交掩码。
    ret_1d 按标的内 trade_date 排序后用 adj_close 计算。
    """
    skipped = 0
    by_symbol: dict[str, list[dict[str, Any]]] = {}
    for bar in bars:
        symbol = str(bar["symbol"])
        trade_date = str(bar["trade_date"])[:10]
        factor = factors.get((symbol, trade_date))
        if factor is None or factor <= 0:
            skipped += 1
            continue
        is_sus = 1 if (symbol, trade_date) in suspended else 0
        is_up = 1 if (symbol, trade_date) in limit_up else 0
        is_dn = 1 if (symbol, trade_date) in limit_down else 0
        can_buy = 0 if (is_sus or is_up) else 1
        can_sell = 0 if (is_sus or is_dn) else 1
        open_ = _f(bar.get("open"))
        high = _f(bar.get("high"))
        low = _f(bar.get("low"))
        close = _f(bar.get("close"))
        row = {
            "process_batch_id": process_batch_id,
            "symbol": symbol,
            "trade_date": trade_date,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": _f(bar.get("volume")),
            "amount": _f(bar.get("amount")),
            "adj_factor": factor,
            "factor_type": factor_type,
            "adj_open": _mul(open_, factor),
            "adj_high": _mul(high, factor),
            "adj_low": _mul(low, factor),
            "adj_close": _mul(close, factor),
            "ret_1d": None,
            "is_suspended": is_sus,
            "is_limit_up": is_up,
            "is_limit_down": is_dn,
            "can_buy": can_buy,
            "can_sell": can_sell,
            "source": str(bar.get("source") or ""),
            "processed_at": processed_at,
        }
        by_symbol.setdefault(symbol, []).append(row)

    out: list[dict[str, Any]] = []
    for symbol, rows in by_symbol.items():
        rows.sort(key=lambda r: r["trade_date"])
        prev_adj: float | None = None
        for row in rows:
            adj_close = row["adj_close"]
            if prev_adj is not None and adj_close is not None and prev_adj != 0:
                row["ret_1d"] = adj_close / prev_adj - 1.0
            if adj_close is not None:
                prev_adj = adj_close
            out.append(row)
    out.sort(key=lambda r: (r["symbol"], r["trade_date"]))
    return out, skipped


def build_index_processed_rows(
    *,
    bars: list[dict[str, Any]],
    process_batch_id: str,
    processed_at: str,
) -> list[dict[str, Any]]:
    by_index: dict[str, list[dict[str, Any]]] = {}
    for bar in bars:
        index_symbol = str(bar["index_symbol"])
        trade_date = str(bar["trade_date"])[:10]
        close = _f(bar.get("close"))
        row = {
            "process_batch_id": process_batch_id,
            "index_symbol": index_symbol,
            "trade_date": trade_date,
            "open": _f(bar.get("open")),
            "high": _f(bar.get("high")),
            "low": _f(bar.get("low")),
            "close": close,
            "volume": _f(bar.get("volume")),
            "amount": _f(bar.get("amount")),
            "ret_1d": None,
            "source": str(bar.get("source") or ""),
            "processed_at": processed_at,
        }
        by_index.setdefault(index_symbol, []).append(row)

    out: list[dict[str, Any]] = []
    for _, rows in by_index.items():
        rows.sort(key=lambda r: r["trade_date"])
        prev: float | None = None
        for row in rows:
            close = row["close"]
            if prev is not None and close is not None and prev != 0:
                row["ret_1d"] = close / prev - 1.0
            if close is not None:
                prev = close
            out.append(row)
    out.sort(key=lambda r: (r["index_symbol"], r["trade_date"]))
    return out


def as_sets(pairs: Iterable[tuple[str, str]]) -> set[tuple[str, str]]:
    return {(str(a), str(b)[:10]) for a, b in pairs}
