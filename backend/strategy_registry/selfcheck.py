from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from strategy_registry.gates import evaluate_promotion_gates
from strategy_registry.transitions import can_transition, validate_transition


def _run_mock() -> None:
    assert can_transition("DRAFT", "BACKTESTED")
    assert can_transition("BACKTESTED", "PAPER")
    assert can_transition("PAPER", "LIVE")
    assert can_transition("LIVE", "RETIRED")
    assert not can_transition("DRAFT", "LIVE")
    assert not can_transition("RETIRED", "PAPER")
    assert validate_transition("DRAFT", "LIVE") is not None
    assert validate_transition("PAPER", "LIVE") is None
    assert validate_transition("RETIRED", "LIVE") is not None

    rules = {
        "LIVE": {
            "max_drawdown": 0.40,
            "min_total_return": -0.10,
            "min_calendar_days": 20,
            "min_trade_count": 1,
            "require_research_ic": True,
            "min_ic_mean": 0.0,
            "min_ic_days": 5,
        }
    }
    bt = {
        "run_id": "bt_mock",
        "status": "committed",
        "start_date": "2026-05-01",
        "end_date": "2026-06-10",
        "total_return": 0.02,
        "max_drawdown": 0.1,
        "trade_count": 2,
    }
    ok = evaluate_promotion_gates(
        to_status="LIVE",
        thresholds_by_status=rules,
        gate_version="v1_default",
        backtest=bt,
        research_meta={"report": {"ic_mean": 0.01, "ic_days": 10}},
        research_run_id="rr_mock",
    )
    assert ok.passed
    bad = evaluate_promotion_gates(
        to_status="LIVE",
        thresholds_by_status=rules,
        gate_version="v1_default",
        backtest={**bt, "max_drawdown": 0.9},
        research_meta={"report": {"ic_mean": 0.01, "ic_days": 10}},
        research_run_id="rr_mock",
    )
    assert not bad.passed
    print("mock_cases=ok")


def main() -> int:
    _run_mock()
    print("status=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
