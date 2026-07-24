from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from data_ingest.alpha_announcement.timeutil import normalize_publish_time
from data_ingest.alpha_news_monitor.models import FetchRequest, NewsRecord
from data_ingest.alpha_news_monitor.sources.base import FetchResult, NewsSource


class MockNewsSource(NewsSource):
    source = "mock"
    channel = "mock"

    _SAMPLES = (
        ("600000", "浦发银行相关市场评论", "媒体A", "2026-07-20T02:00:00+00:00"),
        ("000001", "平安银行获机构调研", "媒体B", "2026-07-21T03:00:00+00:00"),
        (None, "宏观：央行公开市场操作", "财联社", "2026-07-22T04:00:00+00:00"),
    )

    def fetch(self, request: FetchRequest, *, since: str | None = None) -> FetchResult:
        symbols = set(request.symbols or [])
        since_n = normalize_publish_time(since) if since else None
        records: list[NewsRecord] = []
        for symbol, title, media, publish in self._SAMPLES:
            if symbols and (symbol is None or symbol not in symbols):
                continue
            pt = normalize_publish_time(publish)
            if since_n and pt <= since_n:
                continue
            nid = hashlib.sha1(f"{symbol}|{title}|{pt}".encode()).hexdigest()[:16]
            records.append(
                NewsRecord(
                    source_news_id=f"mock-{nid}",
                    symbol=symbol,
                    title=title,
                    summary=title,
                    publish_time=pt,
                    url=f"https://example.local/news/{nid}",
                    media_source=media,
                    channel=self.channel,
                    source=self.source,
                )
            )
        if request.kind in ("news_incremental", "news_watchlist") and not since_n:
            now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
            symbol = (request.symbols or [None])[0]
            title = "模拟最新资讯"
            pt = now.isoformat()
            nid = hashlib.sha1(f"{symbol}|{title}|{pt}".encode()).hexdigest()[:16]
            records.append(
                NewsRecord(
                    source_news_id=f"mock-{nid}",
                    symbol=symbol,
                    title=title,
                    summary=title,
                    publish_time=pt,
                    url=f"https://example.local/news/{nid}",
                    media_source="mock",
                    channel=self.channel,
                    source=self.source,
                )
            )
        max_pt = max((r.publish_time for r in records), default=None)
        return FetchResult(records=records, max_publish_time=max_pt)
