from __future__ import annotations

import logging
from dataclasses import dataclass

from data_ingest.alpha_contract.models import VALID_KINDS, FetchRequest, UpsertStats
from data_ingest.alpha_contract.repository import ContractRepository
from data_ingest.alpha_contract.sources import get_source
from data_ingest.alpha_contract.sources.base import ContractSource
from data_ingest.ingest_common.batch import BatchManager

logger = logging.getLogger(__name__)

MODULE_NAME = "alpha_contract"


@dataclass
class IngestResult:
    batch_id: str
    status: str
    kind: str
    fetched: int
    inserted: int
    updated: int
    message: str = ""


class ContractIngestService:
    """ALPHA 重大合同 / 中标：拉源 → 落 raw_major_contract → commit。"""

    def __init__(self, source: ContractSource | None = None) -> None:
        self.source = source or get_source("akshare")
        self.batches = BatchManager()
        self.repo = ContractRepository()

    def run(self, request: FetchRequest) -> IngestResult:
        if request.kind not in VALID_KINDS:
            raise ValueError(f"非法 ingest_kind: {request.kind}; 允许: {VALID_KINDS}")
        if not (request.start and request.end):
            raise ValueError(f"{request.kind} 必须提供 --start 与 --end")

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
                "alpha_contract committed batch_id=%s kind=%s fetched=%s inserted=%s updated=%s",
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
            logger.exception("alpha_contract failed batch_id=%s", batch.batch_id)
            return IngestResult(
                batch_id=batch.batch_id,
                status="failed",
                kind=request.kind,
                fetched=0,
                inserted=0,
                updated=0,
                message=str(exc),
            )
