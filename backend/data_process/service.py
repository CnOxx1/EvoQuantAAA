from __future__ import annotations

import logging
from datetime import datetime, timezone

from data_process.batch import ProcessBatchManager
from data_process.compute import build_equity_processed_rows, build_index_processed_rows
from data_process.models import P0_KINDS, ProcessRequest, ProcessResult
from data_process.repository import ProcessRepository

logger = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class DataProcessService:
    def __init__(
        self,
        *,
        repo: ProcessRepository | None = None,
        batches: ProcessBatchManager | None = None,
    ) -> None:
        self.repo = repo or ProcessRepository()
        self.batches = batches or ProcessBatchManager()

    def run(self, request: ProcessRequest) -> ProcessResult:
        if request.kind == "equity_1d":
            return self._run_equity(request)
        if request.kind == "index_1d":
            return self._run_index(request)
        raise ValueError(f"unsupported process kind: {request.kind}")

    def run_p0(self, request_base: ProcessRequest) -> list[ProcessResult]:
        results: list[ProcessResult] = []
        for kind in P0_KINDS:
            req = ProcessRequest(
                kind=kind,
                start=request_base.start,
                end=request_base.end,
                symbols=list(request_base.symbols),
                index_symbols=list(request_base.index_symbols) or ["000300"],
                factor_type=request_base.factor_type,
                preferred_source=request_base.preferred_source,
                job_id=request_base.job_id,
            )
            results.append(self.run(req))
        return results

    def _run_equity(self, request: ProcessRequest) -> ProcessResult:
        info = self.batches.create(
            process_kind="equity_1d",
            job_id=request.job_id,
            meta={
                "start": request.start,
                "end": request.end,
                "symbols": request.symbols,
                "factor_type": request.factor_type,
                "preferred_source": request.preferred_source,
            },
        )
        try:
            bars = self.repo.load_equity_bars(
                start=request.start,
                end=request.end,
                symbols=request.symbols,
                preferred_source=request.preferred_source,
            )
            if not bars:
                raise RuntimeError("无可用 raw_equity_bar_1d 输入")

            symbols = request.symbols or sorted({str(b["symbol"]) for b in bars})
            factors = self.repo.load_adj_factors(
                start=request.start,
                end=request.end,
                symbols=symbols,
                factor_type=request.factor_type,
                preferred_source=request.preferred_source,
            )
            suspended = self.repo.load_suspend_keys(
                start=request.start, end=request.end, symbols=symbols
            )
            limit_up, limit_down = self.repo.load_limit_keys(
                start=request.start, end=request.end, symbols=symbols
            )
            rows, skipped = build_equity_processed_rows(
                bars=bars,
                factors=factors,
                suspended=suspended,
                limit_up=limit_up,
                limit_down=limit_down,
                factor_type=request.factor_type,
                process_batch_id=info.process_batch_id,
                processed_at=_utcnow(),
            )
            if not rows:
                raise RuntimeError(
                    f"加工结果为空：输入 {len(bars)} 行，缺因子跳过 {skipped}"
                )
            inserted, updated = self.repo.upsert_equity_rows(rows)
            self.batches.commit(info.process_batch_id)
            msg = ""
            if skipped:
                msg = f"skipped_no_factor={skipped}"
            logger.info(
                "data_process committed kind=equity_1d batch=%s out=%s",
                info.process_batch_id,
                len(rows),
            )
            return ProcessResult(
                kind="equity_1d",
                status="committed",
                process_batch_id=info.process_batch_id,
                input_rows=len(bars),
                output_rows=len(rows),
                inserted=inserted,
                updated=updated,
                skipped_no_factor=skipped,
                message=msg,
            )
        except Exception as exc:
            logger.exception("data_process equity_1d failed")
            self.batches.fail(info.process_batch_id, str(exc))
            return ProcessResult(
                kind="equity_1d",
                status="failed",
                process_batch_id=info.process_batch_id,
                message=str(exc),
            )

    def _run_index(self, request: ProcessRequest) -> ProcessResult:
        indexes = list(request.index_symbols) or ["000300"]
        info = self.batches.create(
            process_kind="index_1d",
            job_id=request.job_id,
            meta={
                "start": request.start,
                "end": request.end,
                "index_symbols": indexes,
                "preferred_source": request.preferred_source,
            },
        )
        try:
            bars = self.repo.load_index_bars(
                start=request.start,
                end=request.end,
                index_symbols=indexes,
                preferred_source=request.preferred_source,
            )
            if not bars:
                raise RuntimeError("无可用 raw_index_bar_1d 输入")
            rows = build_index_processed_rows(
                bars=bars,
                process_batch_id=info.process_batch_id,
                processed_at=_utcnow(),
            )
            inserted, updated = self.repo.upsert_index_rows(rows)
            self.batches.commit(info.process_batch_id)
            logger.info(
                "data_process committed kind=index_1d batch=%s out=%s",
                info.process_batch_id,
                len(rows),
            )
            return ProcessResult(
                kind="index_1d",
                status="committed",
                process_batch_id=info.process_batch_id,
                input_rows=len(bars),
                output_rows=len(rows),
                inserted=inserted,
                updated=updated,
            )
        except Exception as exc:
            logger.exception("data_process index_1d failed")
            self.batches.fail(info.process_batch_id, str(exc))
            return ProcessResult(
                kind="index_1d",
                status="failed",
                process_batch_id=info.process_batch_id,
                message=str(exc),
            )
