from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from research_lab.evaluate import evaluate_factor, format_eval_report
from research_lab.factors import (
    compute_flow_net_5,
    compute_mom_20,
    compute_tech_level,
    compute_tech_ma20_bias,
    compute_val_pe_pct,
)
from research_lab.models import FACTOR_CODES, ResearchRequest, ResearchResult
from research_lab.repository import ResearchRepository

logger = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class ResearchService:
    def __init__(self, *, repo: ResearchRepository | None = None) -> None:
        self.repo = repo or ResearchRepository()

    def run(self, request: ResearchRequest) -> ResearchResult:
        if request.factor_code not in FACTOR_CODES:
            raise ValueError(f"不支持的因子: {request.factor_code}")
        if not (request.start and request.end):
            raise ValueError("需要 --start 与 --end")
        start, end = request.start[:10], request.end[:10]
        run_id = f"rs_{uuid.uuid4().hex}"
        created = _utcnow()

        if request.require_dq:
            gate = self.repo.require_dq_passed(
                start=start, end=end, factor_type=request.factor_type
            )
            if not gate or gate.get("status") != "passed":
                return ResearchResult(
                    status="failed",
                    run_id=run_id,
                    factor_code=request.factor_code,
                    universe_code=request.universe_code,
                    start=start,
                    end=end,
                    message=(
                        "dq_gate 未 passed，禁止研究消费该区间"
                        "（可用 --no-dq-check 仅调试）"
                    ),
                )

        snapshot_id, symbols = self.repo.load_universe_symbols(
            universe_code=request.universe_code,
            as_of=start,
            as_of_end=end,
        )
        if not symbols:
            return ResearchResult(
                status="failed",
                run_id=run_id,
                factor_code=request.factor_code,
                universe_code=request.universe_code,
                start=start,
                end=end,
                message=(
                    f"Universe {request.universe_code} 在 {start}~{end} 无快照，"
                    f"请先: python main.py security_master --universe "
                    f"{request.universe_code} --as-of {start}"
                ),
            )

        meta: dict[str, Any] = {
            "universe_snapshot_id": snapshot_id,
            "symbol_count": len(symbols),
            "factor_type": request.factor_type,
            "job_id": request.job_id,
        }
        self.repo.create_run(
            {
                "run_id": run_id,
                "factor_code": request.factor_code,
                "universe_code": request.universe_code,
                "start_date": start,
                "end_date": end,
                "status": "running",
                "meta": meta,
                "created_at": created,
            }
        )

        try:
            rows = self._compute(request, symbols=symbols, start=start, end=end)
            n = self.repo.upsert_factor_values(
                rows=rows,
                factor_code=request.factor_code,
                universe_code=request.universe_code,
                run_id=run_id,
                created_at=created,
            )
            meta["row_count"] = n
            meta["dates"] = sorted({str(r["trade_date"])[:10] for r in rows})
            self.repo.finish_run(run_id=run_id, status="committed", meta=meta)
            logger.info(
                "research committed run=%s factor=%s rows=%s",
                run_id,
                request.factor_code,
                n,
            )
            return ResearchResult(
                status="committed",
                run_id=run_id,
                factor_code=request.factor_code,
                universe_code=request.universe_code,
                start=start,
                end=end,
                row_count=n,
                meta=meta,
                message=f"rows={n}",
            )
        except Exception as exc:
            logger.exception("research failed")
            meta["error"] = str(exc)
            self.repo.finish_run(run_id=run_id, status="failed", meta=meta)
            return ResearchResult(
                status="failed",
                run_id=run_id,
                factor_code=request.factor_code,
                universe_code=request.universe_code,
                start=start,
                end=end,
                message=str(exc),
                meta=meta,
            )

    def _compute(
        self,
        request: ResearchRequest,
        *,
        symbols: list[str],
        start: str,
        end: str,
    ) -> list[dict[str, Any]]:
        code = request.factor_code
        if code == "MOM_20":
            bars = self.repo.load_equity_bars(
                start=start,
                end=end,
                symbols=symbols,
                factor_type=request.factor_type,
                lookback_calendar_days=60,
            )
            return compute_mom_20(bars, start=start, end=end)

        if code == "VAL_PE_PCT":
            vals = self.repo.load_valuations(
                start=start, end=end, symbols=symbols
            )
            return compute_val_pe_pct(
                vals, symbols=set(symbols), start=start, end=end
            )

        if code == "FLOW_NET_5":
            flows = self.repo.load_stock_flows(
                start=start, end=end, symbols=symbols, lookback_calendar_days=14
            )
            bars = self.repo.load_equity_bars(
                start=start,
                end=end,
                symbols=symbols,
                factor_type=request.factor_type,
                lookback_calendar_days=14,
            )
            return compute_flow_net_5(flows, bars, start=start, end=end)

        if code == "TECH_RSI_14":
            tech = self.repo.load_tech_indicators(
                start=start,
                end=end,
                symbols=symbols,
                factor_type=request.factor_type,
                indicator_codes=["RSI_14"],
            )
            return compute_tech_level(
                tech, indicator_code="RSI_14", start=start, end=end
            )

        if code == "TECH_MACD_HIST":
            tech = self.repo.load_tech_indicators(
                start=start,
                end=end,
                symbols=symbols,
                factor_type=request.factor_type,
                indicator_codes=["MACD_HIST"],
            )
            return compute_tech_level(
                tech, indicator_code="MACD_HIST", start=start, end=end
            )

        if code == "TECH_MA20_BIAS":
            tech = self.repo.load_tech_indicators(
                start=start,
                end=end,
                symbols=symbols,
                factor_type=request.factor_type,
                indicator_codes=["MA_20"],
            )
            bars = self.repo.load_equity_bars(
                start=start,
                end=end,
                symbols=symbols,
                factor_type=request.factor_type,
                lookback_calendar_days=0,
            )
            return compute_tech_ma20_bias(tech, bars, start=start, end=end)

        raise ValueError(f"不支持的因子: {code}")

    def evaluate(self, request: ResearchRequest) -> ResearchResult:
        """对已落库因子做 IC / 分层；结果写入 research_run.meta_json。"""
        if request.factor_code not in FACTOR_CODES:
            raise ValueError(f"不支持的因子: {request.factor_code}")
        start, end = request.start[:10], request.end[:10]
        run_id = f"re_{uuid.uuid4().hex}"
        created = _utcnow()

        if request.require_dq:
            gate = self.repo.require_dq_passed(
                start=start, end=end, factor_type=request.factor_type
            )
            if not gate or gate.get("status") != "passed":
                return ResearchResult(
                    status="failed",
                    run_id=run_id,
                    factor_code=request.factor_code,
                    universe_code=request.universe_code,
                    start=start,
                    end=end,
                    message="dq_gate 未 passed，禁止评估（可用 --no-dq-check 仅调试）",
                )

        snapshot_id, symbols = self.repo.load_universe_symbols(
            universe_code=request.universe_code,
            as_of=start,
            as_of_end=end,
        )
        if not symbols:
            return ResearchResult(
                status="failed",
                run_id=run_id,
                factor_code=request.factor_code,
                universe_code=request.universe_code,
                start=start,
                end=end,
                message=f"Universe {request.universe_code} 无快照",
            )

        factor_rows = self.repo.load_factor_values(
            factor_code=request.factor_code,
            universe_code=request.universe_code,
            start=start,
            end=end,
            symbols=symbols,
        )
        if not factor_rows:
            return ResearchResult(
                status="failed",
                run_id=run_id,
                factor_code=request.factor_code,
                universe_code=request.universe_code,
                start=start,
                end=end,
                message="无因子值，请先: python main.py research --factor ...",
            )

        bars = self.repo.load_equity_bars(
            start=start,
            end=end,
            symbols=symbols,
            factor_type=request.factor_type,
            lookback_calendar_days=5,
        )
        report = evaluate_factor(factor_rows=factor_rows, ret_rows=bars)
        meta: dict[str, Any] = {
            "mode": "evaluate",
            "universe_snapshot_id": snapshot_id,
            "symbol_count": len(symbols),
            "factor_rows": len(factor_rows),
            "report": report,
            "report_text": format_eval_report(request.factor_code, report),
        }
        self.repo.create_run(
            {
                "run_id": run_id,
                "factor_code": request.factor_code,
                "universe_code": request.universe_code,
                "start_date": start,
                "end_date": end,
                "status": "committed",
                "meta": meta,
                "created_at": created,
            }
        )
        return ResearchResult(
            status="committed",
            run_id=run_id,
            factor_code=request.factor_code,
            universe_code=request.universe_code,
            start=start,
            end=end,
            row_count=len(factor_rows),
            meta=meta,
            message=meta["report_text"],
        )
