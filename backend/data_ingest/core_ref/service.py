from __future__ import annotations

import logging
from dataclasses import dataclass

from data_ingest.core_ref.models import VALID_KINDS, FetchRequest, UpsertStats
from data_ingest.core_ref.repository import CoreRefRepository
from data_ingest.core_ref.sources import get_source
from data_ingest.core_ref.sources.base import CoreRefSource
from data_ingest.ingest_common.batch import BatchManager

logger = logging.getLogger(__name__)

MODULE_NAME = "core_ref"


@dataclass
class IngestResult:
    batch_id: str
    status: str
    kind: str
    fetched: int
    inserted: int
    updated: int
    message: str = ""


class CoreRefIngestService:
    """CORE 参考数据：按 kind 拉取 → 落对应 raw_* → commit batch。"""

    def __init__(self, source: CoreRefSource | None = None) -> None:
        self.source = source or get_source("akshare")
        self.batches = BatchManager()
        self.repo = CoreRefRepository()

    def run(self, request: FetchRequest) -> IngestResult:
        if request.kind not in VALID_KINDS:
            raise ValueError(f"非法 ingest_kind: {request.kind}; 允许: {VALID_KINDS}")
        if request.kind == "calendar" and not (request.start and request.end):
            raise ValueError("calendar 必须提供 --start 与 --end")
        if request.kind == "index_member" and not request.index_symbols:
            # 允许默认指数，由 mock 填 000300；真实源应强制
            request.index_symbols = ["000300"]

        batch = self.batches.create(
            ingest_module=MODULE_NAME,
            ingest_kind=request.kind,
            lane="CORE",
            job_id=request.job_id,
            meta={
                "source": self.source.source,
                "exchange": request.exchange,
                "industry_standard": request.industry_standard,
                "index_symbols": request.index_symbols,
                "start": request.start,
                "end": request.end,
            },
        )
        try:
            bundle = self.source.fetch(request)
            stats: UpsertStats = self.repo.upsert_bundle(batch.batch_id, bundle)
            self.batches.commit(batch.batch_id)
            logger.info(
                "core_ref committed batch_id=%s kind=%s fetched=%s inserted=%s updated=%s",
                batch.batch_id,
                request.kind,
                len(bundle.rows),
                stats.inserted,
                stats.updated,
            )
            return IngestResult(
                batch_id=batch.batch_id,
                status="committed",
                kind=request.kind,
                fetched=len(bundle.rows),
                inserted=stats.inserted,
                updated=stats.updated,
            )
        except Exception as exc:  # noqa: BLE001
            self.batches.fail(batch.batch_id, str(exc))
            logger.exception("core_ref failed batch_id=%s", batch.batch_id)
            return IngestResult(
                batch_id=batch.batch_id,
                status="failed",
                kind=request.kind,
                fetched=0,
                inserted=0,
                updated=0,
                message=str(exc),
            )

    def run_p0(self, request_base: FetchRequest) -> list[IngestResult]:
        """按约定顺序跑齐 P0：calendar → listing → industry → share_capital。"""
        results: list[IngestResult] = []
        for kind in ("calendar", "listing", "industry", "share_capital"):
            req = FetchRequest(
                kind=kind,  # type: ignore[arg-type]
                start=request_base.start,
                end=request_base.end,
                exchange=request_base.exchange,
                industry_standard=request_base.industry_standard,
                job_id=request_base.job_id,
            )
            if kind != "calendar":
                # listing 等不强制日期，但保留透传
                pass
            results.append(self.run(req))
            if results[-1].status != "committed":
                break
        return results
