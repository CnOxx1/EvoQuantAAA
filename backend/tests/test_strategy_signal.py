from __future__ import annotations

from strategy_registry.gates import (
    evaluate_promotion_gates,
    extract_ic_report,
    parse_thresholds,
)
from strategy_registry.transitions import can_transition, validate_transition


def test_transition_happy_path():
    assert can_transition("DRAFT", "BACKTESTED")
    assert can_transition("BACKTESTED", "PAPER")
    assert can_transition("PAPER", "LIVE")
    assert validate_transition("DRAFT", "LIVE") is not None
    assert validate_transition("LIVE", "LIVE") is not None


def test_factor_top_n_no_lookahead():
    from signal_prod.weights import build_factor_top_n_weights

    dates = ["2026-01-01", "2026-01-02", "2026-01-03"]
    symbols_by_date = {d: {"X", "Y"} for d in dates}
    factors = [
        {"symbol": "X", "trade_date": "2026-01-01", "value": 1.0},
        {"symbol": "Y", "trade_date": "2026-01-01", "value": 2.0},
        {"symbol": "X", "trade_date": "2026-01-02", "value": 9.0},
        {"symbol": "Y", "trade_date": "2026-01-02", "value": 0.1},
    ]
    rows = build_factor_top_n_weights(
        trade_dates=dates,
        symbols_by_date=symbols_by_date,
        factor_rows=factors,
        top_n=1,
        rebalance_days=1,
    )
    d2 = [r for r in rows if r["trade_date"] == "2026-01-02"]
    assert len(d2) == 1 and d2[0]["symbol"] == "Y"
    d3 = [r for r in rows if r["trade_date"] == "2026-01-03"]
    assert len(d3) == 1 and d3[0]["symbol"] == "X"


_LIVE_RULES = {
    "BACKTESTED": {
        "max_drawdown": 0.80,
        "min_total_return": -1.0,
        "min_calendar_days": 1,
        "min_trade_count": 1,
        "require_research_ic": False,
    },
    "PAPER": {
        "max_drawdown": 0.50,
        "min_total_return": -0.50,
        "min_calendar_days": 1,
        "min_trade_count": 1,
        "require_research_ic": False,
    },
    "LIVE": {
        "max_drawdown": 0.40,
        "min_total_return": -0.10,
        "min_calendar_days": 20,
        "min_trade_count": 1,
        "require_research_ic": True,
        "min_ic_mean": 0.0,
        "min_ic_days": 5,
    },
}


def _ok_backtest(**overrides):
    base = {
        "run_id": "bt_x",
        "status": "committed",
        "start_date": "2026-05-01",
        "end_date": "2026-06-10",
        "total_return": 0.05,
        "max_drawdown": 0.10,
        "trade_count": 5,
    }
    base.update(overrides)
    return base


def test_parse_thresholds_and_ic_report():
    raw = parse_thresholds('{"LIVE": {"max_drawdown": 0.3}}')
    assert raw["LIVE"]["max_drawdown"] == 0.3
    report = extract_ic_report(
        {"mode": "evaluate", "report": {"ic_mean": 0.02, "ic_days": 10}}
    )
    assert report["ic_mean"] == 0.02


def test_gate_live_pass():
    ev = evaluate_promotion_gates(
        to_status="LIVE",
        thresholds_by_status=_LIVE_RULES,
        gate_version="v1_default",
        backtest=_ok_backtest(),
        research_meta={"report": {"ic_mean": 0.02, "ic_days": 20}},
        research_run_id="rr_1",
    )
    assert ev.passed
    assert ev.failing_names() == []


def test_gate_live_reject_drawdown():
    ev = evaluate_promotion_gates(
        to_status="LIVE",
        thresholds_by_status=_LIVE_RULES,
        gate_version="v1_default",
        backtest=_ok_backtest(max_drawdown=0.55),
        research_meta={"report": {"ic_mean": 0.02, "ic_days": 20}},
        research_run_id="rr_1",
    )
    assert not ev.passed
    assert "max_drawdown" in ev.failing_names()


def test_gate_live_reject_missing_ic():
    ev = evaluate_promotion_gates(
        to_status="LIVE",
        thresholds_by_status=_LIVE_RULES,
        gate_version="v1_default",
        backtest=_ok_backtest(),
        research_meta=None,
        research_run_id=None,
    )
    assert not ev.passed
    assert "research_ic_present" in ev.failing_names()


def test_gate_live_reject_short_window():
    ev = evaluate_promotion_gates(
        to_status="LIVE",
        thresholds_by_status=_LIVE_RULES,
        gate_version="v1_default",
        backtest=_ok_backtest(start_date="2026-06-09", end_date="2026-06-10"),
        research_meta={"report": {"ic_mean": 0.02, "ic_days": 20}},
        research_run_id="rr_1",
    )
    assert not ev.passed
    assert "min_calendar_days" in ev.failing_names()


def test_gate_paper_no_ic_required():
    ev = evaluate_promotion_gates(
        to_status="PAPER",
        thresholds_by_status=_LIVE_RULES,
        gate_version="v1_default",
        backtest=_ok_backtest(start_date="2026-06-09", end_date="2026-06-10"),
        research_meta=None,
        research_run_id=None,
    )
    assert ev.passed


def test_gate_retired_skipped():
    ev = evaluate_promotion_gates(
        to_status="RETIRED",
        thresholds_by_status=_LIVE_RULES,
        gate_version="v1_default",
        backtest=None,
    )
    assert ev.passed
