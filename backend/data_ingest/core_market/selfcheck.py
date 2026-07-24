"""本地自检：python -m data_ingest.core_market.selfcheck"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from data_ingest.core_market.models import FetchRequest
from data_ingest.core_market.repository import CoreMarketRepository
from data_ingest.core_market.service import CoreMarketIngestService
from data_ingest.core_market.sources import get_source
from shared.db import apply_migration_file, get_conn
from shared.logging_utils import setup_logging


def _apply_all_migrations() -> None:
    mig_dir = BACKEND_ROOT.parent / "database" / "migrations"
    for path in sorted(mig_dir.glob("*.sql")):
        apply_migration_file(path)


def main() -> int:
    setup_logging("WARNING")
    _apply_all_migrations()

    with get_conn() as conn:
        for t in (
            "raw_equity_bar_1d",
            "raw_adj_factor",
            "raw_suspend",
            "raw_limit_board",
            "raw_index_bar_1d",
            "raw_corp_action",
        ):
            conn.execute(f"DELETE FROM {t} WHERE source='mock'")
        conn.execute("DELETE FROM ingest_batch WHERE ingest_module='core_market'")

    svc = CoreMarketIngestService(source=get_source("mock"))
    base = FetchRequest(
        kind="equity_1d",
        start="2026-07-21",
        end="2026-07-23",
        symbols=["600000", "000001"],
        index_symbols=["000300"],
    )
    results = svc.run_p0(base)
    assert all(r.status == "committed" for r in results), results
    # 3 个交易日 × 2 标的
    assert results[0].fetched == 6, results[0]
    # 3 日 × 2 标的 × 2 因子类型
    assert results[1].fetched == 12, results[1]
    assert results[2].fetched == 1, results[2]
    assert results[3].fetched == 2, results[3]
    assert results[4].fetched == 3, results[4]

    r2 = svc.run(
        FetchRequest(
            kind="equity_1d",
            start="2026-07-21",
            end="2026-07-23",
            symbols=["600000", "000001"],
        )
    )
    assert r2.updated == 6 and r2.inserted == 0, r2

    counts = CoreMarketRepository().counts()
    assert counts["raw_equity_bar_1d"] >= 6
    assert counts["raw_adj_factor"] >= 12
    print("selfcheck OK:", counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
