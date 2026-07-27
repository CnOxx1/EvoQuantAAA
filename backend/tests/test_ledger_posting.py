from __future__ import annotations

from ledger.posting import apply_fifo_sell, project_balances, sellable_qty


def test_t1_sellable_excludes_same_day():
    lots = [
        {"lot_id": "1", "symbol": "X", "buy_date": "2026-01-01", "qty_remaining": 50},
        {"lot_id": "2", "symbol": "X", "buy_date": "2026-01-02", "qty_remaining": 80},
    ]
    assert sellable_qty(lots, symbol="X", as_of="2026-01-02") == 50
    assert sellable_qty(lots, symbol="X", as_of="2026-01-03") == 130


def test_fifo_sell_oldest_first():
    lots = [
        {
            "lot_id": "a",
            "symbol": "X",
            "buy_date": "2026-01-01",
            "qty_remaining": 50,
            "created_at": "1",
        },
        {
            "lot_id": "b",
            "symbol": "X",
            "buy_date": "2026-01-01",
            "qty_remaining": 50,
            "created_at": "2",
        },
    ]
    out, taken = apply_fifo_sell(lots, symbol="X", qty=60, as_of="2026-01-02")
    assert taken == 60
    assert float(out[0]["qty_remaining"]) == 0
    assert float(out[1]["qty_remaining"]) == 40


def test_same_day_sell_blocked_in_projection():
    _, pos, _, errs = project_balances(
        opening_cash=1_000_000,
        fills=[
            {
                "side": "BUY",
                "symbol": "A",
                "qty": 100,
                "amount": 1000,
                "commission": 5,
                "stamp_tax": 0,
                "trade_date": "2026-07-23",
                "fill_id": "1",
            },
            {
                "side": "SELL",
                "symbol": "A",
                "qty": 100,
                "amount": 1000,
                "commission": 5,
                "stamp_tax": 0.5,
                "trade_date": "2026-07-23",
                "fill_id": "2",
            },
        ],
    )
    assert pos.get("A") == 100
    assert any("T+1" in e for e in errs)
