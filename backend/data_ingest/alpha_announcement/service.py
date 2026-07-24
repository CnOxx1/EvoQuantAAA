from __future__ import annotations

import logging
from dataclasses import dataclass

from data_ingest.alpha_announcement.models import VALID_KINDS, FetchRequest
from data_ingest.alpha_announcement.repository import AnnouncementRepository
from data_ingest.alpha_announcement.sources import get_source
from data_ingest.alpha_announcement.sources.base import AnnouncementSource, FetchResult
from data_ingest.alpha_announcement.sources.mock import MockAnnouncementSource
from data_ingest.ingest_common.batch import BatchManager

logger = logging.getLogger(__name__)

MODULE_NAME = "alpha_announcement"
_WATERMARK_KINDS = frozenset({"ann_incremental", "ann_watchlist"})


@dataclass
class IngestResult:
    batch_id: str
    status: str
    fetched: int
    upserted: int
    inserted: int
    updated: int
    watermark: str | None
    message: str = ""


class AnnouncementIngestService:
    """公告获取：拉源 → 落 raw_announcement → 更新水位 → commit batch。"""

    def __init__(
        self,
        source: AnnouncementSource | None = None,
        *,
        fallback_mock_on_error: bool = True,
    ) -> None:
        self.source = source or get_source("eastmoney")
        self.fallback_mock_on_error = fallback_mock_on_error
        self.batches = BatchManager()
        self.repo = AnnouncementRepository()

    def run(self, request: FetchRequest) -> IngestResult:
        if request.kind not in VALID_KINDS:
            raise ValueError(f"非法 ingest_kind: {request.kind}; 允许: {VALID_KINDS}")
        if request.kind == "ann_watchlist" and not request.symbols:
            raise ValueError("ann_watchlist 必须提供 --symbol")
        if request.kind == "ann_by_category" and not request.categories:
            raise ValueError("ann_by_category 必须提供 --category")

        active_source = self.source
        watch_key = self._watch_key(request)
        since = None
        if request.kind in _WATERMARK_KINDS:
            since = self.repo.get_watermark(
                active_source.source, active_source.channel, watch_key
            )

        batch = self.batches.create(
            ingest_module=MODULE_NAME,
            ingest_kind=request.kind,
            lane="ALPHA",
            job_id=request.job_id,
            meta={
                "source": active_source.source,
                "channel": active_source.channel,
                "watch_key": watch_key,
                "since": since,
            },
        )

        try:
            fetch_result, active_source = self._fetch(
                active_source, request, since=since
            )
            stats = self.repo.upsert_many(batch.batch_id, fetch_result.records)

            # 仅增量/订阅更新水位；无新数据时保持原水位，禁止回退
            new_wm = since
            if request.kind in _WATERMARK_KINDS:
                if fetch_result.max_publish_time and (
                    since is None or fetch_result.max_publish_time > since
                ):
                    new_wm = fetch_result.max_publish_time
                    self.repo.set_watermark(
                        active_source.source,
                        active_source.channel,
                        new_wm,
                        watch_key,
                    )

            self.batches.commit(batch.batch_id)
            logger.info(
                "announcement ingest committed batch_id=%s kind=%s fetched=%s inserted=%s updated=%s wm=%s",
                batch.batch_id,
                request.kind,
                len(fetch_result.records),
                stats.inserted,
                stats.updated,
                new_wm,
            )
            return IngestResult(
                batch_id=batch.batch_id,
                status="committed",
                fetched=len(fetch_result.records),
                upserted=stats.inserted + stats.updated,
                inserted=stats.inserted,
                updated=stats.updated,
                watermark=new_wm,
            )
        except Exception as exc:  # noqa: BLE001
            self.batches.fail(batch.batch_id, str(exc))
            # 网络类失败常见，避免堆栈刷屏；其它异常保留堆栈
            if exc.__class__.__name__ in {
                "ConnectionError",
                "Timeout",
                "ConnectTimeout",
                "ReadTimeout",
            } or "NameResolutionError" in repr(exc):
                logger.error(
                    "announcement ingest failed batch_id=%s err=%s",
                    batch.batch_id,
                    exc,
                )
            else:
                logger.exception(
                    "announcement ingest failed batch_id=%s", batch.batch_id
                )
            return IngestResult(
                batch_id=batch.batch_id,
                status="failed",
                fetched=0,
                upserted=0,
                inserted=0,
                updated=0,
                watermark=since,
                message=str(exc),
            )

    def _fetch(
        self,
        source: AnnouncementSource,
        request: FetchRequest,
        *,
        since: str | None,
    ) -> tuple[FetchResult, AnnouncementSource]:
        try:
            return source.fetch(request, since=since), source
        except Exception:
            if not self.fallback_mock_on_error or isinstance(source, MockAnnouncementSource):
                raise
            logger.warning(
                "primary source %s failed, fallback to mock (不污染原 source 配置)",
                source.source,
            )
            mock = MockAnnouncementSource()
            return mock.fetch(request, since=since), mock

    @staticmethod
    def _watch_key(request: FetchRequest) -> str:
        if request.kind == "ann_watchlist":
            symbols = ",".join(sorted(request.symbols or []))
            return f"watch:{symbols}"
        return ""
