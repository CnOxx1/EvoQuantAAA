from __future__ import annotations

from risk_engine.models import RiskLimits
from risk_engine.rules import evaluate_account_book, evaluate_portfolio


def _pos(symbol: str, w: float, shares: float, value: float, can_buy: int = 1):
    return {
        "symbol": symbol,
        "target_weight": w,
        "target_shares": shares,
        "target_value": value,
        "can_buy": can_buy,
    }


def test_approve_clean_book():
    breaches = evaluate_portfolio(
        positions=[_pos("A", 0.05, 100, 1000), _pos("B", 0.05, 100, 1000)],
        nav=20_000,
        invested_value=2000,
        kill_switch_on=False,
        limits=RiskLimits(),
    )
    assert breaches == []


def test_reject_kill_switch():
    breaches = evaluate_portfolio(
        positions=[_pos("A", 0.05, 100, 1000)],
        nav=20_000,
        invested_value=1000,
        kill_switch_on=True,
        limits=RiskLimits(),
    )
    assert any(b["code"] == "KILL_SWITCH_ON" for b in breaches)


def test_reject_single_weight_and_cannot_buy():
    breaches = evaluate_portfolio(
        positions=[
            _pos("A", 0.2, 100, 2000),
            _pos("B", 0.05, 100, 500, can_buy=0),
        ],
        nav=10_000,
        invested_value=2500,
        kill_switch_on=False,
        limits=RiskLimits(max_single_weight=0.15),
    )
    codes = {b["code"] for b in breaches}
    assert "MAX_SINGLE_WEIGHT" in codes
    assert "CANNOT_BUY" in codes


def test_account_merged_single_weight():
    # 两策略同票叠加：合并 2400 / 10000 = 0.24 > 0.15
    breaches = evaluate_account_book(
        position_books=[
            [_pos("A", 0.24, 100, 1200)],
            [_pos("A", 0.24, 100, 1200)],
        ],
        account_nav=10_000,
        limits=RiskLimits(max_single_weight=0.15),
    )
    assert any(b["code"] == "ACCOUNT_MAX_SINGLE_WEIGHT" for b in breaches)


def test_account_merged_gross():
    breaches = evaluate_account_book(
        position_books=[
            [_pos("A", 0.6, 100, 6000)],
            [_pos("B", 0.6, 100, 6000)],
        ],
        account_nav=10_000,
        limits=RiskLimits(max_gross_exposure=1.01),
    )
    assert any(b["code"] == "ACCOUNT_MAX_GROSS_EXPOSURE" for b in breaches)
