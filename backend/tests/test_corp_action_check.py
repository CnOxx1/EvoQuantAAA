from __future__ import annotations

import json

from data_quality.corp_action_check import corp_action_adj_check, theoretical_ex_price


def test_bonus_10_for_10_pass():
    # 前收 10，10 送 10 → 理论除权价 5
    theo = theoretical_ex_price(10.0, cash_per_share=0.0, share_factor=1.0)
    assert abs(theo - 5.0) < 1e-9
    equity = [
        {"symbol": "A", "trade_date": "2026-01-01", "close": 10.0},
        {"symbol": "A", "trade_date": "2026-01-02", "close": 5.0},
    ]
    actions = [
        {
            "symbol": "A",
            "ex_date": "2026-01-02",
            "action_type": "BONUS",
            "raw_payload": json.dumps({"bonus_ratio_per_10": 10, "transfer_ratio_per_10": 0}),
        }
    ]
    out = corp_action_adj_check(corp_actions=actions, equity_rows=equity)
    assert out.status == "pass"


def test_wrong_close_fails():
    equity = [
        {"symbol": "A", "trade_date": "2026-01-01", "close": 10.0},
        {"symbol": "A", "trade_date": "2026-01-02", "close": 9.5},  # 应为 ~5
    ]
    actions = [
        {
            "symbol": "A",
            "ex_date": "2026-01-02",
            "action_type": "BONUS",
            "raw_payload": json.dumps({"bonus_ratio_per_10": 10}),
        }
    ]
    out = corp_action_adj_check(corp_actions=actions, equity_rows=equity)
    assert out.status == "fail"
    assert out.severity == "warn"
