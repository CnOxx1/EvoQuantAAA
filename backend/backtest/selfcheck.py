from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from backtest.models import BacktestRequest
from backtest.service import BacktestService
from shared.db import get_conn


def main() -> int:
    with get_conn() as conn:
        n = int(
            conn.execute(
                "SELECT COUNT(*) AS n FROM processed_equity_bar_1d"
            ).fetchone()["n"]
        )
    if n < 2:
        print("status=skip message=需要 processed_equity_bar_1d")
        return 0

    result = BacktestService().run(
        BacktestRequest(
            strategy_code="EW_HOLD",
            start="2026-07-01",
            end="2026-07-23",
            symbols=["600000", "000001"],
            universe_code=None,
            require_dq=True,
        )
    )
    print(
        f"status={result.status} run_id={result.run_id} "
        f"ret={result.total_return:.6f} bench={result.benchmark_return:.6f} "
        f"mdd={result.max_drawdown:.6f} trades={result.trade_count}"
    )
    if result.message:
        print(f"message={result.message}")
    if result.status != "committed":
        return 2

    with get_conn() as conn:
        nav_n = int(
            conn.execute(
                "SELECT COUNT(*) AS n FROM backtest_nav WHERE run_id=?",
                (result.run_id,),
            ).fetchone()["n"]
        )
        tr_n = int(
            conn.execute(
                "SELECT COUNT(*) AS n FROM backtest_trade WHERE run_id=?",
                (result.run_id,),
            ).fetchone()["n"]
        )
    assert nav_n >= 2, "nav 行不足"
    assert tr_n >= 1, "应有成交"
    print(f"nav_rows={nav_n} trade_rows={tr_n}")
    print("status=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
