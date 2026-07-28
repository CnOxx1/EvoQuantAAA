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


def test_reject_industry_concentration():
    limits = RiskLimits(max_industry_weight=0.30)
    positions = [
        {
            **_pos("A", 0.20, 100, 2000),
            "industry_code": "801010",
        },
        {
            **_pos("B", 0.15, 100, 1500),
            "industry_code": "801010",
        },
    ]
    # 3500/10000 = 0.35 > 0.30
    breaches = evaluate_portfolio(
        positions=positions,
        nav=10_000,
        invested_value=3500,
        kill_switch_on=False,
        limits=limits,
    )
    assert any(b["code"] == "MAX_INDUSTRY_WEIGHT" for b in breaches)


def test_reject_missing_industry_when_limit_on():
    breaches = evaluate_portfolio(
        positions=[_pos("A", 0.10, 100, 1000)],
        nav=10_000,
        invested_value=1000,
        kill_switch_on=False,
        limits=RiskLimits(max_industry_weight=0.30),
    )
    assert any(b["code"] == "MISSING_INDUSTRY" for b in breaches)


def test_reject_adv_participation():
    # target 2000 / ADV 10000 = 0.20 > 0.10
    breaches = evaluate_portfolio(
        positions=[
            {
                **_pos("A", 0.10, 100, 2000),
                "adv_20": 10_000,
            }
        ],
        nav=20_000,
        invested_value=2000,
        kill_switch_on=False,
        limits=RiskLimits(max_adv_participation=0.10),
    )
    assert any(b["code"] == "MAX_ADV_PARTICIPATION" for b in breaches)


def test_v1_default_skips_industry_adv():
    # v1：字段为 None，即使没有 industry/adv 也不报
    breaches = evaluate_portfolio(
        positions=[_pos("A", 0.05, 100, 1000)],
        nav=20_000,
        invested_value=1000,
        kill_switch_on=False,
        limits=RiskLimits(),
    )
    assert breaches == []


def test_account_merged_industry_and_adv():
    limits = RiskLimits(
        max_industry_weight=0.30,
        max_adv_participation=0.10,
    )
    books = [
        [
            {
                **_pos("A", 0.2, 100, 2000),
                "industry_code": "801010",
                "adv_20": 50_000,
            }
        ],
        [
            {
                **_pos("B", 0.15, 100, 1500),
                "industry_code": "801010",
                "adv_20": 50_000,
            }
        ],
    ]
    # industry 3500/10000=0.35；ADV A=2000/50000=0.04 ok
    breaches = evaluate_account_book(
        position_books=books, account_nav=10_000, limits=limits
    )
    assert any(b["code"] == "ACCOUNT_MAX_INDUSTRY_WEIGHT" for b in breaches)
