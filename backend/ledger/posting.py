from __future__ import annotations

"""过账纯函数：fill → 分录意图；T+1 可卖按 buy_date < as_of。"""

from typing import Any


def sellable_qty(
    lots: list[dict[str, Any]], *, symbol: str, as_of: str
) -> float:
    """T+1：buy_date < as_of 的剩余数量之和。"""
    total = 0.0
    day = as_of[:10]
    for lot in lots:
        if str(lot.get("symbol")) != symbol:
            continue
        rem = float(lot.get("qty_remaining") or 0)
        if rem <= 0:
            continue
        if str(lot.get("buy_date"))[:10] < day:
            total += rem
    return total


def apply_fifo_sell(
    lots: list[dict[str, Any]], *, symbol: str, qty: float, as_of: str
) -> tuple[list[dict[str, Any]], float]:
    """
    从可卖批次 FIFO 扣减。返回 (更新后的 lots 拷贝, 实际扣减量)。
    若可卖不足，实际扣减 < qty（调用方应先校验）。
    """
    need = float(qty)
    if need <= 0:
        return [dict(x) for x in lots], 0.0
    day = as_of[:10]
    out = [dict(x) for x in lots]
    # 仅可卖：buy_date < as_of，按 buy_date、created 排序
    idxs = [
        i
        for i, lot in enumerate(out)
        if str(lot.get("symbol")) == symbol
        and float(lot.get("qty_remaining") or 0) > 0
        and str(lot.get("buy_date"))[:10] < day
    ]
    idxs.sort(
        key=lambda i: (
            str(out[i].get("buy_date"))[:10],
            str(out[i].get("created_at") or ""),
            str(out[i].get("lot_id") or ""),
        )
    )
    taken = 0.0
    for i in idxs:
        if need <= 1e-12:
            break
        rem = float(out[i]["qty_remaining"])
        use = min(rem, need)
        out[i]["qty_remaining"] = rem - use
        need -= use
        taken += use
    return out, taken


def build_fill_entries(fills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    将 fill 转为分录意图（未写库）。
    BUY: CASH_OUT(amount+commission), POSITION_IN(qty)
    SELL: CASH_IN(amount-commission-stamp_tax), POSITION_OUT(qty)
    """
    entries: list[dict[str, Any]] = []
    for f in fills:
        side = str(f["side"]).upper()
        symbol = str(f["symbol"])
        qty = float(f["qty"])
        amount = float(f["amount"])
        commission = float(f.get("commission") or 0)
        stamp = float(f.get("stamp_tax") or 0)
        trade_date = str(f["trade_date"])[:10]
        fill_id = str(f.get("fill_id") or "")

        if side == "BUY":
            cash_out = amount + commission
            entries.append(
                {
                    "entry_type": "CASH_OUT",
                    "symbol": None,
                    "qty": None,
                    "amount": -cash_out,
                    "fill_id": fill_id,
                    "trade_date": trade_date,
                    "memo": f"BUY {symbol} amount+commission",
                }
            )
            entries.append(
                {
                    "entry_type": "POSITION_IN",
                    "symbol": symbol,
                    "qty": qty,
                    "amount": amount,
                    "fill_id": fill_id,
                    "trade_date": trade_date,
                    "memo": f"BUY {symbol} shares",
                }
            )
        elif side == "SELL":
            cash_in = amount - commission - stamp
            entries.append(
                {
                    "entry_type": "CASH_IN",
                    "symbol": None,
                    "qty": None,
                    "amount": cash_in,
                    "fill_id": fill_id,
                    "trade_date": trade_date,
                    "memo": f"SELL {symbol} amount-fees",
                }
            )
            entries.append(
                {
                    "entry_type": "POSITION_OUT",
                    "symbol": symbol,
                    "qty": -qty,
                    "amount": -amount,
                    "fill_id": fill_id,
                    "trade_date": trade_date,
                    "memo": f"SELL {symbol} shares",
                }
            )
        else:
            raise ValueError(f"未知 side: {side}")
    return entries


def project_balances(
    *,
    opening_cash: float,
    fills: list[dict[str, Any]],
) -> tuple[float, dict[str, float], list[dict[str, Any]], list[str]]:
    """
    从空仓 + opening_cash 投影过账结果（用于单测）。
    返回 (cash, positions, lots, errors)。
    """
    cash = float(opening_cash)
    positions: dict[str, float] = {}
    lots: list[dict[str, Any]] = []
    errors: list[str] = []

    # 按 trade_date 再 fill 顺序
    ordered = sorted(
        fills,
        key=lambda f: (str(f["trade_date"])[:10], str(f.get("fill_id") or "")),
    )
    for f in ordered:
        side = str(f["side"]).upper()
        symbol = str(f["symbol"])
        qty = float(f["qty"])
        amount = float(f["amount"])
        commission = float(f.get("commission") or 0)
        stamp = float(f.get("stamp_tax") or 0)
        trade_date = str(f["trade_date"])[:10]

        if side == "BUY":
            cost = amount + commission
            if cash + 1e-9 < cost:
                errors.append(f"现金不足 BUY {symbol}: need={cost:.2f} cash={cash:.2f}")
                continue
            cash -= cost
            positions[symbol] = positions.get(symbol, 0.0) + qty
            lots.append(
                {
                    "lot_id": f"lot_{symbol}_{trade_date}_{len(lots)}",
                    "symbol": symbol,
                    "buy_date": trade_date,
                    "qty_remaining": qty,
                    "created_at": trade_date,
                }
            )
        else:
            sellable = sellable_qty(lots, symbol=symbol, as_of=trade_date)
            if sellable + 1e-9 < qty:
                errors.append(
                    f"T+1 可卖不足 SELL {symbol}: need={qty} sellable={sellable}"
                )
                continue
            lots, taken = apply_fifo_sell(
                lots, symbol=symbol, qty=qty, as_of=trade_date
            )
            if abs(taken - qty) > 1e-9:
                errors.append(f"FIFO 扣减异常 {symbol}")
                continue
            cash += amount - commission - stamp
            positions[symbol] = positions.get(symbol, 0.0) - qty
            if abs(positions[symbol]) < 1e-12:
                positions.pop(symbol, None)

    return cash, positions, lots, errors
