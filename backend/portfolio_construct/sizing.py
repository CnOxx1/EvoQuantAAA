from __future__ import annotations

"""目标持仓 sizing（纯函数）：权重归一 + 整手股数。"""

from typing import Any


def renormalize_weights(
    rows: list[dict[str, Any]], *, weight_key: str = "weight"
) -> list[dict[str, Any]]:
    """过滤后按剩余权重重新归一到 1.0；全零则原样返回空。"""
    kept = [dict(r) for r in rows if float(r.get(weight_key) or 0.0) > 0]
    total = sum(float(r[weight_key]) for r in kept)
    if total <= 0:
        return []
    out: list[dict[str, Any]] = []
    for r in kept:
        nr = dict(r)
        nr["target_weight"] = float(r[weight_key]) / total
        out.append(nr)
    return out


def lot_shares(value: float, price: float, lot_size: int) -> int:
    if price <= 0 or lot_size <= 0 or value <= 0:
        return 0
    raw = int(value / price)
    return (raw // lot_size) * lot_size


def size_positions(
    *,
    weight_rows: list[dict[str, Any]],
    prices: dict[str, float],
    can_buy: dict[str, int],
    nav: float,
    lot_size: int = 100,
    drop_cannot_buy: bool = True,
    can_sell: dict[str, int] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    将信号权重转为目标股数。
    - drop_cannot_buy：can_buy!=1 的标的剔除后重归一
    - 缺价剔除后重归一
    - 成交价应为未复权 close（由上游 prices 保证）
    返回 (positions, meta)
    """
    if nav <= 0:
        raise ValueError("nav 必须 > 0")
    if lot_size <= 0:
        raise ValueError("lot_size 必须 > 0")
    sell_map = can_sell or {}

    candidates: list[dict[str, Any]] = []
    dropped_no_price = 0
    dropped_cannot_buy = 0
    for r in weight_rows:
        sym = str(r["symbol"])
        w = float(r.get("weight") or 0.0)
        if w <= 0:
            continue
        px = prices.get(sym)
        if px is None or px <= 0:
            dropped_no_price += 1
            continue
        cb = int(can_buy.get(sym, 0))
        if drop_cannot_buy and cb != 1:
            dropped_cannot_buy += 1
            continue
        candidates.append(
            {
                "symbol": sym,
                "weight": w,
                "signal_weight": w,
                "signal_value": r.get("signal_value"),
                "price": float(px),
                "can_buy": cb,
                "can_sell": int(sell_map[sym]) if sym in sell_map else 1,
            }
        )

    normed = renormalize_weights(candidates, weight_key="weight")
    positions: list[dict[str, Any]] = []
    invested = 0.0
    for r in normed:
        tw = float(r["target_weight"])
        px = float(r["price"])
        target_value = nav * tw
        shares = float(lot_shares(target_value, px, lot_size))
        actual_value = shares * px
        invested += actual_value
        positions.append(
            {
                "symbol": r["symbol"],
                "target_weight": tw,
                "target_value": actual_value,
                "target_shares": shares,
                "price": px,
                "signal_value": r.get("signal_value"),
                "signal_weight": float(r.get("signal_weight") or tw),
                "can_buy": int(r.get("can_buy") or 1),
                "can_sell": int(
                    r.get("can_sell") if r.get("can_sell") is not None else 1
                ),
                "status": "draft",
            }
        )

    meta = {
        "dropped_no_price": dropped_no_price,
        "dropped_cannot_buy": dropped_cannot_buy,
        "position_count": len(positions),
        "invested_value": invested,
        "cash_residual": max(0.0, nav - invested),
        "lot_size": lot_size,
        "pricing": "unadjusted_close",
    }
    return positions, meta
