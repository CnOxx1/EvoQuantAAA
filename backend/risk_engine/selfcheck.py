from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from risk_engine.models import RiskLimits
from risk_engine.rules import evaluate_portfolio


def _run_mock() -> None:
    limits = RiskLimits(
        max_single_weight=0.15, max_names=50, max_gross_exposure=1.01, min_names=1
    )
    ok = evaluate_portfolio(
        positions=[
            {
                "symbol": "A",
                "target_weight": 0.1,
                "target_shares": 1000,
                "target_value": 10000,
                "can_buy": 1,
            },
            {
                "symbol": "B",
                "target_weight": 0.1,
                "target_shares": 500,
                "target_value": 10000,
                "can_buy": 1,
            },
        ],
        nav=100_000,
        invested_value=20_000,
        kill_switch_on=False,
        limits=limits,
    )
    assert ok == []

    kill = evaluate_portfolio(
        positions=[],
        nav=100_000,
        invested_value=0,
        kill_switch_on=True,
        limits=limits,
    )
    assert any(b["code"] == "KILL_SWITCH_ON" for b in kill)

    heavy = evaluate_portfolio(
        positions=[
            {
                "symbol": "A",
                "target_weight": 0.2,
                "target_shares": 1000,
                "target_value": 20000,
                "can_buy": 1,
            }
        ],
        nav=100_000,
        invested_value=20_000,
        kill_switch_on=False,
        limits=limits,
    )
    assert any(b["code"] == "MAX_SINGLE_WEIGHT" for b in heavy)

    odd_lot = evaluate_portfolio(
        positions=[
            {
                "symbol": "A",
                "target_weight": 0.1,
                "target_shares": 150,
                "target_value": 1500,
                "can_buy": 1,
            }
        ],
        nav=100_000,
        invested_value=1500,
        kill_switch_on=False,
        limits=limits,
    )
    assert any(b["code"] == "LOT_SIZE" for b in odd_lot)

    # 18a：行业 / ADV
    ind_ok = evaluate_portfolio(
        positions=[
            {
                "symbol": "A",
                "target_weight": 0.1,
                "target_shares": 1000,
                "target_value": 10000,
                "can_buy": 1,
                "industry_code": "801010",
                "adv_20": 500_000,
            }
        ],
        nav=100_000,
        invested_value=10_000,
        kill_switch_on=False,
        limits=RiskLimits(
            max_industry_weight=0.30,
            max_adv_participation=0.10,
        ),
    )
    assert ind_ok == []

    ind_heavy = evaluate_portfolio(
        positions=[
            {
                "symbol": "A",
                "target_weight": 0.2,
                "target_shares": 1000,
                "target_value": 20000,
                "can_buy": 1,
                "industry_code": "801010",
                "adv_20": 500_000,
            },
            {
                "symbol": "B",
                "target_weight": 0.15,
                "target_shares": 500,
                "target_value": 15000,
                "can_buy": 1,
                "industry_code": "801010",
                "adv_20": 500_000,
            },
        ],
        nav=100_000,
        invested_value=35_000,
        kill_switch_on=False,
        limits=RiskLimits(max_industry_weight=0.30, max_adv_participation=0.10),
    )
    assert any(b["code"] == "MAX_INDUSTRY_WEIGHT" for b in ind_heavy)
    print("mock_cases=ok")


def main() -> int:
    _run_mock()
    print("status=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
