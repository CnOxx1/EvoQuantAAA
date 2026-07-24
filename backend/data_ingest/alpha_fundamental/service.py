from __future__ import annotations

import logging
from dataclasses import dataclass

from data_ingest.alpha_fundamental.models import (
    P1_KINDS,
    VALID_KINDS,
    FetchRequest,
    UpsertStats,
)
from data_ingest.alpha_fundamental.repository import FundamentalRepository
from data_ingest.alpha_fundamental.sources import get_source
from data_ingest.alpha_fundamental.sources.base import FundamentalSource
from data_ingest.ingest_common.batch import BatchManager

logger = logging.getLogger(__name__)

MODULE_NAME = "alpha_fundamental"


@dataclass
class IngestResult:
    batch_id: str
    status: str
    kind: str
    fetched: int
    inserted: int
    updated: int
    message: str = ""


class FundamentalIngestService:
    """ALPHA 基本面：拉源 → 落 raw_fund_* / consensus → commit batch。"""

    def __init__(self, source: FundamentalSource | None = None) -> None:
        self.source = source or get_source("akshare")
        self.batches = BatchManager()
        self.repo = FundamentalRepository()

    def run(self, request: FetchRequest) -> IngestResult:
        if request.kind not in VALID_KINDS:
            raise ValueError(f"非法 ingest_kind: {request.kind}; 允许: {VALID_KINDS}")
        if request.kind in {"statement", "indicator"} and not request.symbols:
            raise ValueError(f"{request.kind} 必须提供 --symbol")
        # consensus 允许不传 symbol（全市场快照）；传了则过滤

        batch = self.batches.create(
            ingest_module=MODULE_NAME,
            ingest_kind=request.kind,
            lane="ALPHA",
            job_id=request.job_id,
            meta={
                "source": self.source.source,
                "symbols": request.symbols,
                "statement_types": request.statement_types,
                "start": request.start,
                "end": request.end,
            },
        )
        try:
            bundle = self.source.fetch(request)
            stats: UpsertStats = self.repo.upsert_bundle(batch.batch_id, bundle)
            self.batches.commit(batch.batch_id)
            logger.info(
                "alpha_fundamental committed batch_id=%s kind=%s fetched=%s inserted=%s updated=%s",
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
            logger.exception("alpha_fundamental failed batch_id=%s", batch.batch_id)
            return IngestResult(
                batch_id=batch.batch_id,
                status="failed",
                kind=request.kind,
                fetched=0,
                inserted=0,
                updated=0,
                message=str(exc),
            )

    def run_p1(self, request_base: FetchRequest) -> list[IngestResult]:
        """P1：statement → indicator。"""
        results: list[IngestResult] = []
        for kind in P1_KINDS:
            req = FetchRequest(
                kind=kind,  # type: ignore[arg-type]
                start=request_base.start,
                end=request_base.end,
                symbols=list(request_base.symbols),
                statement_types=list(request_base.statement_types),
                job_id=request_base.job_id,
            )
            results.append(self.run(req))
            if results[-1].status != "committed":
                break
        return results
