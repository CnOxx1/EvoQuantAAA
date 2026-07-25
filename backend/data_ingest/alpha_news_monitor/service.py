from __future__ import annotations

import logging
from dataclasses import dataclass

from data_ingest.alpha_news_monitor.models import VALID_KINDS, FetchRequest
from data_ingest.alpha_news_monitor.repository import NewsRepository
from data_ingest.alpha_news_monitor.sources import get_source
from data_ingest.alpha_news_monitor.sources.base import FetchResult, NewsSource
from data_ingest.alpha_news_monitor.sources.mock import MockNewsSource
from data_ingest.ingest_common.batch import BatchManager

logger = logging.getLogger(__name__)

MODULE_NAME = "alpha_news_monitor"
_WATERMARK_KINDS = frozenset(
    {
        "news_incremental",
        "news_watchlist",
        "news_official",
        "news_forum",
        "news_policy",
    }
)


@dataclass
class IngestResult:
    batch_id: str
    status: str
    fetched: int
    inserted: int
    updated: int
    watermark: str | None
    message: str = ""


class NewsIngestService:
    def __init__(
        self,
        source: NewsSource | None = None,
        *,
        fallback_mock_on_error: bool = False,
    ) -> None:
        self.source = source or get_source("akshare")
        self.fallback_mock_on_error = fallback_mock_on_error
        self.batches = BatchManager()
        self.repo = NewsRepository()

    def run(self, request: FetchRequest) -> IngestResult:
        if request.kind not in VALID_KINDS:
            raise ValueError(f"非法 ingest_kind: {request.kind}")
        if request.kind == "news_watchlist" and not request.symbols:
            raise ValueError("news_watchlist 必须提供 --symbol")

        active = self.source
        watch_key = self._watch_key(request)
        # channel 在 fetch 前按 kind 预设，便于水位读写
        channel = {
            "news_official": "official",
            "news_forum": "forum",
            "news_policy": "policy",
        }.get(request.kind, getattr(active, "channel", "eastmoney"))
        since = None
        if request.kind in _WATERMARK_KINDS:
            since = self.repo.get_watermark(active.source, channel, watch_key)

        batch = self.batches.create(
            ingest_module=MODULE_NAME,
            ingest_kind=request.kind,
            lane="ALPHA",
            job_id=request.job_id,
            meta={
                "source": active.source,
                "channel": channel,
                "watch_key": watch_key,
                "since": since,
                "media_filters": request.media_filters,
                "forum_top_n": request.forum_top_n,
            },
        )
        try:
            fetch_result, active = self._fetch(active, request, since=since)
            stats = self.repo.upsert_many(batch.batch_id, fetch_result.records)
            new_wm = since
            if request.kind in _WATERMARK_KINDS:
                # fetch 可能改写 source.channel
                channel = getattr(active, "channel", channel) or channel
                if fetch_result.max_publish_time and (
                    since is None or fetch_result.max_publish_time > since
                ):
                    new_wm = fetch_result.max_publish_time
                    self.repo.set_watermark(
                        active.source, channel, new_wm, watch_key
                    )
            self.batches.commit(batch.batch_id)
            return IngestResult(
                batch_id=batch.batch_id,
                status="committed",
                fetched=len(fetch_result.records),
                inserted=stats.inserted,
                updated=stats.updated,
                watermark=new_wm,
            )
        except Exception as exc:  # noqa: BLE001
            self.batches.fail(batch.batch_id, str(exc))
            logger.exception("news ingest failed batch_id=%s", batch.batch_id)
            return IngestResult(
                batch_id=batch.batch_id,
                status="failed",
                fetched=0,
                inserted=0,
                updated=0,
                watermark=since,
                message=str(exc),
            )

    def _fetch(
        self, source: NewsSource, request: FetchRequest, *, since: str | None
    ) -> tuple[FetchResult, NewsSource]:
        try:
            return source.fetch(request, since=since), source
        except Exception:
            if not self.fallback_mock_on_error or isinstance(source, MockNewsSource):
                raise
            mock = MockNewsSource()
            return mock.fetch(request, since=since), mock

    @staticmethod
    def _watch_key(request: FetchRequest) -> str:
        if request.kind == "news_watchlist":
            return "watch:" + ",".join(sorted(request.symbols or []))
        if (
            request.kind in {"news_official", "news_forum", "news_policy"}
            and request.media_filters
        ):
            return "media:" + ",".join(sorted(m.lower() for m in request.media_filters))
        return ""
