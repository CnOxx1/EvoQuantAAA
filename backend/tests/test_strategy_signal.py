from __future__ import annotations

from signal_prod.weights import build_factor_top_n_weights
from strategy_registry.transitions import can_transition, validate_transition


def test_transition_happy_path():
    assert can_transition("DRAFT", "BACKTESTED")
    assert can_transition("BACKTESTED", "PAPER")
    assert can_transition("PAPER", "LIVE")
    assert validate_transition("DRAFT", "LIVE") is not None
    assert validate_transition("LIVE", "LIVE") is not None


def test_factor_top_n_no_lookahead():
    dates = ["2026-01-01", "2026-01-02", "2026-01-03"]
    symbols_by_date = {d: {"X", "Y"} for d in dates}
    factors = [
        {"symbol": "X", "trade_date": "2026-01-01", "value": 1.0},
        {"symbol": "Y", "trade_date": "2026-01-01", "value": 2.0},
        {"symbol": "X", "trade_date": "2026-01-02", "value": 9.0},
        {"symbol": "Y", "trade_date": "2026-01-02", "value": 0.1},
    ]
    rows = build_factor_top_n_weights(
        trade_dates=dates,
        symbols_by_date=symbols_by_date,
        factor_rows=factors,
        top_n=1,
        rebalance_days=1,
    )
    d2 = [r for r in rows if r["trade_date"] == "2026-01-02"]
    assert len(d2) == 1 and d2[0]["symbol"] == "Y"
    d3 = [r for r in rows if r["trade_date"] == "2026-01-03"]
    assert len(d3) == 1 and d3[0]["symbol"] == "X"
