from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from data_ingest.alpha_announcement.category import (
    matches_requested_categories,
    normalize_category,
)
from data_ingest.alpha_announcement.models import AnnouncementRecord, FetchRequest
from data_ingest.alpha_announcement.sources.base import AnnouncementSource, FetchResult
from data_ingest.alpha_announcement.timeutil import normalize_publish_time


class MockAnnouncementSource(AnnouncementSource):
    """稳定夹具源：幂等 ID 固定，便于验证水位与去重。"""

    source = "mock"
    channel = "mock"

    # 固定点时样本（UTC）
    _SAMPLES = (
        ("600000", "关于股份减持计划的公告", "减持", "2026-07-20T02:00:00+00:00"),
        ("000001", "2025年业绩预告", "业绩预告", "2026-07-21T03:00:00+00:00"),
        ("300750", "立案调查通知书", "立案调查", "2026-07-22T04:00:00+00:00"),
        ("601318", "回购股份方案公告", "回购", "2026-07-23T05:00:00+00:00"),
        ("600284", "浦东建设重大项目中标公告", "重大合同", "2026-07-24T06:00:00+00:00"),
        ("002428", "关于签署日常经营重大合同的公告", "重大合同", "2026-07-24T07:00:00+00:00"),
    )

    def fetch(self, request: FetchRequest, *, since: str | None = None) -> FetchResult:
        symbols = set(request.symbols or [])
        since_n = normalize_publish_time(since) if since else None
        start_n = normalize_publish_time(request.start) if request.start else None
        end_n = normalize_publish_time(request.end + "T23:59:59") if request.end else None

        records: list[AnnouncementRecord] = []
        for symbol, title, cat, publish in self._SAMPLES:
            if symbols and symbol not in symbols:
                continue
            publish_n = normalize_publish_time(publish)
            if since_n and publish_n <= since_n:
                continue
            if start_n and publish_n < start_n:
                continue
            if end_n and publish_n > end_n:
                continue
            norm = normalize_category(cat, title)
            if request.categories and not matches_requested_categories(
                category_norm=norm,
                category_raw=cat,
                requested=request.categories,
            ):
                continue
            ann_id = hashlib.sha1(f"{symbol}|{title}|{publish_n}".encode()).hexdigest()[:16]
            records.append(
                AnnouncementRecord(
                    source_ann_id=f"mock-{ann_id}",
                    symbol=symbol,
                    title=title,
                    publish_time=publish_n,
                    category_raw=cat,
                    category_norm=norm,
                    url=f"https://example.local/ann/{symbol}",
                    channel=self.channel,
                    source=self.source,
                )
            )

        # 增量联调：若无 since 且未指定回填区间，附加一条“当前小时”动态样本，模拟新公告
        if request.kind in ("ann_incremental", "ann_watchlist") and not request.start:
            now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
            dyn_pub = now.isoformat()
            if not since_n or dyn_pub > since_n:
                symbol = (request.symbols or ["600000"])[0]
                title = "模拟最新公告"
                cat = "其他"
                if not request.categories or "其他" in request.categories:
                    ann_id = hashlib.sha1(f"{symbol}|{title}|{dyn_pub}".encode()).hexdigest()[:16]
                    records.append(
                        AnnouncementRecord(
                            source_ann_id=f"mock-{ann_id}",
                            symbol=symbol,
                            title=title,
                            publish_time=dyn_pub,
                            category_raw=cat,
                            category_norm=normalize_category(cat, title),
                            url=f"https://example.local/ann/{symbol}/latest",
                            channel=self.channel,
                            source=self.source,
                        )
                    )

        max_pt = max((r.publish_time for r in records), default=None)
        return FetchResult(records=records, max_publish_time=max_pt)
