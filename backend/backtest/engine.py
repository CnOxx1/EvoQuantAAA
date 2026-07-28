from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from backtest.models import CostParams
from shared.impact import slipped_fill_price


@dataclass
class EngineOutput:
    nav_rows: list[dict[str, Any]] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)
    final_nav: float = 0.0
    total_return: float = 0.0
    benchmark_return: float = 0.0
    max_drawdown: float = 0.0
    symbols_used: list[str] = field(default_factory=list)


def _trade_px(bar: dict[str, Any] | None) -> float | None:
    """成交/整手定价：优先未复权 close，缺则 adj_close。"""
    if not bar:
        return None
    px = bar.get("close")
    if px is None:
        px = bar.get("adj_close")
    if px is None:
        return None
    v = float(px)
    return v if v > 0 else None


def _slip_fill_px(
    *,
    side: str,
    mid: float,
    qty: float,
    cost: CostParams,
    bar: dict[str, Any] | None,
) -> float:
    adv = None
    if bar is not None and bar.get("adv") is not None:
        try:
            adv = float(bar["adv"])
        except (TypeError, ValueError):
            adv = None
    return slipped_fill_price(
        side=side,
        mid=mid,
        base_slippage=cost.slippage_rate,
        impact_model=getattr(cost, "impact_model", "flat"),
        impact_coef=getattr(cost, "impact_coef", 0.0),
        qty=qty,
        adv=adv,
    )


def _commission(amount: float, cost: CostParams) -> float:
    return max(abs(amount) * cost.commission_rate, cost.min_commission)


def _mark_to_market(
    positions: dict[str, float], day_bars: dict[str, dict[str, Any]]
) -> float:
    mv = 0.0
    for sym, sh in positions.items():
        if sh <= 0:
            continue
        px = _trade_px(day_bars.get(sym))
        if px is not None:
            mv += sh * px
    return mv


def _lot_shares(value: float, px: float, lot: int) -> int:
    if px <= 0 or lot <= 0 or value <= 0:
        return 0
    return int(value // (px * lot)) * lot


def _sellable_from_lots(
    lots: list[dict[str, Any]], *, symbol: str, as_of: str
) -> float:
    day = as_of[:10]
    return sum(
        float(l["qty"])
        for l in lots
        if str(l["symbol"]) == symbol and str(l["buy_date"])[:10] < day and float(l["qty"]) > 0
    )


def _fifo_take(
    lots: list[dict[str, Any]], *, symbol: str, qty: float, as_of: str
) -> float:
    """从 lots 按 FIFO 扣减可卖量，返回实际扣减。"""
    need = float(qty)
    if need <= 0:
        return 0.0
    day = as_of[:10]
    idxs = [
        i
        for i, l in enumerate(lots)
        if str(l["symbol"]) == symbol
        and float(l["qty"]) > 0
        and str(l["buy_date"])[:10] < day
    ]
    idxs.sort(key=lambda i: (str(lots[i]["buy_date"])[:10], i))
    taken = 0.0
    for i in idxs:
        if need <= 1e-12:
            break
        rem = float(lots[i]["qty"])
        use = min(rem, need)
        lots[i]["qty"] = rem - use
        need -= use
        taken += use
    # 清理空 lot
    lots[:] = [l for l in lots if float(l["qty"]) > 1e-12]
    return taken


def _aligned_to_target(
    *,
    positions: dict[str, float],
    day_bars: dict[str, dict[str, Any]],
    cash: float,
    target: dict[str, float],
    cost: CostParams,
) -> bool:
    """目标权重是否已在整手精度内对齐（无法再交易则视为对齐）。"""
    mv = _mark_to_market(positions, day_bars)
    nav = cash + mv
    if nav <= 0:
        return True
    symbols = set(positions) | set(target)
    for sym in symbols:
        tw = float(target.get(sym, 0.0))
        px = _trade_px(day_bars.get(sym))
        if px is None:
            if positions.get(sym, 0.0) > 0 and tw <= 0:
                return False
            continue
        cur = float(positions.get(sym, 0.0))
        want = _lot_shares(nav * tw, px, cost.lot_size)
        if abs(cur - want) >= cost.lot_size:
            return False
    return True


def run_target_weights(
    *,
    bars: list[dict[str, Any]],
    index_bars: list[dict[str, Any]],
    cost: CostParams,
    initial_cash: float,
    target_weights: dict[str, dict[str, float]],
    trade_reason: str = "REBALANCE",
) -> EngineOutput:
    """
    通用日频撮合：按目标权重调仓。

    - 目标日写入 pending；未对齐时逐日重试（跌停/T+1 顺延），对齐后清空以免日更微扰
    - 先卖后买；卖出计佣金+印花税；买入仅佣金；滑点计入成交价
    - T+1：按买入批次 FIFO（加仓不合并最早 buy_date）
    - 成交价优先未复权 close
    """
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for b in bars:
        by_date[str(b["trade_date"])[:10]].append(b)
    dates = sorted(by_date.keys())
    if not dates:
        raise RuntimeError("无 processed 日线可用于回测")

    index_close = {
        str(r["trade_date"])[:10]: float(r["close"])
        for r in index_bars
        if r.get("close") is not None
    }
    first_idx = next((index_close[d] for d in dates if d in index_close), None)

    cash = float(initial_cash)
    positions: dict[str, float] = {}
    lots: list[dict[str, Any]] = []  # {symbol, buy_date, qty}
    trades: list[dict[str, Any]] = []
    nav_rows: list[dict[str, Any]] = []
    peak = initial_cash
    max_dd = 0.0
    symbols_used: set[str] = set()
    pending: dict[str, float] | None = None

    for d in dates:
        day_bars = {str(b["symbol"]): b for b in by_date[d]}

        if d in target_weights:
            pending = {str(k): float(v) for k, v in target_weights[d].items()}

        if pending is not None:
            mv0 = _mark_to_market(positions, day_bars)
            nav0 = cash + mv0

            # ---- 卖出 ----
            sell_plan: list[tuple[str, float]] = []
            for sym in sorted(set(positions) | set(pending)):
                tw = float(pending.get(sym, 0.0))
                cur = float(positions.get(sym, 0.0))
                px_ref = _trade_px(day_bars.get(sym))
                if cur <= 0 or px_ref is None:
                    continue
                want = _lot_shares(nav0 * tw, px_ref, cost.lot_size) if tw > 0 else 0
                delta = want - cur
                if delta < 0:
                    sell_plan.append((sym, -delta))

            for sym, shares_to_sell in sell_plan:
                b = day_bars[sym]
                if int(b.get("can_sell") or 0) != 1:
                    continue
                avail = _sellable_from_lots(lots, symbol=sym, as_of=d)
                sh = min(float(positions.get(sym, 0.0)), shares_to_sell, avail)
                sh = int(sh // cost.lot_size) * cost.lot_size
                if sh <= 0:
                    continue
                px_ref = _trade_px(b)
                if px_ref is None:
                    continue
                px = _slip_fill_px(
                    side="SELL", mid=px_ref, qty=sh, cost=cost, bar=b
                )
                amount = sh * px
                fee_c = _commission(amount, cost)
                fee_stamp = amount * cost.stamp_tax_rate
                fee = fee_c + fee_stamp
                taken = _fifo_take(lots, symbol=sym, qty=sh, as_of=d)
                if abs(taken - sh) > 1e-6:
                    continue
                cash += amount - fee
                positions[sym] = positions.get(sym, 0.0) - sh
                if positions[sym] <= 1e-12:
                    positions.pop(sym, None)
                trades.append(
                    {
                        "trade_date": d,
                        "symbol": sym,
                        "side": "SELL",
                        "shares": float(sh),
                        "price": px,
                        "amount": amount,
                        "cost": fee,
                        "reason": trade_reason,
                    }
                )

            # ---- 买入（按目标差额；现金不足按比例缩量）----
            mv1 = _mark_to_market(positions, day_bars)
            nav1 = cash + mv1
            buy_orders: list[tuple[str, int, float]] = []  # sym, shares, mid
            for sym in sorted(pending):
                tw = float(pending.get(sym, 0.0))
                if tw <= 0:
                    continue
                b = day_bars.get(sym)
                px_ref = _trade_px(b)
                if px_ref is None:
                    continue
                if int(b.get("can_buy") or 0) != 1:
                    continue
                # 整手用 mid；冲击在成交时按实际股数重算
                px_est = _slip_fill_px(
                    side="BUY", mid=px_ref, qty=0, cost=cost, bar=b
                )
                cur = float(positions.get(sym, 0.0))
                want = _lot_shares(nav1 * tw, px_est, cost.lot_size)
                need = want - cur
                need = int(need // cost.lot_size) * cost.lot_size
                if need > 0:
                    buy_orders.append((sym, need, px_ref))

            if buy_orders:
                gross = 0.0
                priced: list[tuple[str, int, float, float]] = []
                for sym, sh, mid in buy_orders:
                    px = _slip_fill_px(
                        side="BUY",
                        mid=mid,
                        qty=sh,
                        cost=cost,
                        bar=day_bars.get(sym),
                    )
                    amt = sh * px
                    gross += amt + _commission(amt, cost)
                    priced.append((sym, sh, mid, px))
                scale = 1.0
                if gross > cash and gross > 0:
                    scale = max(0.0, cash / gross)

                for sym, sh, mid, px0 in priced:
                    adj_sh = int((sh * scale) // cost.lot_size) * cost.lot_size
                    if adj_sh <= 0:
                        continue
                    px = _slip_fill_px(
                        side="BUY",
                        mid=mid,
                        qty=adj_sh,
                        cost=cost,
                        bar=day_bars.get(sym),
                    )
                    amount = adj_sh * px
                    fee = _commission(amount, cost)
                    if amount + fee > cash + 1e-9:
                        adj_sh = (
                            int((cash - cost.min_commission) // (px * cost.lot_size))
                            * cost.lot_size
                        )
                        if adj_sh <= 0:
                            continue
                        px = _slip_fill_px(
                            side="BUY",
                            mid=mid,
                            qty=adj_sh,
                            cost=cost,
                            bar=day_bars.get(sym),
                        )
                        amount = adj_sh * px
                        fee = _commission(amount, cost)
                    if amount + fee > cash + 1e-9:
                        continue
                    cash -= amount + fee
                    positions[sym] = positions.get(sym, 0.0) + adj_sh
                    lots.append(
                        {"symbol": sym, "buy_date": d, "qty": float(adj_sh)}
                    )
                    symbols_used.add(sym)
                    trades.append(
                        {
                            "trade_date": d,
                            "symbol": sym,
                            "side": "BUY",
                            "shares": float(adj_sh),
                            "price": px,
                            "amount": amount,
                            "cost": fee,
                            "reason": trade_reason,
                        }
                    )

            if _aligned_to_target(
                positions=positions,
                day_bars=day_bars,
                cash=cash,
                target=pending,
                cost=cost,
            ):
                pending = None

        mv = _mark_to_market(positions, day_bars)
        nav = cash + mv
        peak = max(peak, nav)
        if peak > 0:
            max_dd = max(max_dd, (peak - nav) / peak)
        bnav = None
        if first_idx and d in index_close and first_idx != 0:
            bnav = index_close[d] / first_idx * initial_cash
        nav_rows.append(
            {
                "trade_date": d,
                "nav": nav,
                "cash": cash,
                "market_value": mv,
                "benchmark_nav": bnav,
            }
        )

    final_nav = nav_rows[-1]["nav"] if nav_rows else initial_cash
    total_ret = final_nav / initial_cash - 1.0 if initial_cash else 0.0
    bench_ret = 0.0
    if first_idx and dates and dates[-1] in index_close and first_idx != 0:
        bench_ret = index_close[dates[-1]] / first_idx - 1.0

    if not trades:
        raise RuntimeError("未能建仓：检查 can_buy / 资金 / 整手约束 / 目标权重")

    return EngineOutput(
        nav_rows=nav_rows,
        trades=trades,
        final_nav=final_nav,
        total_return=total_ret,
        benchmark_return=bench_ret,
        max_drawdown=max_dd,
        symbols_used=sorted(symbols_used),
    )


def build_ew_target_weights(
    *,
    bars: list[dict[str, Any]],
    rebalance_days: int = 0,
) -> dict[str, dict[str, float]]:
    """
    等权目标：首个可买日建仓；rebalance_days>0 时每隔 N 个交易日再平衡。
    再平衡日标的 = 当日有行情且 can_buy=1 的集合（与已持仓无关的新票也可进）。
    """
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for b in bars:
        by_date[str(b["trade_date"])[:10]].append(b)
    dates = sorted(by_date.keys())
    targets: dict[str, dict[str, float]] = {}
    entry_idx: int | None = None

    for i, d in enumerate(dates):
        buyable = [
            str(b["symbol"])
            for b in by_date[d]
            if int(b.get("can_buy") or 0) == 1 and _trade_px(b) is not None
        ]
        buyable = sorted(set(buyable))
        if not buyable:
            continue
        if entry_idx is None:
            entry_idx = i
            w = 1.0 / len(buyable)
            targets[d] = {s: w for s in buyable}
            continue
        if rebalance_days > 0 and (i - entry_idx) % rebalance_days == 0:
            w = 1.0 / len(buyable)
            targets[d] = {s: w for s in buyable}
    return targets


def run_ew_hold(
    *,
    bars: list[dict[str, Any]],
    index_bars: list[dict[str, Any]],
    cost: CostParams,
    initial_cash: float,
) -> EngineOutput:
    """等权买入持有：首日建仓后不再主动调仓（未成交目标会顺延至对齐）。"""
    targets = build_ew_target_weights(bars=bars, rebalance_days=0)
    return run_target_weights(
        bars=bars,
        index_bars=index_bars,
        cost=cost,
        initial_cash=initial_cash,
        target_weights=targets,
        trade_reason="EW_HOLD_ENTRY",
    )


def run_ew_rebalance(
    *,
    bars: list[dict[str, Any]],
    index_bars: list[dict[str, Any]],
    cost: CostParams,
    initial_cash: float,
    rebalance_days: int,
) -> EngineOutput:
    if rebalance_days <= 0:
        raise ValueError("EW_REBALANCE 需要 rebalance_days > 0")
    targets = build_ew_target_weights(bars=bars, rebalance_days=rebalance_days)
    return run_target_weights(
        bars=bars,
        index_bars=index_bars,
        cost=cost,
        initial_cash=initial_cash,
        target_weights=targets,
        trade_reason="EW_REBALANCE",
    )


def build_factor_top_n_targets(
    *,
    bars: list[dict[str, Any]],
    factor_rows: list[dict[str, Any]],
    top_n: int,
    rebalance_days: int,
) -> dict[str, dict[str, float]]:
    """
    调仓日用「前一交易日」因子值取 top N 等权。
    避免用当日收盘信息当日交易（无前视）。
    """
    if top_n <= 0:
        raise ValueError("top_n 必须 > 0")
    if rebalance_days <= 0:
        raise ValueError("FACTOR_TOP_N 需要 rebalance_days > 0")

    by_date: dict[str, set[str]] = defaultdict(set)
    for b in bars:
        if _trade_px(b) is None:
            continue
        by_date[str(b["trade_date"])[:10]].add(str(b["symbol"]))
    dates = sorted(by_date.keys())
    if len(dates) < 2:
        return {}

    factor_by_date: dict[str, dict[str, float]] = defaultdict(dict)
    for r in factor_rows:
        if r.get("value") is None:
            continue
        factor_by_date[str(r["trade_date"])[:10]][str(r["symbol"])] = float(r["value"])

    targets: dict[str, dict[str, float]] = {}
    entry_idx: int | None = None
    for i, d in enumerate(dates):
        if i == 0:
            continue  # 无前一日因子
        prev = dates[i - 1]
        fmap = factor_by_date.get(prev) or {}
        # 仅在当日有行情的标的中选
        candidates = [
            (sym, val)
            for sym, val in fmap.items()
            if sym in by_date[d]
        ]
        if len(candidates) < 1:
            continue
        if entry_idx is None:
            entry_idx = i
        elif (i - entry_idx) % rebalance_days != 0:
            continue
        candidates.sort(key=lambda x: x[1], reverse=True)
        picked = [s for s, _ in candidates[:top_n]]
        if not picked:
            continue
        w = 1.0 / len(picked)
        targets[d] = {s: w for s in picked}
    return targets


def run_factor_top_n(
    *,
    bars: list[dict[str, Any]],
    index_bars: list[dict[str, Any]],
    cost: CostParams,
    initial_cash: float,
    factor_rows: list[dict[str, Any]],
    top_n: int,
    rebalance_days: int,
) -> EngineOutput:
    targets = build_factor_top_n_targets(
        bars=bars,
        factor_rows=factor_rows,
        top_n=top_n,
        rebalance_days=rebalance_days,
    )
    if not targets:
        raise RuntimeError(
            "无法构建 FACTOR_TOP_N 目标权重：检查因子是否已落库、区间是否足够"
        )
    return run_target_weights(
        bars=bars,
        index_bars=index_bars,
        cost=cost,
        initial_cash=initial_cash,
        target_weights=targets,
        trade_reason="FACTOR_TOP_N",
    )
