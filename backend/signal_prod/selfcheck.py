from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from signal_prod.weights import build_factor_top_n_weights


def _run_mock() -> None:
    dates = ["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04"]
    symbols_by_date = {d: {"A", "B", "C"} for d in dates}
    factors = [
        {"symbol": "A", "trade_date": "2026-06-01", "value": 0.1},
        {"symbol": "B", "trade_date": "2026-06-01", "value": 0.3},
        {"symbol": "C", "trade_date": "2026-06-01", "value": 0.2},
        {"symbol": "A", "trade_date": "2026-06-02", "value": 0.9},
        {"symbol": "B", "trade_date": "2026-06-02", "value": 0.1},
        {"symbol": "C", "trade_date": "2026-06-02", "value": 0.5},
    ]
    rows = build_factor_top_n_weights(
        trade_dates=dates,
        symbols_by_date=symbols_by_date,
        factor_rows=factors,
        top_n=2,
        rebalance_days=2,
    )
    # 06-02 用 06-01 因子 → B,C；下一调仓 06-04 用 06-03 无因子则跳过；
    # rebalance=2：entry=06-02(idx1)，下一为 idx3=06-04
    by_date: dict[str, list[str]] = {}
    for r in rows:
        by_date.setdefault(r["trade_date"], []).append(r["symbol"])
    assert "2026-06-02" in by_date
    assert set(by_date["2026-06-02"]) == {"B", "C"}
    for r in rows:
        if r["trade_date"] == "2026-06-02":
            assert abs(r["weight"] - 0.5) < 1e-9
    # 禁止前视：06-02 信号不得用 06-02 当日因子（否则会选 A）
    assert "A" not in by_date["2026-06-02"]
    print("mock_cases=ok")


def main() -> int:
    _run_mock()
    print("status=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
