from __future__ import annotations

import logging
from dataclasses import dataclass

from data_ingest.alpha_flow.models import P1_KINDS, VALID_KINDS, FetchRequest, UpsertStats
from data_ingest.alpha_flow.repository import FlowRepository
from data_ingest.alpha_flow.sources import get_source
from data_ingest.alpha_flow.sources.base import FlowSource
from data_ingest.ingest_common.batch import BatchManager
from shared.ingest_batching import chunk_symbols

logger = logging.getLogger(__name__)

MODULE_NAME = "alpha_flow"


@dataclass
class IngestResult:
    batch_id: str
    status: str
    kind: str
    fetched: int
    inserted: int
    updated: int
    message: str = ""


class FlowIngestService:
    """ALPHA 资金流：拉源 → 落 raw_* → commit batch。"""

    def __init__(self, source: FlowSource | None = None) -> None:
        self.source = source or get_source("akshare")
        self.batches = BatchManager()
        self.repo = FlowRepository()

    def run(self, request: FetchRequest) -> IngestResult:
        if request.kind not in VALID_KINDS:
            raise ValueError(f"非法 ingest_kind: {request.kind}; 允许: {VALID_KINDS}")
        if not (request.start and request.end):
            raise ValueError(f"{request.kind} 必须提供 --start 与 --end")
        if request.kind == "stock_flow" and not request.symbols:
            raise ValueError("stock_flow 必须提供 --symbol")

        batch = self.batches.create(
            ingest_module=MODULE_NAME,
            ingest_kind=request.kind,
            lane="ALPHA",
            job_id=request.job_id,
            meta={
                "source": self.source.source,
                "symbols": request.symbols,
                "start": request.start,
                "end": request.end,
            },
        )
        try:
            bundle = self.source.fetch(request)
            stats: UpsertStats = self.repo.upsert_bundle(batch.batch_id, bundle)
            self.batches.commit(batch.batch_id)
            logger.info(
                "alpha_flow committed batch_id=%s kind=%s fetched=%s inserted=%s updated=%s",
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
            logger.exception("alpha_flow failed batch_id=%s", batch.batch_id)
            return IngestResult(
                batch_id=batch.batch_id,
                status="failed",
                kind=request.kind,
                fetched=0,
                inserted=0,
                updated=0,
                message=str(exc),
            )

    def run_stock_flow_chunked(
        self,
        request_base: FetchRequest,
        *,
        chunk_size: int = 15,
    ) -> list[IngestResult]:
        """stock_flow 按标的分块；单 chunk 失败不中断。"""
        results: list[IngestResult] = []
        offset = 0
        for part in chunk_symbols(list(request_base.symbols), chunk_size):
            req = FetchRequest(
                kind="stock_flow",
                start=request_base.start,
                end=request_base.end,
                symbols=part,
                job_id=request_base.job_id,
            )
            r = self.run(req)
            results.append(r)
            logger.info(
                "alpha_flow chunk stock_flow [%s:%s] status=%s fetched=%s",
                offset,
                offset + len(part),
                r.status,
                r.fetched,
            )
            offset += len(part)
        return results

    def run_p1(self, request_base: FetchRequest) -> list[IngestResult]:
        results: list[IngestResult] = []
        for kind in P1_KINDS:
            req = FetchRequest(
                kind=kind,  # type: ignore[arg-type]
                start=request_base.start,
                end=request_base.end,
                symbols=list(request_base.symbols),
                job_id=request_base.job_id,
            )
            results.append(self.run(req))
            if results[-1].status != "committed":
                break
        return results

    def run_p1_chunked(
        self,
        request_base: FetchRequest,
        *,
        chunk_size: int = 15,
    ) -> list[IngestResult]:
        """P1：northbound 一次 + stock_flow 分块。"""
        results: list[IngestResult] = [
            self.run(
                FetchRequest(
                    kind="northbound",
                    start=request_base.start,
                    end=request_base.end,
                    symbols=[],
                    job_id=request_base.job_id,
                )
            )
        ]
        results.extend(
            self.run_stock_flow_chunked(request_base, chunk_size=chunk_size)
        )
        return results
