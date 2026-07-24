"""本地自检：python -m data_ingest.alpha_fundamental.selfcheck"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from data_ingest.alpha_fundamental.models import FetchRequest
from data_ingest.alpha_fundamental.repository import FundamentalRepository
from data_ingest.alpha_fundamental.service import FundamentalIngestService
from data_ingest.alpha_fundamental.sources import get_source
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
            "raw_fund_statement",
            "raw_fund_indicator",
            "raw_consensus_estimate",
        ):
            conn.execute(f"DELETE FROM {t} WHERE source='mock'")
        conn.execute(
            "DELETE FROM ingest_batch WHERE ingest_module='alpha_fundamental'"
        )

    svc = FundamentalIngestService(source=get_source("mock"))
    base = FetchRequest(
        kind="statement",
        symbols=["600000", "000001"],
        statement_types=["INCOME", "BALANCE", "CASHFLOW"],
    )
    results = svc.run_p1(base)
    assert all(r.status == "committed" for r in results), results
    # 2 symbols × 3 types × 2 periods × 2 items
    assert results[0].fetched == 24, results[0]
    # 2 symbols × 2 periods × 3 indicators
    assert results[1].fetched == 12, results[1]

    r_c = svc.run(
        FetchRequest(
            kind="consensus",
            symbols=["600000", "000001"],
            end="2026-07-24",
        )
    )
    assert r_c.status == "committed" and r_c.fetched == 4, r_c

    r2 = svc.run(FetchRequest(kind="statement", symbols=["600000", "000001"]))
    assert r2.updated == 24 and r2.inserted == 0, r2

    counts = FundamentalRepository().counts()
    assert counts["raw_fund_statement"] >= 24
    assert counts["raw_fund_indicator"] >= 12
    assert counts["raw_consensus_estimate"] >= 4
    print("selfcheck OK:", counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
