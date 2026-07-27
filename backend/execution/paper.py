from __future__ import annotations

"""纸面成交仿真（纯函数）：按目标持仓生成 BUY/SELL 意图与 fill 明细。"""

from typing import Any

from execution.models import CostSnapshot


def commission(amount: float, cost: CostSnapshot) -> float:
    return max(abs(amount) * cost.commission_rate, cost.min_commission)


def fill_price(side: str, mid: float, cost: CostSnapshot) -> float:
    if mid <= 0:
        raise ValueError("price 必须 > 0")
    if side == "BUY":
        return mid * (1.0 + cost.slippage_rate)
    if side == "SELL":
        return mid * (1.0 - cost.slippage_rate)
    raise ValueError(f"未知 side: {side}")


def apply_sellable_limits(
    intents: list[dict[str, Any]],
    *,
    sellable_shares: dict[str, float] | None,
) -> list[dict[str, Any]]:
    """
    T+1 / 可卖上限：SELL 数量压缩至 sellable；无可卖则 reject。
    sellable_shares 为 None 时不改动（兼容旧调用）。
    """
    if sellable_shares is None:
        return intents
    out: list[dict[str, Any]] = []
    for it in intents:
        if it.get("reject") or str(it.get("side")) != "SELL":
            out.append(it)
            continue
        avail = float(sellable_shares.get(str(it["symbol"]), 0.0))
        qty = float(it["qty"])
        if avail + 1e-9 < 1.0:
            out.append({**it, "reject": True, "reason": "t1_or_insufficient"})
            continue
        if qty > avail + 1e-9:
            out.append({**it, "qty": avail, "reject": False, "reason": "clamped_sellable"})
        else:
            out.append(it)
    return out


def build_paper_intents(
    *,
    positions: list[dict[str, Any]],
    current_shares: dict[str, float] | None = None,
    sellable_shares: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """
    目标持仓 vs 当前持仓（默认空仓）→ 买卖意图。
    股数已为整手；差额按 lot 向下取整由上游保证。
    """
    cur = current_shares or {}
    intents: list[dict[str, Any]] = []
    symbols = sorted(
        {str(p["symbol"]) for p in positions if float(p.get("target_shares") or 0) > 0}
        | set(cur.keys())
    )
    want_by = {
        str(p["symbol"]): float(p.get("target_shares") or 0)
        for p in positions
    }
    price_by = {
        str(p["symbol"]): float(p["price"])
        for p in positions
        if p.get("price") is not None
    }
    can_buy_by = {
        str(p["symbol"]): int(p["can_buy"]) if p.get("can_buy") is not None else 0
        for p in positions
    }
    can_sell_by = {
        str(p["symbol"]): int(p["can_sell"]) if p.get("can_sell") is not None else 1
        for p in positions
    }

    for sym in symbols:
        want = float(want_by.get(sym, 0.0))
        have = float(cur.get(sym, 0.0))
        delta = want - have
        if abs(delta) < 1e-9:
            continue
        px = price_by.get(sym)
        if px is None or px <= 0:
            intents.append(
                {
                    "symbol": sym,
                    "side": "BUY" if delta > 0 else "SELL",
                    "qty": abs(delta),
                    "reject": True,
                    "reason": "missing_price",
                }
            )
            continue
        if delta > 0:
            if can_buy_by.get(sym, 0) != 1:
                intents.append(
                    {
                        "symbol": sym,
                        "side": "BUY",
                        "qty": delta,
                        "reject": True,
                        "reason": "cannot_buy",
                        "mid_price": px,
                    }
                )
                continue
            intents.append(
                {
                    "symbol": sym,
                    "side": "BUY",
                    "qty": delta,
                    "reject": False,
                    "mid_price": px,
                }
            )
        else:
            if can_sell_by.get(sym, 1) != 1:
                intents.append(
                    {
                        "symbol": sym,
                        "side": "SELL",
                        "qty": -delta,
                        "reject": True,
                        "reason": "cannot_sell",
                        "mid_price": px,
                    }
                )
                continue
            intents.append(
                {
                    "symbol": sym,
                    "side": "SELL",
                    "qty": -delta,
                    "reject": False,
                    "mid_price": px,
                }
            )
    return apply_sellable_limits(intents, sellable_shares=sellable_shares)


def simulate_paper_fills(
    *,
    intents: list[dict[str, Any]],
    cost: CostSnapshot,
    trade_date: str,
    cash: float | None = None,
    lot_size: int = 100,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    返回 (orders, fills)。
    先处理 SELL 回笼现金，再 BUY；cash 非 None 时禁止透支（整手缩量或 reject）。
    """
    orders: list[dict[str, Any]] = []
    fills: list[dict[str, Any]] = []
    cash_left = None if cash is None else float(cash)
    lot = max(1, int(lot_size))

    ordered = sorted(
        intents,
        key=lambda it: (
            0 if str(it.get("side")) == "SELL" else 1,
            str(it.get("symbol") or ""),
        ),
    )

    for it in ordered:
        side = str(it["side"])
        qty = float(it["qty"])
        if it.get("reject"):
            orders.append(
                {
                    "symbol": it["symbol"],
                    "side": side,
                    "qty": qty,
                    "limit_price": it.get("mid_price"),
                    "status": "REJECTED",
                    "reason": it.get("reason") or "rejected",
                }
            )
            continue
        mid = float(it["mid_price"])
        px = fill_price(side, mid, cost)

        if side == "SELL":
            amount = qty * px
            slip = abs(px - mid) * qty
            comm = commission(amount, cost)
            stamp = amount * cost.stamp_tax_rate
            if cash_left is not None:
                cash_left += amount - comm - stamp
            orders.append(
                {
                    "symbol": it["symbol"],
                    "side": side,
                    "qty": qty,
                    "limit_price": mid,
                    "status": "FILLED",
                    "reason": None,
                }
            )
            fills.append(
                {
                    "symbol": it["symbol"],
                    "side": side,
                    "qty": qty,
                    "price": px,
                    "amount": amount,
                    "commission": comm,
                    "stamp_tax": stamp,
                    "slippage_cost": slip,
                    "trade_date": trade_date[:10],
                }
            )
            continue

        # BUY
        if cash_left is not None:
            # 最大可买整手：fill_price 已含滑点；佣金用迭代压到可负担
            unit = px
            max_by_cash = int(cash_left / unit + 1e-9) if unit > 0 else 0
            max_lot = (max_by_cash // lot) * lot
            while max_lot >= lot:
                amount_try = max_lot * unit
                comm_try = commission(amount_try, cost)
                if amount_try + comm_try <= cash_left + 1e-9:
                    break
                max_lot -= lot
            if max_lot < lot or max_lot + 1e-9 < qty:
                if max_lot < lot:
                    orders.append(
                        {
                            "symbol": it["symbol"],
                            "side": side,
                            "qty": qty,
                            "limit_price": mid,
                            "status": "REJECTED",
                            "reason": "insufficient_cash",
                        }
                    )
                    continue
                qty = float(max_lot)

        amount = qty * px
        slip = abs(px - mid) * qty
        comm = commission(amount, cost)
        if cash_left is not None:
            if amount + comm > cash_left + 1e-9:
                orders.append(
                    {
                        "symbol": it["symbol"],
                        "side": side,
                        "qty": float(it["qty"]),
                        "limit_price": mid,
                        "status": "REJECTED",
                        "reason": "insufficient_cash",
                    }
                )
                continue
            cash_left -= amount + comm

        orders.append(
            {
                "symbol": it["symbol"],
                "side": side,
                "qty": qty,
                "limit_price": mid,
                "status": "FILLED",
                "reason": "clamped_cash" if qty + 1e-9 < float(it["qty"]) else None,
            }
        )
        fills.append(
            {
                "symbol": it["symbol"],
                "side": side,
                "qty": qty,
                "price": px,
                "amount": amount,
                "commission": comm,
                "stamp_tax": 0.0,
                "slippage_cost": slip,
                "trade_date": trade_date[:10],
            }
        )
    return orders, fills


def compute_residuals(
    *,
    intents: list[dict[str, Any]],
    orders: list[dict[str, Any]],
    fills: list[dict[str, Any]],
    lot_size: int = 100,
) -> list[dict[str, Any]]:
    """
    意图数量 − 成交数量 → 残差（至少一整手才保留）。
    REJECTED / clamped_* 的未成交部分进入 pending。
    """
    lot = max(1, int(lot_size))
    filled_by: dict[tuple[str, str], float] = {}
    for f in fills:
        key = (str(f["symbol"]), str(f["side"]))
        filled_by[key] = filled_by.get(key, 0.0) + float(f["qty"])

    reason_by: dict[tuple[str, str], str | None] = {}
    for o in orders:
        key = (str(o["symbol"]), str(o["side"]))
        # 保留最后一条非空 reason（如 clamped_cash / insufficient_cash）
        reason_by[key] = o.get("reason") or reason_by.get(key)

    residuals: list[dict[str, Any]] = []
    for it in intents:
        sym = str(it["symbol"])
        side = str(it["side"])
        key = (sym, side)
        intended = float(it["qty"])
        filled = float(filled_by.get(key, 0.0))
        rem = intended - filled
        if rem + 1e-9 < lot:
            continue
        reason = it.get("reason") if it.get("reject") else reason_by.get(key)
        if reason is None and rem > 1e-9:
            reason = "unfilled_residual"
        residuals.append(
            {
                "symbol": sym,
                "side": side,
                "qty_remaining": rem,
                "qty_origin": intended,
                "last_reason": reason,
            }
        )
    return residuals


def build_pending_intents(
    *,
    pendings: list[dict[str, Any]],
    bars: dict[str, dict[str, Any]],
    sellable_shares: dict[str, float] | None,
) -> list[dict[str, Any]]:
    """将 open pending 转为当日纸面意图（再套 can_* / T+1）。"""
    intents: list[dict[str, Any]] = []
    for p in pendings:
        sym = str(p["symbol"])
        side = str(p["side"])
        qty = float(p["qty_remaining"])
        b = bars.get(sym) or {}
        px = b.get("close") if b.get("close") is not None else b.get("adj_close")
        if px is None or float(px) <= 0:
            intents.append(
                {
                    "symbol": sym,
                    "side": side,
                    "qty": qty,
                    "reject": True,
                    "reason": "missing_price",
                }
            )
            continue
        px_f = float(px)
        if side == "BUY":
            if int(b.get("can_buy") or 0) != 1:
                intents.append(
                    {
                        "symbol": sym,
                        "side": side,
                        "qty": qty,
                        "reject": True,
                        "reason": "cannot_buy",
                        "mid_price": px_f,
                    }
                )
                continue
            intents.append(
                {
                    "symbol": sym,
                    "side": side,
                    "qty": qty,
                    "reject": False,
                    "mid_price": px_f,
                }
            )
        else:
            if int(b.get("can_sell") if b.get("can_sell") is not None else 1) != 1:
                intents.append(
                    {
                        "symbol": sym,
                        "side": side,
                        "qty": qty,
                        "reject": True,
                        "reason": "cannot_sell",
                        "mid_price": px_f,
                    }
                )
                continue
            intents.append(
                {
                    "symbol": sym,
                    "side": side,
                    "qty": qty,
                    "reject": False,
                    "mid_price": px_f,
                }
            )
    return apply_sellable_limits(intents, sellable_shares=sellable_shares)
