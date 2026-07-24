from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from data_quality.models import DqRequest
from data_quality.service import DataQualityService
from shared.db import get_conn


def main() -> int:
    with get_conn() as conn:
        n = int(
            conn.execute(
                "SELECT COUNT(*) AS n FROM processed_equity_bar_1d"
            ).fetchone()["n"]
        )
    if n < 2:
        print("status=skip message=需要先有 processed_equity_bar_1d")
        return 0

    result = DataQualityService().run_core(
        DqRequest(
            start="2026-07-01",
            end="2026-07-23",
            symbols=["600000", "000001"],
            index_symbols=["000300"],
            factor_type="qfq",
        )
    )
    print(
        f"status={result.status} dq_run_id={result.dq_run_id} "
        f"error_fails={result.error_fails} warn_fails={result.warn_fails} "
        f"rules={result.rule_count}"
    )
    if result.message:
        print(f"message={result.message}")

    with get_conn() as conn:
        rules = conn.execute(
            """
            SELECT rule_code, severity, status, message
            FROM dq_result WHERE dq_run_id = ?
            ORDER BY rule_code
            """,
            (result.dq_run_id,),
        ).fetchall()
        for r in rules:
            print(
                f"rule={r['rule_code']} severity={r['severity']} "
                f"status={r['status']} message={r['message']}"
            )
        gate = conn.execute(
            """
            SELECT status, dq_run_id FROM dq_gate
            WHERE scope='CORE' AND start_date='2026-07-01'
              AND end_date='2026-07-23' AND factor_type='qfq'
            """
        ).fetchone()
    assert gate is not None, "dq_gate 未写入"
    print(f"gate={gate['status']} run={gate['dq_run_id']}")
    assert result.status in ("passed", "failed")
    print("status=ok")
    return 0 if result.status == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
