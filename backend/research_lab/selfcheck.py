from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from research_lab.evaluate import evaluate_factor
from research_lab.factors import (
    compute_flow_net_5,
    compute_mom_20,
    compute_tech_level,
    compute_tech_ma20_bias,
    compute_val_pe_pct,
)


def _run_mock() -> None:
    # 21 日动量：第 21 日 MOM = 1.1/1.0 - 1
    bars = []
    for i in range(21):
        d = f"2026-01-{i + 1:02d}"
        px = 1.0 if i < 20 else 1.1
        bars.append(
            {
                "symbol": "600000",
                "trade_date": d,
                "adj_close": px,
                "amount": 1e8,
                "ret_1d": None if i == 0 else 0.0,
            }
        )
    mom = compute_mom_20(bars, start="2026-01-21", end="2026-01-21")
    assert len(mom) == 1 and abs(mom[0]["value"] - 0.1) < 1e-9

    vals = [
        {"symbol": "A", "trade_date": "2026-01-10", "pe_ttm": 5.0},
        {"symbol": "B", "trade_date": "2026-01-10", "pe_ttm": 15.0},
        {"symbol": "C", "trade_date": "2026-01-10", "pe_ttm": -1.0},
    ]
    pe = compute_val_pe_pct(
        vals, symbols={"A", "B", "C"}, start="2026-01-10", end="2026-01-10"
    )
    by = {r["symbol"]: r["value"] for r in pe}
    assert by["A"] == 0.0 and by["B"] == 1.0 and by["C"] == 1.0

    flows = []
    flow_bars = []
    for i in range(5):
        d = f"2026-02-{i + 1:02d}"
        flows.append(
            {
                "scope": "600000",
                "trade_date": d,
                "flow_type": "STOCK_FLOW",
                "net_amount": 1e6,
            }
        )
        flow_bars.append(
            {
                "symbol": "600000",
                "trade_date": d,
                "adj_close": 10.0,
                "amount": 1e7,
            }
        )
    flow = compute_flow_net_5(
        flows, flow_bars, start="2026-02-05", end="2026-02-05"
    )
    assert len(flow) == 1 and abs(flow[0]["value"] - 0.1) < 1e-9

    # IC：因子与次日收益同序 → IC>0
    factor_rows = [
        {"symbol": "A", "trade_date": "2026-03-01", "value": 1.0},
        {"symbol": "B", "trade_date": "2026-03-01", "value": 2.0},
        {"symbol": "C", "trade_date": "2026-03-01", "value": 3.0},
    ]
    ret_rows = [
        {"symbol": "A", "trade_date": "2026-03-02", "ret_1d": 0.01},
        {"symbol": "B", "trade_date": "2026-03-02", "ret_1d": 0.02},
        {"symbol": "C", "trade_date": "2026-03-02", "ret_1d": 0.03},
    ]
    report = evaluate_factor(factor_rows=factor_rows, ret_rows=ret_rows)
    assert report["ic_days"] == 1 and report["ic_mean"] is not None
    assert report["ic_mean"] > 0.99

    tech = [
        {
            "symbol": "600000",
            "trade_date": "2026-04-01",
            "indicator_code": "RSI_14",
            "value": 40.0,
        },
        {
            "symbol": "600000",
            "trade_date": "2026-04-01",
            "indicator_code": "MA_20",
            "value": 10.0,
        },
    ]
    rsi = compute_tech_level(
        tech, indicator_code="RSI_14", start="2026-04-01", end="2026-04-01"
    )
    assert len(rsi) == 1 and rsi[0]["value"] == 40.0
    bias = compute_tech_ma20_bias(
        tech,
        [{"symbol": "600000", "trade_date": "2026-04-01", "adj_close": 11.0}],
        start="2026-04-01",
        end="2026-04-01",
    )
    assert len(bias) == 1 and abs(bias[0]["value"] - 0.1) < 1e-9

    from research_lab.evidence import (
        hard_oos_verdict,
        soft_verdict,
        walk_forward_windows,
        year_windows,
    )

    assert year_windows("2025-12-01", "2026-01-15")[0][0] == "2025"
    v = soft_verdict({"ic_mean": 0.01, "icir": 0.2, "ic_days": 25})
    assert v["passed"] is True
    folds = walk_forward_windows(
        "2026-01-01", "2026-02-10", train_days=7, test_days=5, step_days=5
    )
    assert len(folds) >= 1
    assert hard_oos_verdict(
        {
            "fold_count": 2,
            "positive_ic_fold_ratio": 0.5,
            "ic_mean_avg": 0.0,
        }
    )["passed"]

    print("mock_cases=ok")


def main() -> int:
    _run_mock()
    print("status=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
