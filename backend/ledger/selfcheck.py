from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from ledger.posting import (
    apply_fifo_sell,
    build_fill_entries,
    project_balances,
    sellable_qty,
)


def _run_mock() -> None:
    lots = [
        {
            "lot_id": "1",
            "symbol": "A",
            "buy_date": "2026-07-22",
            "qty_remaining": 100,
            "created_at": "a",
        },
        {
            "lot_id": "2",
            "symbol": "A",
            "buy_date": "2026-07-23",
            "qty_remaining": 200,
            "created_at": "b",
        },
    ]
    assert sellable_qty(lots, symbol="A", as_of="2026-07-23") == 100
    assert sellable_qty(lots, symbol="A", as_of="2026-07-24") == 300

    new_lots, taken = apply_fifo_sell(
        lots, symbol="A", qty=100, as_of="2026-07-23"
    )
    assert taken == 100
    assert float(new_lots[0]["qty_remaining"]) == 0
    assert float(new_lots[1]["qty_remaining"]) == 200

    entries = build_fill_entries(
        [
            {
                "side": "BUY",
                "symbol": "A",
                "qty": 100,
                "amount": 1000,
                "commission": 5,
                "stamp_tax": 0,
                "trade_date": "2026-07-23",
                "fill_id": "f1",
            }
        ]
    )
    assert any(e["entry_type"] == "CASH_OUT" and e["amount"] == -1005 for e in entries)

    cash, pos, _, errs = project_balances(
        opening_cash=10_000,
        fills=[
            {
                "side": "BUY",
                "symbol": "A",
                "qty": 100,
                "amount": 1000,
                "commission": 5,
                "stamp_tax": 0,
                "trade_date": "2026-07-22",
                "fill_id": "b1",
            },
            {
                "side": "SELL",
                "symbol": "A",
                "qty": 100,
                "amount": 1100,
                "commission": 5,
                "stamp_tax": 0.55,
                "trade_date": "2026-07-22",
                "fill_id": "s1",
            },
        ],
    )
    # 同日卖出应 T+1 失败
    assert errs and "T+1" in errs[0]
    assert abs(cash - (10_000 - 1005)) < 1e-6
    assert pos.get("A") == 100

    cash2, pos2, _, errs2 = project_balances(
        opening_cash=10_000,
        fills=[
            {
                "side": "BUY",
                "symbol": "A",
                "qty": 100,
                "amount": 1000,
                "commission": 5,
                "stamp_tax": 0,
                "trade_date": "2026-07-22",
                "fill_id": "b1",
            },
            {
                "side": "SELL",
                "symbol": "A",
                "qty": 100,
                "amount": 1100,
                "commission": 5,
                "stamp_tax": 0.55,
                "trade_date": "2026-07-23",
                "fill_id": "s1",
            },
        ],
    )
    assert errs2 == []
    assert pos2 == {}
    assert abs(cash2 - (10_000 - 1005 + 1100 - 5 - 0.55)) < 1e-6
    print("mock_cases=ok")


def main() -> int:
    _run_mock()
    print("status=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
