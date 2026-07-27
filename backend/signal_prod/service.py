from __future__ import annotations

import logging
import uuid
from datetime import date, timedelta
from typing import Any

from signal_prod.models import SignalRunRequest, SignalRunResult
from signal_prod.repository import SignalProdRepository
from signal_prod.weights import build_factor_top_n_weights

logger = logging.getLogger(__name__)


def _utcnow() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class SignalProdService:
    def __init__(self, *, repo: SignalProdRepository | None = None) -> None:
        self.repo = repo or SignalProdRepository()

    def run(self, request: SignalRunRequest) -> SignalRunResult:
        if not (request.start and request.end):
            return SignalRunResult(status="invalid", message="需要 --start 与 --end")
        start, end = request.start[:10], request.end[:10]
        batch_id = f"sg_{uuid.uuid4().hex}"
        created = _utcnow()

        strat = self.repo.load_strategy(request.strategy_version)
        if not strat:
            return SignalRunResult(
                status="failed",
                signal_batch_id=batch_id,
                strategy_version=request.strategy_version,
                message="strategy_version 不存在",
            )
        status = str(strat["status"])
        if status not in ("PAPER", "LIVE"):
            return SignalRunResult(
                status="failed",
                signal_batch_id=batch_id,
                strategy_version=request.strategy_version,
                strategy_code=str(strat["strategy_code"]),
                message=f"仅 PAPER/LIVE 可生产信号，当前={status}",
            )

        kind = str(strat["strategy_kind"])
        params: dict[str, Any] = dict(strat.get("params") or {})
        if kind != "FACTOR_TOP_N":
            return SignalRunResult(
                status="failed",
                signal_batch_id=batch_id,
                strategy_version=request.strategy_version,
                strategy_code=str(strat["strategy_code"]),
                message=f"暂不支持 strategy_kind={kind}",
            )

        factor_code = str(params["factor_code"])
        top_n = int(params["top_n"])
        rebalance_days = int(params["rebalance_days"])
        universe_code = str(params.get("universe_code") or "TOP100")
        factor_type = str(params.get("factor_type") or "qfq")

        if request.require_dq:
            gate = self.repo.require_dq_passed(
                start=start, end=end, factor_type=factor_type
            )
            if not gate or gate.get("status") != "passed":
                return SignalRunResult(
                    status="failed",
                    signal_batch_id=batch_id,
                    strategy_version=request.strategy_version,
                    strategy_code=str(strat["strategy_code"]),
                    start=start,
                    end=end,
                    message=(
                        "dq_gate 未 passed，禁止生产信号"
                        "（可用 --no-dq-check 仅调试）"
                    ),
                )

        snapshot_id, symbols = self.repo.load_universe_symbols(
            universe_code=universe_code, as_of=start, as_of_end=end
        )
        if not symbols:
            return SignalRunResult(
                status="failed",
                signal_batch_id=batch_id,
                strategy_version=request.strategy_version,
                strategy_code=str(strat["strategy_code"]),
                start=start,
                end=end,
                message=f"Universe {universe_code} 无快照",
            )

        # 为「前一日因子」留日历缓冲
        bar_start = (date.fromisoformat(start) - timedelta(days=40)).isoformat()
        dates, symbols_by_date = self.repo.load_trade_dates_with_bars(
            start=bar_start,
            end=end,
            symbols=symbols,
            factor_type=factor_type,
        )
        # 仅输出落在请求区间内的调仓日
        dates_in_range = [d for d in dates if start <= d <= end]
        if len(dates) < 2 or not dates_in_range:
            return SignalRunResult(
                status="failed",
                signal_batch_id=batch_id,
                strategy_version=request.strategy_version,
                strategy_code=str(strat["strategy_code"]),
                start=start,
                end=end,
                message="区间内交易日不足或无 processed 行情",
            )

        factor_rows = self.repo.load_factor_values(
            factor_code=factor_code,
            universe_code=universe_code,
            start=start,
            end=end,
            symbols=symbols,
        )
        meta = {
            "strategy_kind": kind,
            "factor_code": factor_code,
            "top_n": top_n,
            "rebalance_days": rebalance_days,
            "universe_code": universe_code,
            "universe_snapshot_id": snapshot_id,
            "factor_type": factor_type,
            "job_id": request.job_id,
            "as_of": request.as_of,
        }
        self.repo.create_batch(
            {
                "signal_batch_id": batch_id,
                "strategy_version": request.strategy_version,
                "status": "running",
                "start_date": start,
                "end_date": end,
                "as_of_date": (request.as_of or end)[:10],
                "universe_code": universe_code,
                "universe_snapshot_id": snapshot_id,
                "row_count": 0,
                "job_id": request.job_id,
                "meta": meta,
                "created_at": created,
            }
        )

        try:
            # 用含 lookback 的 dates 建目标，再过滤到请求区间
            all_rows = build_factor_top_n_weights(
                trade_dates=dates,
                symbols_by_date=symbols_by_date,
                factor_rows=factor_rows,
                top_n=top_n,
                rebalance_days=rebalance_days,
            )
            rows = [r for r in all_rows if start <= r["trade_date"] <= end]
            if not rows:
                # 日更单日：非调仓日视为 skipped，不打断 schedule
                single_day = start == end
                st = "skipped" if single_day else "failed"
                msg = (
                    "非调仓日或无可建权重（单日 skipped）"
                    if single_day
                    else "无调仓日权重（检查因子是否已落库、区间是否足够）"
                )
                self.repo.finish_batch(
                    signal_batch_id=batch_id,
                    status=st,
                    row_count=0,
                    finished_at=_utcnow(),
                    error_message=msg,
                    meta=meta,
                )
                return SignalRunResult(
                    status=st,
                    signal_batch_id=batch_id,
                    strategy_version=request.strategy_version,
                    strategy_code=str(strat["strategy_code"]),
                    start=start,
                    end=end,
                    message=msg,
                )

            n = self.repo.upsert_weights(
                rows=rows,
                strategy_version=request.strategy_version,
                signal_batch_id=batch_id,
                created_at=created,
            )
            self.repo.finish_batch(
                signal_batch_id=batch_id,
                status="committed",
                row_count=n,
                finished_at=_utcnow(),
                meta=meta,
            )
            logger.info(
                "signal committed batch=%s version=%s rows=%s",
                batch_id,
                request.strategy_version,
                n,
            )
            return SignalRunResult(
                status="committed",
                signal_batch_id=batch_id,
                strategy_version=request.strategy_version,
                strategy_code=str(strat["strategy_code"]),
                start=start,
                end=end,
                row_count=n,
                meta=meta,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("signal run failed")
            self.repo.finish_batch(
                signal_batch_id=batch_id,
                status="failed",
                row_count=0,
                finished_at=_utcnow(),
                error_message=str(exc),
                meta=meta,
            )
            return SignalRunResult(
                status="failed",
                signal_batch_id=batch_id,
                strategy_version=request.strategy_version,
                strategy_code=str(strat["strategy_code"]),
                start=start,
                end=end,
                message=str(exc),
            )

    def run_all_runnable(
        self,
        *,
        start: str,
        end: str,
        as_of: str | None = None,
        require_dq: bool = True,
        job_id: str | None = None,
        statuses: set[str] | None = None,
    ) -> list[SignalRunResult]:
        want = statuses or {"LIVE", "PAPER"}
        versions = [
            v
            for v in self.repo.list_runnable_versions()
            if str(v["status"]) in want
        ]
        if not versions:
            return [
                SignalRunResult(
                    status="skipped",
                    message="无 PAPER/LIVE 策略可运行",
                )
            ]
        return [
            self.run(
                SignalRunRequest(
                    strategy_version=str(v["strategy_version"]),
                    start=start,
                    end=end,
                    as_of=as_of,
                    require_dq=require_dq,
                    job_id=job_id,
                )
            )
            for v in versions
        ]
