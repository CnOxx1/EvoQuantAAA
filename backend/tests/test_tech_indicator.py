from __future__ import annotations

from data_process.tech_indicator import (
    compute_for_closes,
    compute_tech_indicator_rows,
)


def test_ma_and_boll_on_linear_series():
    closes = [float(i) for i in range(1, 31)]  # 1..30
    s = compute_for_closes(closes)
    # MA_5 at index 4 (value 5): (1+2+3+4+5)/5 = 3
    assert abs(s["MA_5"][4] - 3.0) < 1e-9
    assert s["MA_5"][3] is None
    # MA_20 at index 19: mean 1..20 = 10.5
    assert abs(s["MA_20"][19] - 10.5) < 1e-9
    assert abs(s["BOLL_MID"][19] - 10.5) < 1e-9
    assert s["BOLL_UP"][19] > s["BOLL_MID"][19] > s["BOLL_LOW"][19]
    assert s["MA_60"][29] is None  # only 30 points


def test_ma60_when_enough_history():
    closes = [float(i) for i in range(1, 61)]
    s = compute_for_closes(closes)
    assert abs(s["MA_60"][59] - 30.5) < 1e-9


def test_ema_macd_rsi_finite():
    closes = [100.0 + (i % 7) - 3 for i in range(80)]
    s = compute_for_closes(closes)
    assert s["EMA_12"][11] is not None
    assert s["EMA_26"][25] is not None
    assert s["MACD_DIF"][25] is not None
    # DEA needs 9 DIF points after EMA26 starts → index ~ 25+8
    last = len(closes) - 1
    assert s["MACD_DEA"][last] is not None
    assert s["MACD_HIST"][last] is not None
    assert s["RSI_14"][14] is not None
    assert 0.0 <= s["RSI_14"][last] <= 100.0


def test_rows_respect_start_end_and_skip_warmup():
    bars = [
        {
            "symbol": "X",
            "trade_date": f"2026-01-{i:02d}",
            "adj_close": 10.0 + i,
        }
        for i in range(1, 21)
    ]
    rows = compute_tech_indicator_rows(
        bars,
        start="2026-01-15",
        end="2026-01-20",
        factor_type="qfq",
        process_batch_id="b1",
        processed_at="t",
    )
    dates = {r["trade_date"] for r in rows}
    assert "2026-01-10" not in dates
    assert "2026-01-15" in dates
    assert "2026-01-20" in dates
    codes = {r["indicator_code"] for r in rows if r["trade_date"] == "2026-01-20"}
    assert "MA_5" in codes
    assert "MA_20" in codes
    assert "MA_60" not in codes  # only 20 bars


def test_skip_missing_adj_close():
    bars = [
        {"symbol": "A", "trade_date": "2026-01-01", "adj_close": 1.0},
        {"symbol": "A", "trade_date": "2026-01-02", "adj_close": None},
        {"symbol": "B", "trade_date": "2026-01-01", "adj_close": 2.0},
    ]
    # B alone with 1 bar → no MA_5
    rows = compute_tech_indicator_rows(
        bars,
        start="2026-01-01",
        end="2026-01-02",
        factor_type="qfq",
        process_batch_id="b1",
        processed_at="t",
    )
    # A only has day1 (day2 dropped); insufficient for any MA_5
    assert all(r["symbol"] != "A" or r["indicator_code"] != "MA_5" for r in rows)
