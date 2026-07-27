from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from execution.models import CostSnapshot
from execution.paper import build_paper_intents, commission, fill_price, simulate_paper_fills


def _run_mock() -> None:
    cost = CostSnapshot(
        version="t",
        commission_rate=0.0003,
        min_commission=5.0,
        stamp_tax_rate=0.0005,
        slippage_rate=0.0005,
    )
    assert abs(fill_price("BUY", 10.0, cost) - 10.005) < 1e-9
    assert abs(fill_price("SELL", 10.0, cost) - 9.995) < 1e-9
    assert commission(1000, cost) == 5.0  # min

    intents = build_paper_intents(
        positions=[
            {
                "symbol": "A",
                "target_shares": 1000,
                "price": 10.0,
                "can_buy": 1,
            },
            {
                "symbol": "B",
                "target_shares": 500,
                "price": 20.0,
                "can_buy": 0,
            },
            {
                "symbol": "C",
                "target_shares": 0,
                "price": 10.0,
                "can_sell": 1,
            },
        ],
        current_shares={"C": 200},
        sellable_shares={"C": 100},
    )
    by = {i["symbol"]: i for i in intents}
    assert by["A"]["side"] == "BUY" and not by["A"]["reject"]
    assert by["B"]["reject"] and by["B"]["reason"] == "cannot_buy"
    assert by["C"]["side"] == "SELL" and by["C"]["qty"] == 100

    orders, fills = simulate_paper_fills(
        intents=[i for i in intents if not i.get("reject")],
        cost=cost,
        trade_date="2026-07-23",
    )
    assert len(orders) == 2
    assert any(o["side"] == "BUY" and o["status"] == "FILLED" for o in orders)
    assert any(o["side"] == "SELL" and o["status"] == "FILLED" for o in orders)
    assert len(fills) == 2
    # SELL 才有印花税
    sell_intents = [
        {
            "symbol": "A",
            "side": "SELL",
            "qty": 100,
            "reject": False,
            "mid_price": 10.0,
        }
    ]
    _, sell_fills = simulate_paper_fills(
        intents=sell_intents, cost=cost, trade_date="2026-07-23"
    )
    assert sell_fills[0]["stamp_tax"] > 0

    # 现金约束：零成本下先卖后买，0 现金也能买
    cost0 = CostSnapshot(
        version="t0",
        commission_rate=0.0,
        min_commission=0.0,
        stamp_tax_rate=0.0,
        slippage_rate=0.0,
    )
    orders_c, fills_c = simulate_paper_fills(
        intents=[
            {
                "symbol": "X",
                "side": "BUY",
                "qty": 100,
                "reject": False,
                "mid_price": 10.0,
            },
            {
                "symbol": "Y",
                "side": "SELL",
                "qty": 100,
                "reject": False,
                "mid_price": 10.0,
            },
        ],
        cost=cost0,
        trade_date="2026-07-23",
        cash=0.0,
        lot_size=100,
    )
    assert all(o["status"] == "FILLED" for o in orders_c)
    assert len(fills_c) == 2

    from execution.paper import compute_residuals

    res = compute_residuals(
        intents=[
            {
                "symbol": "Z",
                "side": "BUY",
                "qty": 300,
                "reject": True,
                "reason": "cannot_buy",
            }
        ],
        orders=[
            {
                "symbol": "Z",
                "side": "BUY",
                "qty": 300,
                "status": "REJECTED",
                "reason": "cannot_buy",
            }
        ],
        fills=[],
        lot_size=100,
    )
    assert len(res) == 1 and res[0]["qty_remaining"] == 300
    print("mock_cases=ok")


def main() -> int:
    _run_mock()
    print("status=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
