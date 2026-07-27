from __future__ import annotations

from portfolio_construct.sizing import lot_shares, renormalize_weights, size_positions


def test_lot_shares_rounds_down():
    assert lot_shares(9999, 10.0, 100) == 900
    assert lot_shares(1000, 10.0, 100) == 100


def test_renormalize_after_drop():
    rows = renormalize_weights(
        [{"symbol": "A", "weight": 0.25}, {"symbol": "B", "weight": 0.75}]
    )
    assert abs(rows[0]["target_weight"] - 0.25) < 1e-9
    assert abs(rows[1]["target_weight"] - 0.75) < 1e-9


def test_size_drops_cannot_buy_and_no_price():
    positions, meta = size_positions(
        weight_rows=[
            {"symbol": "A", "weight": 0.4},
            {"symbol": "B", "weight": 0.4},
            {"symbol": "C", "weight": 0.2},
        ],
        prices={"A": 10.0, "B": 10.0},  # C 无价
        can_buy={"A": 1, "B": 0, "C": 1},
        nav=10_000.0,
        lot_size=100,
    )
    assert [p["symbol"] for p in positions] == ["A"]
    assert meta["dropped_cannot_buy"] == 1
    assert meta["dropped_no_price"] == 1
    assert positions[0]["target_shares"] == 1000
    assert abs(positions[0]["target_weight"] - 1.0) < 1e-9
    assert meta["pricing"] == "unadjusted_close"


def test_size_propagates_can_sell():
    positions, _ = size_positions(
        weight_rows=[{"symbol": "A", "weight": 1.0}],
        prices={"A": 10.0},
        can_buy={"A": 1},
        can_sell={"A": 0},
        nav=10_000.0,
        lot_size=100,
    )
    assert positions[0]["can_sell"] == 0
