from __future__ import annotations

"""轻量自检：依赖库中已有 CORE raw，跑 process P0 并断言 processed 行数。"""

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from data_process.models import ProcessRequest
from data_process.service import DataProcessService
from shared.db import get_conn


def main() -> int:
    with get_conn() as conn:
        n_eq = int(
            conn.execute("SELECT COUNT(*) AS n FROM raw_equity_bar_1d").fetchone()["n"]
        )
        n_adj = int(
            conn.execute("SELECT COUNT(*) AS n FROM raw_adj_factor").fetchone()["n"]
        )
    if n_eq < 2 or n_adj < 2:
        print("status=skip message=需要先有 raw_equity_bar_1d 与 raw_adj_factor")
        return 0

    svc = DataProcessService()
    results = svc.run_p0(
        ProcessRequest(
            kind="equity_1d",
            start="2026-07-01",
            end="2026-07-23",
            symbols=["600000", "000001"],
            index_symbols=["000300"],
            factor_type="qfq",
        )
    )
    ok = all(r.status == "committed" for r in results)
    for r in results:
        print(
            f"kind={r.kind} status={r.status} batch={r.process_batch_id} "
            f"out={r.output_rows} inserted={r.inserted} updated={r.updated}"
        )
        if r.message:
            print(f"message={r.message}")

    ti = svc.run(
        ProcessRequest(
            kind="tech_indicator",
            start="2026-07-01",
            end="2026-07-23",
            symbols=["600000", "000001"],
            factor_type="qfq",
            force=True,
            chunk_size=50,
        )
    )
    print(
        f"kind={ti.kind} status={ti.status} batch={ti.process_batch_id} "
        f"out={ti.output_rows} inserted={ti.inserted} updated={ti.updated}"
    )
    ok = ok and ti.status == "committed"

    with get_conn() as conn:
        pe = int(
            conn.execute(
                "SELECT COUNT(*) AS n FROM processed_equity_bar_1d"
            ).fetchone()["n"]
        )
        pi = int(
            conn.execute(
                "SELECT COUNT(*) AS n FROM processed_index_bar_1d"
            ).fetchone()["n"]
        )
        ret_n = int(
            conn.execute(
                """
                SELECT COUNT(*) AS n FROM processed_equity_bar_1d
                WHERE ret_1d IS NOT NULL
                """
            ).fetchone()["n"]
        )
        ti_n = int(
            conn.execute(
                "SELECT COUNT(*) AS n FROM processed_tech_indicator_1d"
            ).fetchone()["n"]
        )
    print(
        f"processed_equity_bar_1d={pe} processed_index_bar_1d={pi} "
        f"ret_filled={ret_n} tech_indicator={ti_n}"
    )
    assert pe >= 2, "processed equity 行数不足"
    assert pi >= 1, "processed index 行数不足"
    assert ret_n >= 1, "ret_1d 应至少有一日有值"
    assert ti.status == "committed" and ti_n >= 1, "tech_indicator 应写出至少一行"
    print("status=ok" if ok else "status=failed")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
