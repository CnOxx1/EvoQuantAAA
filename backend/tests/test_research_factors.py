from __future__ import annotations

from research_lab.evaluate import evaluate_factor
from research_lab.factors import (
    compute_flow_net_5,
    compute_mom_20,
    compute_tech_level,
    compute_tech_ma20_bias,
    compute_val_pe_pct,
)


def test_mom_20():
    bars = [
        {"symbol": "X", "trade_date": f"2026-01-{i:02d}", "adj_close": 10.0 + i}
        for i in range(1, 22)
    ]
    # day 21 close=30, day 1 close=11 → wait i from 1..21: day1=11, day21=31
    rows = compute_mom_20(bars, start="2026-01-21", end="2026-01-21")
    assert len(rows) == 1
    # t-20 = day 1 = 11.0, t = 31.0
    assert abs(rows[0]["value"] - (31.0 / 11.0 - 1.0)) < 1e-9


def test_val_pe_pct_worst_nonpositive():
    vals = [
        {"symbol": "A", "trade_date": "2026-01-01", "pe_ttm": 8.0},
        {"symbol": "B", "trade_date": "2026-01-01", "pe_ttm": 12.0},
        {"symbol": "C", "trade_date": "2026-01-01", "pe_ttm": 0.0},
    ]
    rows = compute_val_pe_pct(
        vals, symbols={"A", "B", "C"}, start="2026-01-01", end="2026-01-01"
    )
    by = {r["symbol"]: r["value"] for r in rows}
    assert by["A"] == 0.0
    assert by["B"] == 1.0
    assert by["C"] == 1.0


def test_flow_net_5():
    flows = [
        {
            "scope": "S",
            "trade_date": f"2026-01-0{i}",
            "flow_type": "STOCK_FLOW",
            "net_amount": 2.0,
        }
        for i in range(1, 6)
    ]
    bars = [
        {
            "symbol": "S",
            "trade_date": f"2026-01-0{i}",
            "adj_close": 1.0,
            "amount": 10.0,
        }
        for i in range(1, 6)
    ]
    rows = compute_flow_net_5(flows, bars, start="2026-01-05", end="2026-01-05")
    assert len(rows) == 1
    assert abs(rows[0]["value"] - 0.2) < 1e-9


def test_evaluate_ic_forward():
    factor_rows = [
        {"symbol": "A", "trade_date": "2026-01-01", "value": 1.0},
        {"symbol": "B", "trade_date": "2026-01-01", "value": 2.0},
        {"symbol": "C", "trade_date": "2026-01-01", "value": 3.0},
        {"symbol": "D", "trade_date": "2026-01-01", "value": 4.0},
        {"symbol": "E", "trade_date": "2026-01-01", "value": 5.0},
    ]
    # 同日收益不得用于 IC：故意给 01-01 反向收益，次日同向
    ret_rows = [
        {"symbol": s, "trade_date": "2026-01-01", "ret_1d": -float(i)}
        for i, s in enumerate("ABCDE", start=1)
    ] + [
        {"symbol": s, "trade_date": "2026-01-02", "ret_1d": float(i)}
        for i, s in enumerate("ABCDE", start=1)
    ]
    report = evaluate_factor(factor_rows=factor_rows, ret_rows=ret_rows)
    assert report["ic_mean"] is not None and report["ic_mean"] > 0.99
    assert report["layers"][0]["days"] == 1
    assert report["long_short_q5_q1"] is not None
    assert report["long_short_q5_q1"] > 0


def test_tech_rsi_passthrough():
    tech = [
        {
            "symbol": "A",
            "trade_date": "2026-07-01",
            "indicator_code": "RSI_14",
            "value": 55.0,
        },
        {
            "symbol": "A",
            "trade_date": "2026-07-01",
            "indicator_code": "MA_5",
            "value": 1.0,
        },
    ]
    rows = compute_tech_level(
        tech, indicator_code="RSI_14", start="2026-07-01", end="2026-07-01"
    )
    assert len(rows) == 1
    assert rows[0]["value"] == 55.0


def test_tech_ma20_bias():
    tech = [
        {
            "symbol": "A",
            "trade_date": "2026-07-01",
            "indicator_code": "MA_20",
            "value": 10.0,
        }
    ]
    bars = [{"symbol": "A", "trade_date": "2026-07-01", "adj_close": 11.0}]
    rows = compute_tech_ma20_bias(
        tech, bars, start="2026-07-01", end="2026-07-01"
    )
    assert len(rows) == 1
    assert abs(rows[0]["value"] - 0.1) < 1e-9
