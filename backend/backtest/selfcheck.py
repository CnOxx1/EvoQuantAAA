from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from backtest.engine import run_target_weights
from backtest.models import BacktestRequest, CostParams
from backtest.service import BacktestService


def _bar(
    symbol: str,
    trade_date: str,
    adj_close: float,
    *,
    can_buy: int = 1,
    can_sell: int = 1,
) -> dict:
    return {
        "symbol": symbol,
        "trade_date": trade_date,
        "adj_close": adj_close,
        "can_buy": can_buy,
        "can_sell": can_sell,
    }


def _cost() -> CostParams:
    return CostParams(
        version="mock",
        commission_rate=0.0003,
        min_commission=5.0,
        stamp_tax_rate=0.001,
        slippage_rate=0.0,
        lot_size=100,
    )


def _run_mock_cases() -> None:
    cost = _cost()
    # T+1：首日买入次日才可卖
    bars_t1 = [
        _bar("AAA", "2026-07-01", 10.0),
        _bar("AAA", "2026-07-02", 10.0),
        _bar("BBB", "2026-07-01", 10.0),
        _bar("BBB", "2026-07-02", 10.0),
    ]
    out = run_target_weights(
        bars=bars_t1,
        index_bars=[],
        cost=cost,
        initial_cash=1_000_000.0,
        target_weights={
            "2026-07-01": {"AAA": 1.0},
            "2026-07-02": {"BBB": 1.0},
        },
        trade_reason="MOCK_T1",
    )
    sells_d2 = [
        t for t in out.trades if t["side"] == "SELL" and t["trade_date"] == "2026-07-02"
    ]
    assert sells_d2, "T+1 次日应能卖出 AAA"
    assert all(t["symbol"] == "AAA" for t in sells_d2)

    # 冲击成本：有 ADV 时买入价应高于 flat
    bars_imp = [
        {
            "symbol": "AAA",
            "trade_date": "2026-07-01",
            "close": 10.0,
            "adj_close": 10.0,
            "can_buy": 1,
            "can_sell": 1,
            "adv": 1_000_000.0,
        }
    ]
    out_flat = run_target_weights(
        bars=bars_imp,
        index_bars=[],
        cost=_cost(),
        initial_cash=100_000.0,
        target_weights={"2026-07-01": {"AAA": 1.0}},
    )
    out_imp = run_target_weights(
        bars=bars_imp,
        index_bars=[],
        cost=CostParams(
            version="mock_imp",
            commission_rate=0.0,
            min_commission=0.0,
            stamp_tax_rate=0.0,
            slippage_rate=0.0,
            lot_size=100,
            impact_model="sqrt_adv",
            impact_coef=0.1,
        ),
        initial_cash=100_000.0,
        target_weights={"2026-07-01": {"AAA": 1.0}},
    )
    assert out_imp.trades[0]["price"] > out_flat.trades[0]["price"]

    # 同日买入不可卖（目标先买后同日切仓）
    bars_same = [
        _bar("AAA", "2026-07-01", 10.0),
        _bar("BBB", "2026-07-01", 10.0),
    ]
    out2 = run_target_weights(
        bars=bars_same,
        index_bars=[],
        cost=cost,
        initial_cash=1_000_000.0,
        target_weights={"2026-07-01": {"AAA": 1.0, "BBB": 0.0}},
        trade_reason="MOCK_SAME",
    )
    assert not any(t["side"] == "SELL" for t in out2.trades), "当日买入不得卖出"

    # can_sell=0 当日不成交，次日顺延
    bars_limit = [
        _bar("AAA", "2026-07-01", 10.0),
        _bar("BBB", "2026-07-01", 10.0),
        _bar("AAA", "2026-07-02", 10.0, can_sell=0),
        _bar("BBB", "2026-07-02", 10.0),
        _bar("AAA", "2026-07-03", 10.0),
        _bar("BBB", "2026-07-03", 10.0),
    ]
    out3 = run_target_weights(
        bars=bars_limit,
        index_bars=[],
        cost=cost,
        initial_cash=1_000_000.0,
        target_weights={
            "2026-07-01": {"AAA": 1.0},
            "2026-07-02": {"BBB": 1.0},
        },
        trade_reason="MOCK_LIMIT",
    )
    assert not any(
        t["side"] == "SELL" and t["trade_date"] == "2026-07-02" for t in out3.trades
    ), "跌停日不得卖出"
    assert any(
        t["side"] == "SELL" and t["trade_date"] == "2026-07-03" and t["symbol"] == "AAA"
        for t in out3.trades
    ), "跌停解除后应顺延卖出"

    # 印花税仅卖出
    sells = [t for t in out3.trades if t["side"] == "SELL"]
    buys = [t for t in out3.trades if t["side"] == "BUY"]
    assert sells and buys
    for t in sells:
        stamp = t["amount"] * cost.stamp_tax_rate
        # cost = commission + stamp；佣金至少 min_commission
        assert t["cost"] + 1e-9 >= stamp, "卖出成本须含印花税"
    for t in buys:
        assert t["cost"] <= max(t["amount"] * cost.commission_rate, cost.min_commission) + 1e-6

    print("mock_cases=ok")


def main() -> int:
    _run_mock_cases()

    try:
        from shared.db import get_conn
    except Exception as exc:
        print(f"status=ok message=mock_only db_skip={exc}")
        return 0

    with get_conn() as conn:
        n = int(
            conn.execute(
                "SELECT COUNT(*) AS n FROM processed_equity_bar_1d"
            ).fetchone()["n"]
        )
    if n < 2:
        print("status=ok message=mock_ok db_skip=需要 processed_equity_bar_1d")
        return 0

    result = BacktestService().run(
        BacktestRequest(
            strategy_code="EW_HOLD",
            start="2026-07-01",
            end="2026-07-23",
            symbols=["600000", "000001"],
            universe_code=None,
            require_dq=True,
        )
    )
    print(
        f"status={result.status} run_id={result.run_id} "
        f"ret={result.total_return:.6f} bench={result.benchmark_return:.6f} "
        f"mdd={result.max_drawdown:.6f} trades={result.trade_count}"
    )
    if result.message:
        print(f"message={result.message}")
    if result.status != "committed":
        return 2

    with get_conn() as conn:
        nav_n = int(
            conn.execute(
                "SELECT COUNT(*) AS n FROM backtest_nav WHERE run_id=?",
                (result.run_id,),
            ).fetchone()["n"]
        )
        tr_n = int(
            conn.execute(
                "SELECT COUNT(*) AS n FROM backtest_trade WHERE run_id=?",
                (result.run_id,),
            ).fetchone()["n"]
        )
    assert nav_n >= 2, "nav 行不足"
    assert tr_n >= 1, "应有成交"
    print(f"nav_rows={nav_n} trade_rows={tr_n}")
    print("status=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
