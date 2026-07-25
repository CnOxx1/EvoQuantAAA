from __future__ import annotations

from data_process.fund_pit import build_fund_pit_intervals, lookup_fund_asof


def test_pit_invisible_before_announce():
    stmts = [
        {
            "symbol": "600000",
            "statement_type": "INCOME",
            "report_period": "2025-12-31",
            "announce_date": "2026-03-31",
            "item_code": "NETPROFIT",
            "item_value": 1e9,
            "source": "mock",
        }
    ]
    rows = build_fund_pit_intervals(
        statement_rows=stmts,
        indicator_rows=[],
        process_batch_id="b1",
        processed_at="t",
    )
    assert lookup_fund_asof(rows, symbol="600000", as_of="2026-03-30") is None
    hit = lookup_fund_asof(rows, symbol="600000", as_of="2026-03-31")
    assert hit is not None and hit["net_profit"] == 1e9


def test_pit_visible_from_announce():
    stmts = [
        {
            "symbol": "A",
            "statement_type": "INCOME",
            "report_period": "2025-12-31",
            "announce_date": "2026-03-31",
            "item_code": "OPERATE_INCOME",
            "item_value": 100.0,
            "source": "mock",
        }
    ]
    rows = build_fund_pit_intervals(
        statement_rows=stmts,
        indicator_rows=[],
        process_batch_id="b1",
        processed_at="t",
    )
    assert rows[0]["valid_from"] == "2026-03-31"
    assert rows[0]["valid_to"] is None
    assert rows[0]["revenue"] == 100.0


def test_correction_overrides_old():
    stmts = [
        {
            "symbol": "A",
            "statement_type": "INCOME",
            "report_period": "2025-12-31",
            "announce_date": "2026-03-31",
            "item_code": "NETPROFIT",
            "item_value": 1.0,
            "source": "mock",
        },
        {
            "symbol": "A",
            "statement_type": "INCOME",
            "report_period": "2025-12-31",
            "announce_date": "2026-04-15",
            "item_code": "NETPROFIT",
            "item_value": 2.0,
            "source": "mock",
        },
    ]
    rows = build_fund_pit_intervals(
        statement_rows=stmts,
        indicator_rows=[],
        process_batch_id="b1",
        processed_at="t",
    )
    early = lookup_fund_asof(rows, symbol="A", as_of="2026-04-01")
    late = lookup_fund_asof(rows, symbol="A", as_of="2026-04-15")
    assert early is not None and early["net_profit"] == 1.0
    assert late is not None and late["net_profit"] == 2.0
    assert early["valid_to"] == "2026-04-14"
