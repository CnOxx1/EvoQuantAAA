from __future__ import annotations

from data_process.limit_derive import derive_limit_keys, limit_threshold


def test_thresholds():
    assert limit_threshold("600000", is_st=False) == 0.10
    assert limit_threshold("300001", is_st=False) == 0.20
    assert limit_threshold("688001", is_st=False) == 0.20
    assert limit_threshold("600000", is_st=True) == 0.05


def test_main_board_limit_up_derived():
    bars = [
        {"symbol": "600000", "trade_date": "2026-01-01", "close": 10.0},
        {"symbol": "600000", "trade_date": "2026-01-02", "close": 11.0},  # +10%
    ]
    up, down, derived = derive_limit_keys(
        bars=bars, st_rows=[], existing_up=set(), existing_down=set()
    )
    assert ("600000", "2026-01-02") in up
    assert ("600000", "2026-01-02") in derived
    assert not down


def test_chinext_20pct():
    bars = [
        {"symbol": "300001", "trade_date": "2026-01-01", "close": 10.0},
        {"symbol": "300001", "trade_date": "2026-01-02", "close": 12.0},
    ]
    up, _, _ = derive_limit_keys(
        bars=bars, st_rows=[], existing_up=set(), existing_down=set()
    )
    assert ("300001", "2026-01-02") in up


def test_st_5pct():
    bars = [
        {"symbol": "600000", "trade_date": "2026-01-01", "close": 10.0},
        {"symbol": "600000", "trade_date": "2026-01-02", "close": 10.5},
    ]
    st = [
        {
            "symbol": "600000",
            "treat_type": "ST",
            "effective_date": "2025-01-01",
            "end_date": None,
        }
    ]
    up, _, _ = derive_limit_keys(
        bars=bars, st_rows=st, existing_up=set(), existing_down=set()
    )
    assert ("600000", "2026-01-02") in up


def test_non_limit_day():
    bars = [
        {"symbol": "600000", "trade_date": "2026-01-01", "close": 10.0},
        {"symbol": "600000", "trade_date": "2026-01-02", "close": 10.5},  # +5%
    ]
    up, down, derived = derive_limit_keys(
        bars=bars, st_rows=[], existing_up=set(), existing_down=set()
    )
    assert not up and not down and not derived


def test_board_overrides_derive():
    bars = [
        {"symbol": "600000", "trade_date": "2026-01-01", "close": 10.0},
        {"symbol": "600000", "trade_date": "2026-01-02", "close": 11.0},
    ]
    up, down, derived = derive_limit_keys(
        bars=bars,
        st_rows=[],
        existing_up={("600000", "2026-01-02")},
        existing_down=set(),
    )
    assert ("600000", "2026-01-02") in up
    assert ("600000", "2026-01-02") not in derived
