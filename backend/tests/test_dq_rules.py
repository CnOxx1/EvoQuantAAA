from __future__ import annotations

from data_quality.rules import run_core_rules


def _eq(symbol="600000", trade_date="2026-07-02", **kw):
    base = {
        "symbol": symbol,
        "trade_date": trade_date,
        "open": 10.0,
        "high": 11.0,
        "low": 9.0,
        "close": 10.0,
        "adj_close": 10.0,
        "adj_factor": 1.0,
        "ret_1d": 0.01,
        "is_suspended": 0,
        "is_limit_up": 0,
        "is_limit_down": 0,
        "can_buy": 1,
        "can_sell": 1,
    }
    base.update(kw)
    return base


def _idx(index_symbol="000300", trade_date="2026-07-02", close=4000.0):
    return {
        "index_symbol": index_symbol,
        "trade_date": trade_date,
        "close": close,
    }


def _by_code(outcomes):
    return {o.rule_code: o for o in outcomes}


def test_all_pass_baseline():
    equity = [
        _eq(trade_date="2026-07-01", ret_1d=None),
        _eq(trade_date="2026-07-02", ret_1d=0.01),
    ]
    index = [_idx(trade_date="2026-07-01"), _idx(trade_date="2026-07-02")]
    out = _by_code(
        run_core_rules(
            equity_rows=equity,
            index_rows=index,
            calendar_open_dates={"2026-07-01", "2026-07-02"},
            expected_symbols=["600000"],
            expected_indexes=["000300"],
            corp_actions=[],
        )
    )
    # corp_action_adj_check 无样本时 pass
    assert all(o.status == "pass" for o in out.values())
    assert "corp_action_adj_check" in out


def test_equity_nonempty_fail():
    out = _by_code(
        run_core_rules(
            equity_rows=[],
            index_rows=[_idx()],
            calendar_open_dates=None,
            expected_symbols=["600000"],
            expected_indexes=["000300"],
        )
    )
    assert out["equity_nonempty"].status == "fail"


def test_index_nonempty_fail():
    out = _by_code(
        run_core_rules(
            equity_rows=[_eq(ret_1d=None)],
            index_rows=[],
            calendar_open_dates=None,
            expected_symbols=["600000"],
            expected_indexes=["000300"],
        )
    )
    assert out["index_nonempty"].status == "fail"


def test_adj_complete_fail():
    out = _by_code(
        run_core_rules(
            equity_rows=[_eq(adj_close=None, ret_1d=None)],
            index_rows=[_idx()],
            calendar_open_dates=None,
            expected_symbols=["600000"],
            expected_indexes=["000300"],
        )
    )
    assert out["adj_complete"].status == "fail"


def test_price_positive_fail():
    out = _by_code(
        run_core_rules(
            equity_rows=[_eq(close=-1.0, adj_close=-1.0, ret_1d=None)],
            index_rows=[_idx()],
            calendar_open_dates=None,
            expected_symbols=["600000"],
            expected_indexes=["000300"],
        )
    )
    assert out["price_positive"].status == "fail"


def test_ret_coverage_fail():
    equity = [
        _eq(trade_date="2026-07-01", ret_1d=None),
        _eq(trade_date="2026-07-02", ret_1d=None),
    ]
    out = _by_code(
        run_core_rules(
            equity_rows=equity,
            index_rows=[_idx()],
            calendar_open_dates=None,
            expected_symbols=["600000"],
            expected_indexes=["000300"],
        )
    )
    assert out["ret_coverage"].status == "fail"


def test_mask_consistency_fail():
    out = _by_code(
        run_core_rules(
            equity_rows=[
                _eq(
                    is_limit_up=1,
                    can_buy=1,
                    can_sell=1,
                    ret_1d=None,
                )
            ],
            index_rows=[_idx()],
            calendar_open_dates=None,
            expected_symbols=["600000"],
            expected_indexes=["000300"],
        )
    )
    assert out["mask_consistency"].status == "fail"


def test_ohlc_order_fail():
    out = _by_code(
        run_core_rules(
            equity_rows=[_eq(high=8.0, low=9.0, ret_1d=None)],
            index_rows=[_idx()],
            calendar_open_dates=None,
            expected_symbols=["600000"],
            expected_indexes=["000300"],
        )
    )
    assert out["ohlc_order"].status == "fail"


def test_extreme_return_fail():
    out = _by_code(
        run_core_rules(
            equity_rows=[
                _eq(trade_date="2026-07-01", ret_1d=None),
                _eq(trade_date="2026-07-02", ret_1d=0.5),
            ],
            index_rows=[_idx()],
            calendar_open_dates=None,
            expected_symbols=["600000"],
            expected_indexes=["000300"],
        )
    )
    assert out["extreme_return"].status == "fail"


def test_calendar_align_fail():
    out = _by_code(
        run_core_rules(
            equity_rows=[_eq(trade_date="2026-07-04", ret_1d=None)],
            index_rows=[_idx(trade_date="2026-07-04")],
            calendar_open_dates={"2026-07-01", "2026-07-02"},
            expected_symbols=["600000"],
            expected_indexes=["000300"],
        )
    )
    assert out["calendar_align"].status == "fail"
