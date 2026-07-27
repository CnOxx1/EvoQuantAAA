"""本地自检：python -m data_ingest.alpha_news_monitor.selfcheck"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from data_ingest.alpha_news_monitor.dedupe import dedupe_news_records
from data_ingest.alpha_news_monitor.models import FetchRequest, NewsRecord
from data_ingest.alpha_news_monitor.repository import NewsRepository, lookback_watermark
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

    # 纯函数：重复标题去重
    dups = dedupe_news_records(
        [
            NewsRecord(
                source_news_id="a",
                title="重复标题测试",
                publish_time="2026-07-01T10:00:00+00:00",
                channel="official",
                source="mock_a",
            ),
            NewsRecord(
                source_news_id="b",
                title="重复标题测试",
                publish_time="2026-07-01T11:00:00+00:00",
                channel="official",
                source="mock_b",
            ),
        ]
    )
    assert len(dups) == 1 and dups[0].source == "mock_a"
    assert lookback_watermark("2026-07-02T00:00:00+00:00", hours=24).startswith(
        "2026-07-01"
    )

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

    r4 = svc.run(FetchRequest(kind="news_policy"))
    assert r4.status == "committed" and r4.fetched >= 2, r4

    r5 = svc.run(FetchRequest(kind="news_forum", symbols=["600000"], forum_top_n=5))
    assert r5.status == "committed" and r5.fetched >= 1, r5

    print("selfcheck OK: news_count=", NewsRepository().count_news())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
