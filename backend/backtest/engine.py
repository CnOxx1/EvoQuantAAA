from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from backtest.models import CostParams


@dataclass
class EngineOutput:
    nav_rows: list[dict[str, Any]] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)
    final_nav: float = 0.0
    total_return: float = 0.0
    benchmark_return: float = 0.0
    max_drawdown: float = 0.0
    symbols_used: list[str] = field(default_factory=list)


def _commission(amount: float, cost: CostParams) -> float:
    return max(abs(amount) * cost.commission_rate, cost.min_commission)


def run_ew_hold(
    *,
    bars: list[dict[str, Any]],
    index_bars: list[dict[str, Any]],
    cost: CostParams,
    initial_cash: float,
) -> EngineOutput:
    """
    P0 等权买入持有：
    - 首个可交易日按收盘价（含滑点）等权建仓；受 can_buy、整手约束
    - T+1：建仓日不可卖（本策略持有到期，仅在需要时检查 can_sell）
    - 每日以 adj_close 计价 NAV；基准用指数收盘归一
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
    positions: dict[str, float] = {}  # shares
    buy_dates: dict[str, str] = {}
    trades: list[dict[str, Any]] = []
    nav_rows: list[dict[str, Any]] = []
    peak = initial_cash
    max_dd = 0.0
    entered = False
    symbols_used: list[str] = []

    for d in dates:
        day_bars = {str(b["symbol"]): b for b in by_date[d]}

        # 建仓：第一个交易日收盘等权买入可买标的
        if not entered:
            buyable = [
                b
                for b in day_bars.values()
                if int(b.get("can_buy") or 0) == 1
                and b.get("adj_close") is not None
                and float(b["adj_close"]) > 0
            ]
            if buyable:
                n = len(buyable)
                budget = cash / n
                for b in buyable:
                    sym = str(b["symbol"])
                    px = float(b["adj_close"]) * (1.0 + cost.slippage_rate)
                    lot = cost.lot_size
                    shares = int(budget // (px * lot)) * lot
                    if shares <= 0:
                        continue
                    amount = shares * px
                    fee = _commission(amount, cost)
                    if amount + fee > cash:
                        shares = int((cash - cost.min_commission) // (px * lot)) * lot
                        if shares <= 0:
                            continue
                        amount = shares * px
                        fee = _commission(amount, cost)
                    if amount + fee > cash:
                        continue
                    cash -= amount + fee
                    positions[sym] = positions.get(sym, 0.0) + shares
                    buy_dates[sym] = d
                    symbols_used.append(sym)
                    trades.append(
                        {
                            "trade_date": d,
                            "symbol": sym,
                            "side": "BUY",
                            "shares": float(shares),
                            "price": px,
                            "amount": amount,
                            "cost": fee,
                            "reason": "EW_HOLD_ENTRY",
                        }
                    )
                entered = True
                symbols_used = sorted(set(symbols_used))

        # 估值
        mv = 0.0
        for sym, sh in positions.items():
            b = day_bars.get(sym)
            if b and b.get("adj_close") is not None:
                mv += sh * float(b["adj_close"])
            else:
                # 无行情日暂用最近不可得则跳过计入 0（样本期应齐全）
                pass
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
        raise RuntimeError("未能建仓：检查 can_buy / 资金 / 整手约束")

    return EngineOutput(
        nav_rows=nav_rows,
        trades=trades,
        final_nav=final_nav,
        total_return=total_ret,
        benchmark_return=bench_ret,
        max_drawdown=max_dd,
        symbols_used=symbols_used,
    )
