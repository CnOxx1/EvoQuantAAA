"""本地自检（不依赖外网）：python -m data_ingest.alpha_announcement.selfcheck"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from data_ingest.alpha_announcement.models import FetchRequest
from data_ingest.alpha_announcement.repository import AnnouncementRepository
from data_ingest.alpha_announcement.service import AnnouncementIngestService
from data_ingest.alpha_announcement.sources import get_source
from shared.db import apply_migration_file
from shared.logging_utils import setup_logging


def main() -> int:
    setup_logging("WARNING")
    repo_root = BACKEND_ROOT.parent
    apply_migration_file(repo_root / "database" / "migrations" / "001_alpha_announcement.sql")

    # 清理 mock 水位，避免污染
    from shared.db import get_conn

    with get_conn() as conn:
        conn.execute("DELETE FROM ingest_announcement_watermark WHERE source='mock'")
        conn.execute("DELETE FROM raw_announcement WHERE source='mock'")
        conn.execute("DELETE FROM ingest_batch WHERE ingest_module='alpha_announcement'")

    svc = AnnouncementIngestService(source=get_source("mock"), fallback_mock_on_error=False)
    r1 = svc.run(FetchRequest(kind="ann_incremental"))
    assert r1.status == "committed" and r1.inserted >= 4, r1

    r2 = svc.run(FetchRequest(kind="ann_incremental"))
    assert r2.status == "committed" and r2.fetched == 0, r2  # 水位生效

    r3 = svc.run(FetchRequest(kind="ann_watchlist", symbols=["600000"]))
    assert r3.status == "committed" and r3.fetched >= 1, r3

    r4 = svc.run(
        FetchRequest(kind="ann_backfill", start="2026-07-21", end="2026-07-23")
    )
    assert r4.status == "committed" and r4.fetched == 3, r4

    r5 = svc.run(FetchRequest(kind="ann_by_category", categories=["investigation"]))
    assert r5.status == "committed" and r5.fetched == 1, r5

    r6 = svc.run(FetchRequest(kind="ann_by_category", categories=["win_bid"]))
    assert r6.status == "committed" and r6.fetched == 1, r6  # 仅标题含中标

    r7 = svc.run(FetchRequest(kind="ann_by_category", categories=["major_contract"]))
    # major_contract 桶含 win_bid + 纯重大合同
    assert r7.status == "committed" and r7.fetched == 2, r7

    try:
        svc.run(FetchRequest(kind="ann_watchlist"))
        raise AssertionError("expected ValueError")
    except ValueError:
        pass

    total = AnnouncementRepository().count_announcements()
    print(
        f"selfcheck OK: batches committed, watermark works, "
        f"win_bid/major_contract filters ok, ann_count>={total}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
