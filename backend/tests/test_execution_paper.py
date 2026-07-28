from __future__ import annotations

from execution.models import CostSnapshot
from execution.paper import build_paper_intents, fill_price, simulate_paper_fills


def test_fill_price_slippage():
    cost = CostSnapshot(
        version="t",
        commission_rate=0.0,
        min_commission=0.0,
        stamp_tax_rate=0.0,
        slippage_rate=0.001,
    )
    assert abs(fill_price("BUY", 100.0, cost) - 100.1) < 1e-9
    assert abs(fill_price("SELL", 100.0, cost) - 99.9) < 1e-9


def test_fill_price_sqrt_impact():
    cost = CostSnapshot(
        version="t",
        commission_rate=0.0,
        min_commission=0.0,
        stamp_tax_rate=0.0,
        slippage_rate=0.0,
        impact_model="sqrt_adv",
        impact_coef=0.1,
    )
    # notional=100*1000=1e5, adv=1e7, part=0.01, slip=0.01
    px = fill_price("BUY", 100.0, cost, qty=1000, adv=10_000_000)
    assert abs(px - 101.0) < 1e-9


def test_intents_from_flat_book():
    intents = build_paper_intents(
        positions=[
            {"symbol": "A", "target_shares": 200, "price": 10.0, "can_buy": 1},
            {"symbol": "B", "target_shares": 0, "price": 10.0, "can_buy": 1},
        ],
        current_shares={"B": 100},
    )
    by = {(i["symbol"], i["side"]): i for i in intents}
    assert ("A", "BUY") in by and by[("A", "BUY")]["qty"] == 200
    assert ("B", "SELL") in by and by[("B", "SELL")]["qty"] == 100


def test_intents_delta_and_t1_clamp():
    intents = build_paper_intents(
        positions=[
            {"symbol": "A", "target_shares": 300, "price": 10.0, "can_buy": 1},
            {"symbol": "B", "target_shares": 0, "price": 10.0, "can_sell": 1},
        ],
        current_shares={"A": 100, "B": 200},
        sellable_shares={"A": 100, "B": 100},
    )
    by = {(i["symbol"], i["side"]): i for i in intents}
    assert by[("A", "BUY")]["qty"] == 200
    assert by[("B", "SELL")]["qty"] == 100  # clamped from 200
    assert by[("B", "SELL")].get("reason") == "clamped_sellable"


def test_stamp_tax_sell_only():
    cost = CostSnapshot(
        version="t",
        commission_rate=0.0,
        min_commission=0.0,
        stamp_tax_rate=0.001,
        slippage_rate=0.0,
    )
    _, buys = simulate_paper_fills(
        intents=[
            {
                "symbol": "A",
                "side": "BUY",
                "qty": 100,
                "reject": False,
                "mid_price": 10.0,
            }
        ],
        cost=cost,
        trade_date="2026-07-23",
    )
    _, sells = simulate_paper_fills(
        intents=[
            {
                "symbol": "A",
                "side": "SELL",
                "qty": 100,
                "reject": False,
                "mid_price": 10.0,
            }
        ],
        cost=cost,
        trade_date="2026-07-23",
    )
    assert buys[0]["stamp_tax"] == 0.0
    assert abs(sells[0]["stamp_tax"] - 1.0) < 1e-9


def test_cash_guard_rejects_and_clamps():
    cost = CostSnapshot(
        version="t",
        commission_rate=0.0,
        min_commission=0.0,
        stamp_tax_rate=0.0,
        slippage_rate=0.0,
    )
    orders, fills = simulate_paper_fills(
        intents=[
            {
                "symbol": "A",
                "side": "BUY",
                "qty": 1000,
                "reject": False,
                "mid_price": 10.0,
            }
        ],
        cost=cost,
        trade_date="2026-07-23",
        cash=500.0,
        lot_size=100,
    )
    assert orders[0]["status"] == "REJECTED"
    assert orders[0]["reason"] == "insufficient_cash"
    assert fills == []

    orders2, fills2 = simulate_paper_fills(
        intents=[
            {
                "symbol": "B",
                "side": "BUY",
                "qty": 500,
                "reject": False,
                "mid_price": 10.0,
            }
        ],
        cost=cost,
        trade_date="2026-07-23",
        cash=2500.0,
        lot_size=100,
    )
    assert orders2[0]["status"] == "FILLED"
    assert orders2[0]["qty"] == 200
    assert orders2[0]["reason"] == "clamped_cash"
    assert fills2[0]["qty"] == 200


def test_sell_before_buy_frees_cash():
    cost = CostSnapshot(
        version="t",
        commission_rate=0.0,
        min_commission=0.0,
        stamp_tax_rate=0.0,
        slippage_rate=0.0,
    )
    orders, fills = simulate_paper_fills(
        intents=[
            {
                "symbol": "BUY1",
                "side": "BUY",
                "qty": 100,
                "reject": False,
                "mid_price": 10.0,
            },
            {
                "symbol": "SELL1",
                "side": "SELL",
                "qty": 100,
                "reject": False,
                "mid_price": 10.0,
            },
        ],
        cost=cost,
        trade_date="2026-07-23",
        cash=0.0,
        lot_size=100,
    )
    by = {o["symbol"]: o for o in orders}
    assert by["SELL1"]["status"] == "FILLED"
    assert by["BUY1"]["status"] == "FILLED"
    assert len(fills) == 2


def test_compute_residuals_reject_and_clamp():
    from execution.paper import compute_residuals

    intents = [
        {
            "symbol": "A",
            "side": "BUY",
            "qty": 500,
            "reject": False,
            "mid_price": 10.0,
        },
        {
            "symbol": "B",
            "side": "SELL",
            "qty": 200,
            "reject": True,
            "reason": "cannot_sell",
            "mid_price": 10.0,
        },
    ]
    orders = [
        {
            "symbol": "A",
            "side": "BUY",
            "qty": 200,
            "status": "FILLED",
            "reason": "clamped_cash",
        },
        {
            "symbol": "B",
            "side": "SELL",
            "qty": 200,
            "status": "REJECTED",
            "reason": "cannot_sell",
        },
    ]
    fills = [{"symbol": "A", "side": "BUY", "qty": 200}]
    res = compute_residuals(
        intents=intents, orders=orders, fills=fills, lot_size=100
    )
    by = {(r["symbol"], r["side"]): r for r in res}
    assert by[("A", "BUY")]["qty_remaining"] == 300
    assert by[("B", "SELL")]["qty_remaining"] == 200
    assert by[("B", "SELL")]["last_reason"] == "cannot_sell"


def test_build_pending_intents_respects_can_sell():
    from execution.paper import build_pending_intents

    pendings = [
        {
            "symbol": "X",
            "side": "SELL",
            "qty_remaining": 100,
        }
    ]
    bars = {"X": {"close": 10.0, "can_buy": 1, "can_sell": 0}}
    intents = build_pending_intents(
        pendings=pendings, bars=bars, sellable_shares={"X": 100}
    )
    assert len(intents) == 1
    assert intents[0]["reject"] and intents[0]["reason"] == "cannot_sell"

    bars2 = {"X": {"close": 10.0, "can_buy": 1, "can_sell": 1}}
    intents2 = build_pending_intents(
        pendings=pendings, bars=bars2, sellable_shares={"X": 100}
    )
    assert not intents2[0]["reject"]
