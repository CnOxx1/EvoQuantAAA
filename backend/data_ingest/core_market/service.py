from __future__ import annotations

import logging
from dataclasses import dataclass

from data_ingest.core_market.models import P0_KINDS, VALID_KINDS, FetchRequest, UpsertStats
from data_ingest.core_market.repository import CoreMarketRepository
from data_ingest.core_market.sources import get_source
from data_ingest.core_market.sources.base import CoreMarketSource
from data_ingest.ingest_common.batch import BatchManager

logger = logging.getLogger(__name__)

MODULE_NAME = "core_market"
_SYMBOL_KINDS = frozenset({"equity_1d", "adj_factor", "corp_action"})
_RANGE_KINDS = frozenset(
    {"equity_1d", "adj_factor", "suspend", "limit", "index_1d", "corp_action"}
)
_MARKET_WIDE_P0 = ("suspend", "limit", "index_1d")
_PER_SYMBOL_P0 = ("equity_1d", "adj_factor")


@dataclass
class IngestResult:
    batch_id: str
    status: str
    kind: str
    fetched: int
    inserted: int
    updated: int
    message: str = ""


class CoreMarketIngestService:
    """CORE 行情：按 kind 拉取 → 落对应 raw_* → commit batch。"""

    def __init__(self, source: CoreMarketSource | None = None) -> None:
        self.source = source or get_source("akshare")
        self.batches = BatchManager()
        self.repo = CoreMarketRepository()

    def run(self, request: FetchRequest) -> IngestResult:
        if request.kind not in VALID_KINDS:
            raise ValueError(f"非法 ingest_kind: {request.kind}; 允许: {VALID_KINDS}")
        if request.kind in _RANGE_KINDS and not (request.start and request.end):
            raise ValueError(f"{request.kind} 必须提供 --start 与 --end")
        if request.kind in _SYMBOL_KINDS and not request.symbols:
            raise ValueError(f"{request.kind} 必须提供 --symbol")
        if request.kind == "index_1d" and not request.index_symbols:
            request.index_symbols = ["000300"]

        batch = self.batches.create(
            ingest_module=MODULE_NAME,
            ingest_kind=request.kind,
            lane="CORE",
            job_id=request.job_id,
            meta={
                "source": self.source.source,
                "symbols": request.symbols,
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
                "core_market committed batch_id=%s kind=%s fetched=%s inserted=%s updated=%s",
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
            logger.exception("core_market failed batch_id=%s", batch.batch_id)
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
        """P0：equity_1d → adj_factor → suspend → limit → index_1d。"""
        results: list[IngestResult] = []
        for kind in P0_KINDS:
            req = FetchRequest(
                kind=kind,  # type: ignore[arg-type]
                start=request_base.start,
                end=request_base.end,
                symbols=list(request_base.symbols),
                index_symbols=list(request_base.index_symbols),
                job_id=request_base.job_id,
            )
            results.append(self.run(req))
            if results[-1].status != "committed":
                break
        return results

    def run_p0_chunked(
        self,
        request_base: FetchRequest,
        *,
        chunk_size: int = 15,
    ) -> list[IngestResult]:
        """
        覆盖型 P0：全市场类 kind 各跑一次；equity/adj 按 chunk 提交。
        单 chunk 失败不中断后续（便于 HS300 增量灌数）。
        """
        if chunk_size < 1:
            raise ValueError("chunk_size 必须 >= 1")
        symbols = list(request_base.symbols)
        results: list[IngestResult] = []

        # 先灌逐票行情，再灌区间事件（事件不依赖 symbols）
        for kind in _PER_SYMBOL_P0:
            for i in range(0, len(symbols), chunk_size):
                part = symbols[i : i + chunk_size]
                req = FetchRequest(
                    kind=kind,  # type: ignore[arg-type]
                    start=request_base.start,
                    end=request_base.end,
                    symbols=part,
                    index_symbols=list(request_base.index_symbols),
                    job_id=request_base.job_id,
                )
                r = self.run(req)
                results.append(r)
                logger.info(
                    "core_market chunk kind=%s [%s:%s] status=%s fetched=%s",
                    kind,
                    i,
                    i + len(part),
                    r.status,
                    r.fetched,
                )

        for kind in _MARKET_WIDE_P0:
            req = FetchRequest(
                kind=kind,  # type: ignore[arg-type]
                start=request_base.start,
                end=request_base.end,
                symbols=[],
                index_symbols=list(request_base.index_symbols) or ["000300"],
                job_id=request_base.job_id,
            )
            results.append(self.run(req))
        return results
