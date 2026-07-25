from __future__ import annotations

from backtest.engine import (
    build_factor_top_n_targets,
    run_ew_rebalance,
    run_target_weights,
)
from backtest.models import CostParams


def _cost(**kwargs) -> CostParams:
    base = dict(
        version="test",
        commission_rate=0.0003,
        min_commission=5.0,
        stamp_tax_rate=0.001,
        slippage_rate=0.0,
        lot_size=100,
    )
    base.update(kwargs)
    return CostParams(**base)


def _bar(sym, d, px, can_buy=1, can_sell=1):
    return {
        "symbol": sym,
        "trade_date": d,
        "adj_close": px,
        "can_buy": can_buy,
        "can_sell": can_sell,
    }


def test_t1_blocks_same_day_sell():
    cost = _cost()
    bars = [_bar("A", "2026-07-01", 10.0), _bar("B", "2026-07-01", 10.0)]
    out = run_target_weights(
        bars=bars,
        index_bars=[],
        cost=cost,
        initial_cash=1_000_000,
        target_weights={"2026-07-01": {"A": 0.5, "B": 0.5}},
    )
    assert not any(t["side"] == "SELL" for t in out.trades)


def test_t1_allows_next_day_sell():
    cost = _cost()
    bars = [
        _bar("A", "2026-07-01", 10.0),
        _bar("B", "2026-07-01", 10.0),
        _bar("A", "2026-07-02", 10.0),
        _bar("B", "2026-07-02", 10.0),
    ]
    out = run_target_weights(
        bars=bars,
        index_bars=[],
        cost=cost,
        initial_cash=1_000_000,
        target_weights={
            "2026-07-01": {"A": 1.0},
            "2026-07-02": {"B": 1.0},
        },
    )
    assert any(
        t["side"] == "SELL" and t["symbol"] == "A" and t["trade_date"] == "2026-07-02"
        for t in out.trades
    )


def test_can_sell_zero_defers_sell():
    cost = _cost()
    bars = [
        _bar("A", "2026-07-01", 10.0),
        _bar("B", "2026-07-01", 10.0),
        _bar("A", "2026-07-02", 10.0, can_sell=0),
        _bar("B", "2026-07-02", 10.0),
        _bar("A", "2026-07-03", 10.0),
        _bar("B", "2026-07-03", 10.0),
    ]
    out = run_target_weights(
        bars=bars,
        index_bars=[],
        cost=cost,
        initial_cash=1_000_000,
        target_weights={
            "2026-07-01": {"A": 1.0},
            "2026-07-02": {"B": 1.0},
        },
    )
    assert not any(t["side"] == "SELL" and t["trade_date"] == "2026-07-02" for t in out.trades)
    assert any(t["side"] == "SELL" and t["trade_date"] == "2026-07-03" for t in out.trades)


def test_stamp_tax_sell_only():
    cost = _cost(commission_rate=0.0, min_commission=0.0, stamp_tax_rate=0.001)
    bars = [
        _bar("A", "2026-07-01", 10.0),
        _bar("B", "2026-07-01", 10.0),
        _bar("A", "2026-07-02", 10.0),
        _bar("B", "2026-07-02", 10.0),
    ]
    out = run_target_weights(
        bars=bars,
        index_bars=[],
        cost=cost,
        initial_cash=1_000_000,
        target_weights={
            "2026-07-01": {"A": 1.0},
            "2026-07-02": {"B": 1.0},
        },
    )
    for t in out.trades:
        if t["side"] == "BUY":
            assert t["cost"] == 0.0
        else:
            assert abs(t["cost"] - t["amount"] * 0.001) < 1e-6


def test_lot_size_rounding():
    cost = _cost(lot_size=100, commission_rate=0.0, min_commission=0.0, stamp_tax_rate=0.0)
    bars = [_bar("A", "2026-07-01", 7.0)]
    out = run_target_weights(
        bars=bars,
        index_bars=[],
        cost=cost,
        initial_cash=10_000,
        target_weights={"2026-07-01": {"A": 1.0}},
    )
    buy = out.trades[0]
    assert buy["shares"] % 100 == 0
    assert buy["shares"] * 7.0 <= 10_000


def test_no_cash_overdraft():
    cost = _cost()
    bars = [
        _bar("A", "2026-07-01", 10.0),
        _bar("B", "2026-07-01", 10.0),
    ]
    out = run_target_weights(
        bars=bars,
        index_bars=[],
        cost=cost,
        initial_cash=50_000,
        target_weights={"2026-07-01": {"A": 0.5, "B": 0.5}},
    )
    spent = sum(t["amount"] + t["cost"] for t in out.trades if t["side"] == "BUY")
    assert spent <= 50_000 + 1e-6
    assert out.nav_rows[-1]["cash"] >= -1e-6


def test_rebalance_weights_near_target():
    cost = _cost(commission_rate=0.0, min_commission=0.0, stamp_tax_rate=0.0)
    dates = [f"2026-07-{i:02d}" for i in range(1, 11)]
    bars = []
    for d in dates:
        bars.append(_bar("A", d, 10.0))
        bars.append(_bar("B", d, 10.0))
    out = run_ew_rebalance(
        bars=bars,
        index_bars=[],
        cost=cost,
        initial_cash=1_000_000,
        rebalance_days=5,
    )
    last = {r["trade_date"]: r for r in out.nav_rows}["2026-07-10"]
    # 双票等权，现金接近 0
    assert last["market_value"] / last["nav"] > 0.95
    assert any(t["side"] == "SELL" for t in out.trades) or len(
        {t["trade_date"] for t in out.trades if t["side"] == "BUY"}
    ) >= 1


def test_factor_top_n_uses_previous_day_factor():
    dates = [f"2026-07-{i:02d}" for i in range(1, 6)]
    bars = []
    for d in dates:
        for s in ("A", "B", "C"):
            bars.append(_bar(s, d, 10.0))
    # 07-01: A 最高；07-02: C 最高 — 调仓日 07-02 应使用 07-01 的因子 → 选 A
    factor_rows = [
        {"symbol": "A", "trade_date": "2026-07-01", "value": 3.0},
        {"symbol": "B", "trade_date": "2026-07-01", "value": 2.0},
        {"symbol": "C", "trade_date": "2026-07-01", "value": 1.0},
        {"symbol": "A", "trade_date": "2026-07-02", "value": 0.0},
        {"symbol": "B", "trade_date": "2026-07-02", "value": 0.0},
        {"symbol": "C", "trade_date": "2026-07-02", "value": 9.0},
    ]
    targets = build_factor_top_n_targets(
        bars=bars, factor_rows=factor_rows, top_n=1, rebalance_days=1
    )
    assert "2026-07-02" in targets
    assert list(targets["2026-07-02"].keys()) == ["A"]
    assert "C" not in targets["2026-07-02"]
