from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from research_lab.evaluate import evaluate_factor, format_eval_report
from research_lab.evidence import (
    format_evidence_pack,
    soft_verdict,
    summarize_oos,
    year_windows,
)
from research_lab.factors import (
    compute_flow_net_5,
    compute_mom_20,
    compute_tech_level,
    compute_tech_ma20_bias,
    compute_val_pe_pct,
)
from research_lab.models import (
    FACTOR_CODES,
    EvidenceRequest,
    EvidenceResult,
    ResearchRequest,
    ResearchResult,
)
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

    def evidence(self, request: EvidenceRequest) -> EvidenceResult:
        """
        多因子证据包：全样本 IC + 可选年切 OOS；结果写入一条 research_run
        （factor_code=EVIDENCE_PACK, meta.mode=evidence）。
        回测由 CLI 编排后经 attach_backtests 合并，避免跨模块 import。
        """
        start, end = request.start[:10], request.end[:10]
        run_id = f"re_{uuid.uuid4().hex}"
        created = _utcnow()
        codes = list(request.factor_codes) or list(FACTOR_CODES)

        if request.require_dq:
            gate = self.repo.require_dq_passed(
                start=start, end=end, factor_type=request.factor_type
            )
            if not gate or gate.get("status") != "passed":
                return EvidenceResult(
                    status="failed",
                    run_id=run_id,
                    universe_code=request.universe_code,
                    start=start,
                    end=end,
                    message="dq_gate 未 passed（可用 --no-dq-check 仅调试）",
                )

        factors_out: dict[str, Any] = {}
        any_ok = False
        for code in codes:
            if code not in FACTOR_CODES:
                factors_out[code] = {
                    "status": "invalid",
                    "message": f"不支持的因子: {code}",
                }
                continue
            req = ResearchRequest(
                factor_code=code,  # type: ignore[arg-type]
                start=start,
                end=end,
                universe_code=request.universe_code,
                factor_type=request.factor_type,
                require_dq=False,  # 已在包级检查
                job_id=request.job_id,
            )
            if request.compute_first:
                comp = self.run(req)
                if comp.status != "committed":
                    factors_out[code] = {
                        "status": "failed",
                        "message": f"compute failed: {comp.message}",
                        "compute_run_id": comp.run_id,
                    }
                    continue

            ev = self.evaluate(req)
            row: dict[str, Any] = {
                "status": ev.status,
                "evaluate_run_id": ev.run_id,
                "message": ev.message if ev.status != "committed" else "",
            }
            if ev.status == "committed":
                any_ok = True
                report = (ev.meta or {}).get("report") or {}
                row["report"] = report
                row["verdict"] = soft_verdict(report, request.soft_gates)
                if request.year_split:
                    snapshot_id, symbols = self.repo.load_universe_symbols(
                        universe_code=request.universe_code,
                        as_of=start,
                        as_of_end=end,
                    )
                    factor_rows = self.repo.load_factor_values(
                        factor_code=code,
                        universe_code=request.universe_code,
                        start=start,
                        end=end,
                        symbols=symbols,
                    )
                    bars = self.repo.load_equity_bars(
                        start=start,
                        end=end,
                        symbols=symbols,
                        factor_type=request.factor_type,
                        lookback_calendar_days=5,
                    )
                    by_year: dict[str, Any] = {}
                    # bars 按日期排序后，年窗末日后取若干交易日供 t→t+1
                    bar_dates_sorted = sorted(
                        {str(r["trade_date"])[:10] for r in bars}
                    )
                    for ylabel, w0, w1 in year_windows(start, end):
                        f_slice = [
                            r
                            for r in factor_rows
                            if w0 <= str(r["trade_date"])[:10] <= w1
                        ]
                        post = [d for d in bar_dates_sorted if d > w1][:5]
                        b_hi = post[-1] if post else w1
                        b_slice = [
                            r
                            for r in bars
                            if w0 <= str(r["trade_date"])[:10] <= b_hi
                        ]
                        yrep = evaluate_factor(
                            factor_rows=f_slice, ret_rows=b_slice
                        )
                        by_year[ylabel] = {
                            "start": w0,
                            "end": w1,
                            "report": yrep,
                            "universe_snapshot_id": snapshot_id,
                        }
                    row["oos"] = {
                        "by_year": by_year,
                        "summary": summarize_oos(by_year),
                    }
            factors_out[code] = row

        pack: dict[str, Any] = {
            "mode": "evidence",
            "universe_code": request.universe_code,
            "start": start,
            "end": end,
            "factor_type": request.factor_type,
            "year_split": request.year_split,
            "with_backtest": False,
            "compute_first": request.compute_first,
            "factors": factors_out,
            "job_id": request.job_id,
        }
        pack["report_text"] = format_evidence_pack(pack)
        status = "committed" if any_ok else "failed"
        self.repo.create_run(
            {
                "run_id": run_id,
                "factor_code": "EVIDENCE_PACK",
                "universe_code": request.universe_code,
                "start_date": start,
                "end_date": end,
                "status": status,
                "meta": pack,
                "created_at": created,
            }
        )
        return EvidenceResult(
            status=status,
            run_id=run_id,
            universe_code=request.universe_code,
            start=start,
            end=end,
            message=pack["report_text"],
            pack=pack,
        )

    def attach_backtests_to_evidence(
        self, *, run_id: str, backtests: dict[str, dict[str, Any]]
    ) -> None:
        """CLI 跑完 FACTOR_TOP_N 后回写 evidence pack。"""
        import json

        from shared.db import get_conn

        with get_conn() as conn:
            row = conn.execute(
                "SELECT meta_json FROM research_run WHERE run_id=?",
                (run_id,),
            ).fetchone()
            if not row:
                return
            meta = row["meta_json"]
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except json.JSONDecodeError:
                    meta = {}
            if not isinstance(meta, dict):
                meta = {}
            factors = meta.get("factors") or {}
            for code, bt in backtests.items():
                if code in factors and isinstance(factors[code], dict):
                    factors[code]["backtest"] = bt
            meta["factors"] = factors
            meta["with_backtest"] = True
            meta["report_text"] = format_evidence_pack(meta)
            conn.execute(
                "UPDATE research_run SET meta_json=? WHERE run_id=?",
                (json.dumps(meta, ensure_ascii=False), run_id),
            )
