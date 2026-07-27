from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from portfolio_construct.sizing import lot_shares, renormalize_weights, size_positions


def _run_mock() -> None:
    assert lot_shares(10000, 10.0, 100) == 1000
    assert lot_shares(1050, 10.0, 100) == 100  # 105 股 → 100
    assert lot_shares(50, 10.0, 100) == 0

    norm = renormalize_weights(
        [{"symbol": "A", "weight": 0.2}, {"symbol": "B", "weight": 0.3}]
    )
    assert abs(norm[0]["target_weight"] + norm[1]["target_weight"] - 1.0) < 1e-9

    positions, meta = size_positions(
        weight_rows=[
            {"symbol": "A", "weight": 0.5, "signal_value": 1.0},
            {"symbol": "B", "weight": 0.5, "signal_value": 2.0},
            {"symbol": "C", "weight": 0.5, "signal_value": 3.0},  # 不可买
        ],
        prices={"A": 10.0, "B": 20.0, "C": 30.0},
        can_buy={"A": 1, "B": 1, "C": 0},
        nav=100_000.0,
        lot_size=100,
    )
    syms = {p["symbol"] for p in positions}
    assert syms == {"A", "B"}
    assert "C" not in syms
    assert meta["dropped_cannot_buy"] == 1
    assert abs(sum(p["target_weight"] for p in positions) - 1.0) < 1e-9
    # A: 50k / 10 = 5000 股；B: 50k / 20 = 2500 股
    by = {p["symbol"]: p for p in positions}
    assert by["A"]["target_shares"] == 5000
    assert by["B"]["target_shares"] == 2500
    print("mock_cases=ok")


def main() -> int:
    _run_mock()
    print("status=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
