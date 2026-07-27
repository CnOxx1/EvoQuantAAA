from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from data_process.batch import ProcessBatchManager
from data_process.compute import build_equity_processed_rows, build_index_processed_rows
from data_process.fund_pit import build_fund_pit_intervals
from data_process.limit_derive import derive_limit_keys
from data_process.min_bars import build_min_processed_rows
from data_process.models import P0_KINDS, ProcessRequest, ProcessResult
from data_process.repository import ProcessRepository
from data_process.tech_catalog import SUITE_CORE, SUITE_FULL
from data_process.tech_indicator import (
    compute_tech_indicator_rows,
    lookback_days_for_suite,
)

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
        if request.kind == "fundamental_pit":
            return self._run_fundamental_pit(request)
        if request.kind == "tech_indicator":
            return self._run_tech_indicator(request)
        if request.kind in ("equity_15m", "equity_60m"):
            return self._run_equity_min(request)
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
            st_rows = self.repo.load_special_treat(symbols=symbols)
            limit_up, limit_down, derived = derive_limit_keys(
                bars=bars,
                st_rows=st_rows,
                existing_up=limit_up,
                existing_down=limit_down,
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
            if derived:
                dkeys = derived
                for row in rows:
                    key = (str(row["symbol"]), str(row["trade_date"])[:10])
                    if key in dkeys:
                        src = str(row.get("source") or "")
                        if "limit_derived" not in src:
                            row["source"] = f"{src}|limit_derived" if src else "limit_derived"
            if not rows:
                raise RuntimeError(
                    f"加工结果为空：输入 {len(bars)} 行，缺因子跳过 {skipped}"
                )
            inserted, updated = self.repo.upsert_equity_rows(rows)
            self.batches.commit(info.process_batch_id)
            msg_parts = []
            if skipped:
                msg_parts.append(f"skipped_no_factor={skipped}")
            if derived:
                msg_parts.append(f"limit_derived={len(derived)}")
            msg = ";".join(msg_parts)
            logger.info(
                "data_process committed kind=equity_1d batch=%s out=%s derived=%s",
                info.process_batch_id,
                len(rows),
                len(derived),
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

    def _run_fundamental_pit(self, request: ProcessRequest) -> ProcessResult:
        info = self.batches.create(
            process_kind="fundamental_pit",
            job_id=request.job_id,
            meta={
                "symbols": request.symbols,
                "preferred_source": request.preferred_source,
            },
        )
        try:
            stmts = self.repo.load_fund_statements(
                symbols=request.symbols,
                preferred_source=request.preferred_source,
            )
            inds = self.repo.load_fund_indicators(
                symbols=request.symbols,
                preferred_source=request.preferred_source,
            )
            if not stmts and not inds:
                raise RuntimeError("无 raw_fund_statement / raw_fund_indicator 输入")
            rows = build_fund_pit_intervals(
                statement_rows=stmts,
                indicator_rows=inds,
                process_batch_id=info.process_batch_id,
                processed_at=_utcnow(),
            )
            if not rows:
                raise RuntimeError("PIT 区间为空（检查 announce_date）")
            inserted, updated = self.repo.upsert_fund_snapshot_rows(rows)
            self.batches.commit(info.process_batch_id)
            logger.info(
                "data_process committed kind=fundamental_pit batch=%s out=%s",
                info.process_batch_id,
                len(rows),
            )
            return ProcessResult(
                kind="fundamental_pit",
                status="committed",
                process_batch_id=info.process_batch_id,
                input_rows=len(stmts) + len(inds),
                output_rows=len(rows),
                inserted=inserted,
                updated=updated,
            )
        except Exception as exc:
            logger.exception("data_process fundamental_pit failed")
            self.batches.fail(info.process_batch_id, str(exc))
            return ProcessResult(
                kind="fundamental_pit",
                status="failed",
                process_batch_id=info.process_batch_id,
                message=str(exc),
            )

    def _run_equity_min(self, request: ProcessRequest) -> ProcessResult:
        freq = "15m" if request.kind == "equity_15m" else "60m"
        info = self.batches.create(
            process_kind=request.kind,
            job_id=request.job_id,
            meta={
                "start": request.start,
                "end": request.end,
                "symbols": request.symbols,
                "freq": freq,
                "factor_type": request.factor_type,
            },
        )
        try:
            bars = self.repo.load_raw_equity_min_bars(
                start=request.start,
                end=request.end,
                symbols=list(request.symbols),
                freq=freq,
                preferred_source=request.preferred_source,
            )
            if not bars:
                raise RuntimeError(f"无可用 raw_equity_bar_min freq={freq}")
            symbols = request.symbols or sorted({str(b["symbol"]) for b in bars})
            # 复权因子按日；分钟 bar 用当日因子
            factors = self.repo.load_adj_factors(
                start=request.start,
                end=request.end,
                symbols=symbols,
                factor_type=request.factor_type,
                preferred_source=request.preferred_source,
            )
            rows, skipped = build_min_processed_rows(
                bars,
                factors=factors,
                factor_type=request.factor_type,
                process_batch_id=info.process_batch_id,
                processed_at=_utcnow(),
            )
            if not rows:
                raise RuntimeError(
                    f"分钟加工结果为空：输入 {len(bars)}，缺因子跳过 {skipped}"
                )
            inserted, updated = self.repo.upsert_min_equity_rows(rows)
            self.batches.commit(info.process_batch_id)
            return ProcessResult(
                kind=request.kind,
                status="committed",
                process_batch_id=info.process_batch_id,
                input_rows=len(bars),
                output_rows=len(rows),
                inserted=inserted,
                updated=updated,
                skipped_no_factor=skipped,
                message=f"freq={freq};skipped_no_factor={skipped}",
            )
        except Exception as exc:
            logger.exception("data_process %s failed", request.kind)
            self.batches.fail(info.process_batch_id, str(exc))
            return ProcessResult(
                kind=request.kind,
                status="failed",
                process_batch_id=info.process_batch_id,
                message=str(exc),
            )

    def _run_tech_indicator(self, request: ProcessRequest) -> ProcessResult:
        """读 processed 日线/分钟算指标；不拉外部；缺 bar 跳过。"""
        if not request.start or not request.end:
            raise ValueError("tech_indicator 需要 --start 与 --end")
        suite = (request.suite or SUITE_CORE).strip().lower()
        if suite not in {SUITE_CORE, SUITE_FULL}:
            raise ValueError("suite 仅支持 core|full")
        freq = (request.freq or "1d").strip().lower()
        if freq not in {"1d", "15m", "60m"}:
            raise ValueError("freq 仅支持 1d|15m|60m")
        start = request.start[:10]
        end = request.end[:10]
        chunk_size = max(1, int(request.chunk_size or 100))
        if suite == SUITE_FULL and chunk_size > 20:
            chunk_size = 20
        lookback = lookback_days_for_suite(suite)
        load_start = (date.fromisoformat(start) - timedelta(days=lookback)).isoformat()
        cats = [c.strip() for c in (request.categories or []) if c.strip()]
        sentinel = "MA_5" if suite == SUITE_CORE else "AO_5_34"

        if freq == "1d":
            with_bars = self.repo.list_symbols_with_processed_bars(
                start=start,
                end=end,
                symbols=list(request.symbols),
                factor_type=request.factor_type,
            )
        else:
            with_bars = self.repo.list_symbols_with_processed_min_bars(
                start=start,
                end=end,
                symbols=list(request.symbols),
                freq=freq,
                factor_type=request.factor_type,
            )
        requested = list(request.symbols)
        skipped_no_bars = (
            len(set(requested) - set(with_bars)) if requested else 0
        )
        if request.force:
            targets = with_bars
        elif freq == "1d":
            targets = self.repo.list_symbols_incomplete_indicators(
                start=start,
                end=end,
                symbols=with_bars,
                factor_type=request.factor_type,
                sentinel_code=sentinel,
            )
        else:
            targets = self.repo.list_symbols_incomplete_min_indicators(
                start=start,
                end=end,
                symbols=with_bars,
                freq=freq,
                factor_type=request.factor_type,
                sentinel_code=sentinel,
            )

        info = self.batches.create(
            process_kind="tech_indicator",
            job_id=request.job_id,
            meta={
                "start": start,
                "end": end,
                "factor_type": request.factor_type,
                "force": request.force,
                "suite": suite,
                "freq": freq,
                "categories": cats,
                "chunk_size": chunk_size,
                "symbols_requested": len(requested),
                "symbols_with_bars": len(with_bars),
                "symbols_to_compute": len(targets),
                "lookback_calendar_days": lookback,
                "sentinel": sentinel,
            },
        )
        try:
            if not targets:
                self.batches.commit(info.process_batch_id)
                msg = (
                    f"suite={suite};freq={freq};skipped_no_bars={skipped_no_bars};"
                    f"symbols_with_bars={len(with_bars)};nothing_to_compute"
                )
                return ProcessResult(
                    kind="tech_indicator",
                    status="committed",
                    process_batch_id=info.process_batch_id,
                    input_rows=0,
                    output_rows=0,
                    message=msg,
                )

            total_in = 0
            total_out = 0
            inserted = 0
            updated = 0
            processed_at = _utcnow()
            src_label = (
                "processed_equity_bar_1d"
                if freq == "1d"
                else f"processed_equity_bar_min:{freq}"
            )
            for i in range(0, len(targets), chunk_size):
                part = targets[i : i + chunk_size]
                if freq == "1d":
                    bars = self.repo.load_processed_equity_bars(
                        start=load_start,
                        end=end,
                        symbols=part,
                        factor_type=request.factor_type,
                    )
                else:
                    bars = self.repo.load_processed_equity_min_bars(
                        start=load_start,
                        end=end,
                        symbols=part,
                        freq=freq,
                        factor_type=request.factor_type,
                    )
                total_in += len(bars)
                rows = compute_tech_indicator_rows(
                    bars,
                    start=start,
                    end=end,
                    factor_type=request.factor_type,
                    process_batch_id=info.process_batch_id,
                    processed_at=processed_at,
                    source=src_label,
                    suite=suite,
                    categories=cats or None,
                    freq=freq,
                )
                if freq == "1d":
                    ins, upd = self.repo.upsert_tech_indicator_rows(rows)
                else:
                    ins, upd = self.repo.upsert_tech_indicator_min_rows(rows)
                inserted += ins
                updated += upd
                total_out += len(rows)
                logger.info(
                    "tech_indicator suite=%s freq=%s chunk %s/%s symbols=%s rows=%s",
                    suite,
                    freq,
                    min(i + chunk_size, len(targets)),
                    len(targets),
                    len(part),
                    len(rows),
                )

            self.batches.commit(info.process_batch_id)
            msg = (
                f"suite={suite};freq={freq};skipped_no_bars={skipped_no_bars};"
                f"symbols_computed={len(targets)};chunks="
                f"{(len(targets) + chunk_size - 1) // chunk_size}"
            )
            return ProcessResult(
                kind="tech_indicator",
                status="committed",
                process_batch_id=info.process_batch_id,
                input_rows=total_in,
                output_rows=total_out,
                inserted=inserted,
                updated=updated,
                message=msg,
            )
        except Exception as exc:
            logger.exception("data_process tech_indicator failed")
            self.batches.fail(info.process_batch_id, str(exc))
            return ProcessResult(
                kind="tech_indicator",
                status="failed",
                process_batch_id=info.process_batch_id,
                message=str(exc),
            )
