"""本地自检：python -m data_ingest.alpha_flow.selfcheck"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from data_ingest.alpha_flow.models import FetchRequest
from data_ingest.alpha_flow.repository import FlowRepository
from data_ingest.alpha_flow.service import FlowIngestService
from data_ingest.alpha_flow.sources import get_source
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
            "raw_money_flow",
            "raw_margin",
            "raw_dragon_tiger",
            "raw_block_trade",
        ):
            conn.execute(f"DELETE FROM {t} WHERE source='mock'")
        conn.execute("DELETE FROM ingest_batch WHERE ingest_module='alpha_flow'")

    svc = FlowIngestService(source=get_source("mock"))
    base = FetchRequest(
        kind="northbound",
        start="2026-07-21",
        end="2026-07-23",
        symbols=["600000", "000001"],
    )
    results = svc.run_p1(base)
    assert all(r.status == "committed" for r in results), results
    # 3 日 × 3 flow_type
    assert results[0].fetched == 9, results[0]
    # 2 标的 × 3 日
    assert results[1].fetched == 6, results[1]

    for kind, expect in (
        ("margin", 3),
        ("dragon_tiger", 1),
        ("block_trade", 1),
    ):
        r = svc.run(
            FetchRequest(
                kind=kind,  # type: ignore[arg-type]
                start="2026-07-21",
                end="2026-07-23",
            )
        )
        assert r.status == "committed" and r.fetched == expect, (kind, r)

    counts = FlowRepository().counts()
    assert counts["raw_money_flow"] >= 15
    print("selfcheck OK:", counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
