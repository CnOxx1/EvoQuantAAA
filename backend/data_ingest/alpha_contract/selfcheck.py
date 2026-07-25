"""本地自检：python -m data_ingest.alpha_contract.selfcheck"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from data_ingest.alpha_contract.models import FetchRequest
from data_ingest.alpha_contract.repository import ContractRepository
from data_ingest.alpha_contract.service import ContractIngestService
from data_ingest.alpha_contract.sources import get_source
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
        conn.execute("DELETE FROM raw_major_contract WHERE source='mock'")
        conn.execute("DELETE FROM ingest_batch WHERE ingest_module='alpha_contract'")

    svc = ContractIngestService(source=get_source("mock"))
    r1 = svc.run(
        FetchRequest(kind="major_contract", start="2026-07-01", end="2026-07-25")
    )
    assert r1.status == "committed" and r1.fetched == 2, r1

    r2 = svc.run(FetchRequest(kind="win_bid", start="2026-07-01", end="2026-07-25"))
    assert r2.status == "committed" and r2.fetched == 1, r2

    # 幂等
    r3 = svc.run(FetchRequest(kind="win_bid", start="2026-07-01", end="2026-07-25"))
    assert r3.status == "committed" and r3.updated >= 1, r3

    n = ContractRepository().count(source="mock", win_bid_only=True)
    assert n >= 1, n
    print("selfcheck OK: win_bid_rows=", n, "total_mock=", ContractRepository().count(source="mock"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
