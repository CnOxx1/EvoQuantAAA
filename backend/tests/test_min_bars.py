from __future__ import annotations

from datetime import datetime, timedelta

from data_process.min_bars import build_min_processed_rows
from data_process.tech_indicator import compute_tech_indicator_rows


def test_min_adj_applies_daily_factor():
    bars = [
        {
            "symbol": "X",
            "bar_time": "2026-07-21 10:00:00",
            "freq": "15m",
            "open": 10.0,
            "high": 11.0,
            "low": 9.0,
            "close": 10.5,
            "volume": 1000.0,
            "amount": 10500.0,
            "source": "mock",
        }
    ]
    rows, skipped = build_min_processed_rows(
        bars,
        factors={("X", "2026-07-21"): 2.0},
        factor_type="qfq",
        process_batch_id="b1",
        processed_at="t",
    )
    assert skipped == 0
    assert len(rows) == 1
    assert rows[0]["adj_close"] == 21.0
    assert rows[0]["adj_open"] == 20.0


def test_min_tech_core_on_bar_time():
    bars = []
    t0 = datetime(2026, 7, 21, 9, 45, 0)
    px = 10.0
    for i in range(40):
        px += 0.05
        bt = t0 + timedelta(minutes=15 * i)
        bars.append(
            {
                "symbol": "X",
                "bar_time": bt.strftime("%Y-%m-%d %H:%M:%S"),
                "freq": "15m",
                "adj_close": px,
                "volume": 1.0,
            }
        )
    rows = compute_tech_indicator_rows(
        bars,
        start="2026-07-21",
        end="2026-07-22",
        factor_type="qfq",
        process_batch_id="b1",
        processed_at="t",
        suite="core",
        freq="15m",
    )
    assert any(r["indicator_code"] == "MA_5" for r in rows)
    assert all("bar_time" in r for r in rows)
    assert all(r.get("freq") == "15m" for r in rows)
