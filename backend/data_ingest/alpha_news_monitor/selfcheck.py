"""本地自检：python -m data_ingest.alpha_news_monitor.selfcheck"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from data_ingest.alpha_news_monitor.models import FetchRequest
from data_ingest.alpha_news_monitor.repository import NewsRepository
from data_ingest.alpha_news_monitor.service import NewsIngestService
from data_ingest.alpha_news_monitor.sources import get_source
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
        conn.execute("DELETE FROM raw_news_media WHERE source='mock'")
        conn.execute("DELETE FROM ingest_news_watermark WHERE source='mock'")
        conn.execute(
            "DELETE FROM ingest_batch WHERE ingest_module='alpha_news_monitor'"
        )

    svc = NewsIngestService(source=get_source("mock"))
    r1 = svc.run(FetchRequest(kind="news_incremental"))
    assert r1.status == "committed" and r1.fetched >= 3, r1
    wm = r1.watermark
    assert wm

    r2 = svc.run(FetchRequest(kind="news_incremental"))
    # 水位推进后动态样本可能仍更新；至少不应回退水位
    assert r2.status == "committed"
    assert r2.watermark and r2.watermark >= wm

    r3 = svc.run(FetchRequest(kind="news_watchlist", symbols=["600000"]))
    assert r3.status == "committed" and r3.fetched >= 1, r3

    print("selfcheck OK: news_count=", NewsRepository().count_news())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
