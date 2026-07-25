"""本地自检：python -m data_ingest.alpha_relation.selfcheck"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from data_ingest.alpha_relation.models import FetchRequest
from data_ingest.alpha_relation.repository import RelationRepository
from data_ingest.alpha_relation.service import RelationIngestService
from data_ingest.alpha_relation.sources import get_source
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
        conn.execute("DELETE FROM raw_stock_relation WHERE source='mock'")
        conn.execute("DELETE FROM ingest_batch WHERE ingest_module='alpha_relation'")

    svc = RelationIngestService(source=get_source("mock"))
    r1 = svc.run(
        FetchRequest(
            kind="hot_relate",
            symbols=["600519", "000858"],
            end="2026-07-25",
        )
    )
    assert r1.status == "committed" and r1.fetched >= 1, r1

    r2 = svc.run(
        FetchRequest(kind="holder_team", holder_type="社保", end="2026-07-25")
    )
    assert r2.status == "committed" and r2.fetched >= 1, r2

    r3 = svc.run(
        FetchRequest(
            kind="board_co",
            board_type="CONCEPT",
            board_names=["人工智能"],
            end="2026-07-25",
        )
    )
    assert r3.status == "committed" and r3.fetched >= 1, r3

    n = RelationRepository().count(source="mock")
    assert n >= 3, n
    print("selfcheck OK: relation_rows=", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
