from __future__ import annotations

"""成交冲击（纯函数）：flat 基滑点 + 可选 sqrt(ADV 参与度) 附加冲击。"""

from collections import defaultdict
from typing import Any


def effective_slippage_rate(
    *,
    base_slippage: float,
    impact_model: str | None = "flat",
    impact_coef: float | None = 0.0,
    notional: float | None = None,
    adv: float | None = None,
) -> float:
    """
    返回总滑点率（小数，如 0.001=10bps）。

    - flat / None / 空：仅 base_slippage
    - sqrt_adv：base + coef * sqrt(notional / ADV)；ADV 缺失时退回 flat
    """
    base = max(0.0, float(base_slippage or 0.0))
    model = (impact_model or "flat").strip().lower()
    if model in ("", "flat", "none"):
        return base
    if model != "sqrt_adv":
        return base
    coef = float(impact_coef or 0.0)
    if coef <= 0 or notional is None or float(notional) <= 0:
        return base
    if adv is None or float(adv) <= 0:
        return base
    participation = float(notional) / float(adv)
    return base + coef * (participation**0.5)


def apply_side_slippage(*, side: str, mid: float, slip_rate: float) -> float:
    if mid <= 0:
        raise ValueError("price 必须 > 0")
    s = str(side).upper()
    rate = max(0.0, float(slip_rate or 0.0))
    if s == "BUY":
        return mid * (1.0 + rate)
    if s == "SELL":
        return mid * (1.0 - rate)
    raise ValueError(f"未知 side: {side}")


def slipped_fill_price(
    *,
    side: str,
    mid: float,
    base_slippage: float,
    impact_model: str | None = "flat",
    impact_coef: float | None = 0.0,
    qty: float | None = None,
    adv: float | None = None,
) -> float:
    """按 mid×qty 估算名义成交额后定价（冲击与 mid 同向）。"""
    notional = None
    if qty is not None and float(qty) > 0 and mid > 0:
        notional = float(qty) * float(mid)
    rate = effective_slippage_rate(
        base_slippage=base_slippage,
        impact_model=impact_model,
        impact_coef=impact_coef,
        notional=notional,
        adv=adv,
    )
    return apply_side_slippage(side=side, mid=mid, slip_rate=rate)


def compute_rolling_adv(
    bars: list[dict[str, Any]],
    *,
    lookback: int = 20,
) -> dict[tuple[str, str], float]:
    """
    按 (symbol, trade_date) 返回含当日在内的近 lookback 个交易日 amount 均值。
    仅使用 amount>0 的样本；样本不足时用已有天数均值。
    """
    lb = max(1, int(lookback))
    by_sym: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for b in bars:
        amt = b.get("amount")
        if amt is None or float(amt) <= 0:
            continue
        sym = str(b.get("symbol") or "")
        d = str(b.get("trade_date") or "")[:10]
        if not sym or not d:
            continue
        by_sym[sym].append((d, float(amt)))

    out: dict[tuple[str, str], float] = {}
    for sym, series in by_sym.items():
        series.sort(key=lambda x: x[0])
        window: list[float] = []
        for d, amt in series:
            window.append(amt)
            if len(window) > lb:
                window.pop(0)
            out[(sym, d)] = sum(window) / len(window)
    return out


def attach_adv_to_bars(
    bars: list[dict[str, Any]],
    *,
    lookback: int = 20,
) -> list[dict[str, Any]]:
    """就地/拷贝写入 bar['adv']（基于同列表内 amount 滚动）。"""
    adv_map = compute_rolling_adv(bars, lookback=lookback)
    out: list[dict[str, Any]] = []
    for b in bars:
        row = dict(b)
        key = (str(row.get("symbol") or ""), str(row.get("trade_date") or "")[:10])
        if key in adv_map:
            row["adv"] = adv_map[key]
        out.append(row)
    return out
