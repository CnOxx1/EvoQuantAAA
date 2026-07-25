from __future__ import annotations

from data_process.compute import build_equity_processed_rows


def _raw(symbol, trade_date, close=10.0, open_=10.0, high=11.0, low=9.0):
    return {
        "symbol": symbol,
        "trade_date": trade_date,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": 1000,
        "amount": 10000,
        "source": "test",
    }


def test_adj_multiply_and_ret():
    bars = [
        _raw("600000", "2026-07-01", close=10.0),
        _raw("600000", "2026-07-02", close=11.0),
    ]
    factors = {("600000", "2026-07-01"): 2.0, ("600000", "2026-07-02"): 2.0}
    rows, skipped = build_equity_processed_rows(
        bars=bars,
        factors=factors,
        suspended=set(),
        limit_up=set(),
        limit_down=set(),
        factor_type="qfq",
        process_batch_id="b1",
        processed_at="2026-07-25T00:00:00+00:00",
    )
    assert skipped == 0
    assert rows[0]["adj_close"] == 20.0
    assert rows[0]["ret_1d"] is None
    assert abs(rows[1]["ret_1d"] - 0.1) < 1e-9


def test_missing_factor_skipped():
    bars = [_raw("600000", "2026-07-01"), _raw("600000", "2026-07-02")]
    factors = {("600000", "2026-07-01"): 1.0}
    rows, skipped = build_equity_processed_rows(
        bars=bars,
        factors=factors,
        suspended=set(),
        limit_up=set(),
        limit_down=set(),
        factor_type="qfq",
        process_batch_id="b1",
        processed_at="t",
    )
    assert skipped == 1
    assert len(rows) == 1


def test_suspend_masks():
    bars = [_raw("600000", "2026-07-01")]
    rows, _ = build_equity_processed_rows(
        bars=bars,
        factors={("600000", "2026-07-01"): 1.0},
        suspended={("600000", "2026-07-01")},
        limit_up=set(),
        limit_down=set(),
        factor_type="qfq",
        process_batch_id="b1",
        processed_at="t",
    )
    assert rows[0]["can_buy"] == 0
    assert rows[0]["can_sell"] == 0


def test_limit_up_buy_blocked():
    bars = [_raw("600000", "2026-07-01")]
    rows, _ = build_equity_processed_rows(
        bars=bars,
        factors={("600000", "2026-07-01"): 1.0},
        suspended=set(),
        limit_up={("600000", "2026-07-01")},
        limit_down=set(),
        factor_type="qfq",
        process_batch_id="b1",
        processed_at="t",
    )
    assert rows[0]["can_buy"] == 0
    assert rows[0]["can_sell"] == 1


def test_limit_down_sell_blocked():
    bars = [_raw("600000", "2026-07-01")]
    rows, _ = build_equity_processed_rows(
        bars=bars,
        factors={("600000", "2026-07-01"): 1.0},
        suspended=set(),
        limit_up=set(),
        limit_down={("600000", "2026-07-01")},
        factor_type="qfq",
        process_batch_id="b1",
        processed_at="t",
    )
    assert rows[0]["can_buy"] == 1
    assert rows[0]["can_sell"] == 0
