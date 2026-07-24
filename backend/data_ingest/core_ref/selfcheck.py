"""本地自检：python -m data_ingest.core_ref.selfcheck"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from data_ingest.core_ref.models import FetchRequest
from data_ingest.core_ref.repository import CoreRefRepository
from data_ingest.core_ref.service import CoreRefIngestService
from data_ingest.core_ref.sources import get_source
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
            "raw_trade_calendar",
            "raw_security_listing",
            "raw_industry_class",
            "raw_share_capital",
            "raw_index_member",
            "raw_special_treat",
        ):
            conn.execute(f"DELETE FROM {t} WHERE source='mock'")
        conn.execute("DELETE FROM ingest_batch WHERE ingest_module='core_ref'")

    svc = CoreRefIngestService(source=get_source("mock"))
    base = FetchRequest(
        kind="calendar",
        start="2026-07-01",
        end="2026-07-31",
        exchange="SSE",
    )
    results = svc.run_p0(base)
    assert all(r.status == "committed" for r in results), results
    assert results[0].fetched == 31, results[0]  # July 2026 days
    assert results[1].inserted == 5, results[1]

    r_idx = svc.run(
        FetchRequest(
            kind="index_member",
            end="2026-07-24",
            index_symbols=["000300"],
        )
    )
    assert r_idx.status == "committed" and r_idx.inserted == 4, r_idx

    r_st = svc.run(FetchRequest(kind="special_treat"))
    assert r_st.status == "committed" and r_st.inserted == 1, r_st

    # 幂等：再跑 listing 应全是 update
    r_list2 = svc.run(FetchRequest(kind="listing"))
    assert r_list2.updated == 5 and r_list2.inserted == 0, r_list2

    counts = CoreRefRepository().counts()
    assert counts["raw_trade_calendar"] >= 31
    assert counts["raw_security_listing"] >= 5
    print("selfcheck OK:", counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
