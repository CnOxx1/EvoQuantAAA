from __future__ import annotations

from ops_monitor.coverage import month_counts_from_rows


def test_month_counts():
    rows = [
        {"trade_date": "2026-01-01"},
        {"trade_date": "2026-01-15"},
        {"trade_date": "2026-02-01"},
    ]
    assert month_counts_from_rows(rows) == {"2026-01": 2, "2026-02": 1}
