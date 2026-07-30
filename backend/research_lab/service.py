from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from research_lab.evaluate import evaluate_factor, format_eval_report
from research_lab.evidence import (
    artifact_hash,
    format_evidence_pack,
    hard_oos_verdict,
    oos_eval_windows,
    pack_freeze_eligibility,
    soft_verdict,
    summarize_oos,
    walk_forward_windows,
)
from research_lab.factors import (
    compute_flow_net_5,
    compute_mom_20,
    compute_tech_level,
    compute_tech_ma20_bias,
    compute_val_pe_pct,
)
from research_lab.models import (
    BUILTIN_SPECS,
    FACTOR_CODES,
    FACTOR_TEMPLATES,
    EvidenceRequest,
    EvidenceResult,
    FactorDefUpsert,
    FreezeRequest,
    FreezeResult,
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

    def resolve_factor_spec(self, factor_code: str) -> dict[str, Any]:
        code = (factor_code or "").strip()
        if not code:
            raise ValueError("factor_code 必填")
        row = self.repo.get_factor_def(code)
        if row:
            if str(row.get("status") or "").upper() != "ACTIVE":
                raise ValueError(f"因子 {code} 状态为 {row.get('status')}，不可计算")
            return {
                "factor_code": code,
                "template": str(row["template"]),
                "params": dict(row.get("params") or {}),
                "display_name": row.get("display_name") or code,
            }
        if code in BUILTIN_SPECS:
            spec = BUILTIN_SPECS[code]
            return {
                "factor_code": code,
                "template": spec["template"],
                "params": dict(spec["params"]),
                "display_name": code,
            }
        raise ValueError(
            f"未知因子 {code}：请先在 research_factor_def 注册，或使用内置码 {', '.join(FACTOR_CODES)}"
        )

    def list_factor_defs(self, *, status: str | None = "ACTIVE") -> list[dict[str, Any]]:
        try:
            return self.repo.list_factor_defs(status=status)
        except Exception:
            # 迁移未应用时回退内置
            now = _utcnow()
            return [
                {
                    "factor_code": k,
                    "display_name": k,
                    "template": v["template"],
                    "params": v["params"],
                    "status": "ACTIVE",
                    "is_builtin": 1,
                    "created_at": now,
                    "updated_at": now,
                }
                for k, v in BUILTIN_SPECS.items()
            ]

    def register_factor_def(self, req: FactorDefUpsert) -> dict[str, Any]:
        code = (req.factor_code or "").strip().upper().replace(" ", "_")
        if not code or not code.replace("_", "").isalnum():
            raise ValueError("factor_code 仅允许字母数字下划线")
        tmpl = (req.template or "").strip().upper()
        if tmpl not in FACTOR_TEMPLATES:
            raise ValueError(f"不支持的模板: {tmpl}；可选 {', '.join(FACTOR_TEMPLATES)}")
        params = self._normalize_params(tmpl, dict(req.params or {}))
        existing = self.repo.get_factor_def(code)
        if existing and int(existing.get("is_builtin") or 0) == 1:
            raise ValueError(f"内置因子 {code} 已存在，请用更新接口改参数/名称")
        now = _utcnow()
        return self.repo.upsert_factor_def(
            {
                "factor_code": code,
                "display_name": (req.display_name or code).strip() or code,
                "template": tmpl,
                "params": params,
                "description": req.description,
                "status": (req.status or "ACTIVE").upper(),
                "is_builtin": 0,
                "created_by": req.actor,
                "created_at": (existing or {}).get("created_at") or now,
                "updated_at": now,
            }
        )

    def update_factor_def(
        self,
        factor_code: str,
        *,
        display_name: str | None = None,
        params: dict[str, Any] | None = None,
        description: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        cur = self.repo.get_factor_def(factor_code)
        if not cur:
            raise ValueError(f"因子不存在: {factor_code}")
        patch: dict[str, Any] = {"updated_at": _utcnow()}
        if display_name is not None:
            patch["display_name"] = display_name.strip() or cur["factor_code"]
        if description is not None:
            patch["description"] = description
        if status is not None:
            st = status.strip().upper()
            if st not in ("ACTIVE", "RETIRED"):
                raise ValueError("status 仅 ACTIVE|RETIRED")
            patch["status"] = st
        if params is not None:
            patch["params"] = self._normalize_params(
                str(cur["template"]), dict(params)
            )
        return self.repo.update_factor_def(factor_code, patch)  # type: ignore[return-value]

    def _normalize_params(
        self, template: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        t = template.upper()
        out: dict[str, Any] = {}
        if t == "MOM":
            lb = int(params.get("lookback", 20))
            if lb < 2 or lb > 250:
                raise ValueError("MOM.lookback 需在 2~250")
            out["lookback"] = lb
        elif t == "FLOW_NET":
            lb = int(params.get("lookback", 5))
            if lb < 2 or lb > 60:
                raise ValueError("FLOW_NET.lookback 需在 2~60")
            out["lookback"] = lb
        elif t == "TECH_PASS":
            code = str(params.get("indicator_code") or "").strip().upper()
            if not code or not code.replace("_", "").isalnum():
                raise ValueError("TECH_PASS 需要合法 indicator_code（如 RSI_14 / MACD_HIST）")
            if len(code) > 64:
                raise ValueError("indicator_code 过长")
            out["indicator_code"] = code
        elif t == "TECH_RSI":
            p = int(params.get("period", 14))
            if p < 2 or p > 100:
                raise ValueError("TECH_RSI.period 需在 2~100")
            out["period"] = p
        elif t == "TECH_MA_BIAS":
            p = int(params.get("period", 20))
            if p < 2 or p > 250:
                raise ValueError("TECH_MA_BIAS.period 需在 2~250")
            out["period"] = p
        elif t in ("VAL_PE_PCT", "TECH_MACD_HIST"):
            out = {}
        else:
            raise ValueError(f"未知模板 {template}")
        return out

    def run(self, request: ResearchRequest) -> ResearchResult:
        spec = self.resolve_factor_spec(request.factor_code)
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
            "template": spec["template"],
            "params": spec["params"],
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
            rows = self._compute(
                factor_code=request.factor_code,
                template=str(spec["template"]),
                params=dict(spec["params"]),
                factor_type=request.factor_type,
                symbols=symbols,
                start=start,
                end=end,
            )
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
        *,
        factor_code: str,
        template: str,
        params: dict[str, Any],
        factor_type: str,
        symbols: list[str],
        start: str,
        end: str,
    ) -> list[dict[str, Any]]:
        t = template.upper()
        if t == "MOM":
            lookback = int(params.get("lookback", 20))
            bars = self.repo.load_equity_bars(
                start=start,
                end=end,
                symbols=symbols,
                factor_type=factor_type,
                lookback_calendar_days=max(60, lookback * 3),
            )
            return compute_mom_20(
                bars, start=start, end=end, lookback=lookback
            )

        if t == "VAL_PE_PCT":
            vals = self.repo.load_valuations(
                start=start, end=end, symbols=symbols
            )
            return compute_val_pe_pct(
                vals, symbols=set(symbols), start=start, end=end
            )

        if t == "FLOW_NET":
            lookback = int(params.get("lookback", 5))
            flows = self.repo.load_stock_flows(
                start=start,
                end=end,
                symbols=symbols,
                lookback_calendar_days=max(14, lookback * 3),
            )
            bars = self.repo.load_equity_bars(
                start=start,
                end=end,
                symbols=symbols,
                factor_type=factor_type,
                lookback_calendar_days=max(14, lookback * 3),
            )
            return compute_flow_net_5(
                flows, bars, start=start, end=end, lookback=lookback
            )

        if t == "TECH_PASS":
            ind = str(params.get("indicator_code") or "").strip().upper()
            if not ind:
                raise ValueError("TECH_PASS 缺少 indicator_code")
            tech = self.repo.load_tech_indicators(
                start=start,
                end=end,
                symbols=symbols,
                factor_type=factor_type,
                indicator_codes=[ind],
            )
            rows = compute_tech_level(
                tech, indicator_code=ind, start=start, end=end
            )
            if not rows:
                raise ValueError(
                    f"无技术指标 {ind} 数据：请先 "
                    f"python main.py data_process --kind tech_indicator"
                )
            return rows

        if t == "TECH_RSI":
            period = int(params.get("period", 14))
            ind = f"RSI_{period}"
            tech = self.repo.load_tech_indicators(
                start=start,
                end=end,
                symbols=symbols,
                factor_type=factor_type,
                indicator_codes=[ind],
            )
            return compute_tech_level(
                tech, indicator_code=ind, start=start, end=end
            )

        if t == "TECH_MACD_HIST":
            tech = self.repo.load_tech_indicators(
                start=start,
                end=end,
                symbols=symbols,
                factor_type=factor_type,
                indicator_codes=["MACD_HIST"],
            )
            return compute_tech_level(
                tech, indicator_code="MACD_HIST", start=start, end=end
            )

        if t == "TECH_MA_BIAS":
            period = int(params.get("period", 20))
            ma_code = f"MA_{period}"
            tech = self.repo.load_tech_indicators(
                start=start,
                end=end,
                symbols=symbols,
                factor_type=factor_type,
                indicator_codes=[ma_code],
            )
            bars = self.repo.load_equity_bars(
                start=start,
                end=end,
                symbols=symbols,
                factor_type=factor_type,
                lookback_calendar_days=0,
            )
            return compute_tech_ma20_bias(
                tech, bars, start=start, end=end, ma_code=ma_code
            )

        raise ValueError(f"不支持的因子模板: {template} ({factor_code})")

    def evaluate(self, request: ResearchRequest) -> ResearchResult:
        """对已落库因子做 IC / 分层；结果写入 research_run.meta_json。"""
        self.resolve_factor_spec(request.factor_code)
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
                message="无因子值，请先计算因子",
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
                split_mode = (request.split_mode or "year").strip().lower()
                if request.year_split is False and split_mode == "year":
                    split_mode = "none"
                folds = oos_eval_windows(
                    start,
                    end,
                    split_mode=split_mode,
                    train_days=request.wf_train_days,
                    test_days=request.wf_test_days,
                    step_days=request.wf_step_days,
                )
                if folds:
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
                    by_fold: dict[str, Any] = {}
                    bar_dates_sorted = sorted(
                        {str(r["trade_date"])[:10] for r in bars}
                    )
                    wf_meta = None
                    if split_mode in ("walk_forward", "wf"):
                        wf_meta = walk_forward_windows(
                            start,
                            end,
                            train_days=request.wf_train_days,
                            test_days=request.wf_test_days,
                            step_days=request.wf_step_days,
                        )
                    for ylabel, w0, w1 in folds:
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
                        fold_row: dict[str, Any] = {
                            "start": w0,
                            "end": w1,
                            "report": yrep,
                            "universe_snapshot_id": snapshot_id,
                        }
                        if wf_meta:
                            match = next(
                                (x for x in wf_meta if x[0] == ylabel), None
                            )
                            if match:
                                fold_row["train_start"] = match[1]
                                fold_row["train_end"] = match[2]
                        by_fold[ylabel] = fold_row
                    oos_summary = summarize_oos(by_fold)
                    row["oos"] = {
                        "split_mode": split_mode,
                        "by_fold": by_fold,
                        "by_year": by_fold,  # 兼容旧读者
                        "summary": oos_summary,
                    }
                    row["hard_oos"] = hard_oos_verdict(
                        oos_summary, request.hard_oos_gates
                    )
            factors_out[code] = row

        split_mode = (request.split_mode or "year").strip().lower()
        if request.year_split is False and split_mode == "year":
            split_mode = "none"
        pack: dict[str, Any] = {
            "mode": "evidence",
            "universe_code": request.universe_code,
            "start": start,
            "end": end,
            "factor_type": request.factor_type,
            "year_split": split_mode == "year",
            "split_mode": split_mode,
            "walk_forward": {
                "train_days": request.wf_train_days,
                "test_days": request.wf_test_days,
                "step_days": request.wf_step_days
                if request.wf_step_days is not None
                else request.wf_test_days,
            }
            if split_mode in ("walk_forward", "wf")
            else None,
            "with_backtest": False,
            "compute_first": request.compute_first,
            "factors": factors_out,
            "job_id": request.job_id,
        }
        pack["freeze_eligibility"] = pack_freeze_eligibility(
            pack, request.hard_oos_gates
        )
        pack["artifact_hash"] = artifact_hash(pack)
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

    def freeze_evidence(self, request: FreezeRequest) -> FreezeResult:
        """将已 committed 的 EVIDENCE_PACK 固化为不可变冻结记录。"""
        run = self.repo.get_run(request.evidence_run_id)
        if not run:
            return FreezeResult(
                status="failed",
                evidence_run_id=request.evidence_run_id,
                message="evidence_run_id 不存在",
            )
        if str(run.get("status")) != "committed":
            return FreezeResult(
                status="rejected",
                evidence_run_id=request.evidence_run_id,
                message=f"research_run 状态非 committed: {run.get('status')}",
            )
        if str(run.get("factor_code")) != "EVIDENCE_PACK":
            return FreezeResult(
                status="rejected",
                evidence_run_id=request.evidence_run_id,
                message="仅支持 factor_code=EVIDENCE_PACK",
            )
        pack = run.get("meta") or {}
        if not isinstance(pack, dict) or pack.get("mode") != "evidence":
            return FreezeResult(
                status="rejected",
                evidence_run_id=request.evidence_run_id,
                message="meta.mode 不是 evidence",
            )

        eligibility = pack_freeze_eligibility(pack, request.hard_oos_gates)
        if not eligibility.get("eligible") and not request.force:
            return FreezeResult(
                status="rejected",
                evidence_run_id=request.evidence_run_id,
                message="硬 OOS 门槛未通过（加 --force 可强制冻结，不推荐）",
                meta={"freeze_eligibility": eligibility},
            )
        if request.force and not request.reason:
            return FreezeResult(
                status="rejected",
                evidence_run_id=request.evidence_run_id,
                message="--force 冻结必须提供 --reason",
            )

        h = artifact_hash(pack)
        existing = self.repo.find_freeze_by_hash(h)
        if existing:
            return FreezeResult(
                status="skipped",
                freeze_id=str(existing["freeze_id"]),
                evidence_run_id=request.evidence_run_id,
                artifact_hash=h,
                message="相同 artifact_hash 已冻结（幂等）",
                meta={"existing": True},
            )

        freeze_id = f"ef_{uuid.uuid4().hex}"
        created = _utcnow()
        summary = {
            "freeze_eligibility": eligibility,
            "split_mode": pack.get("split_mode"),
            "factors": {
                code: {
                    "soft_passed": ((row.get("verdict") or {}).get("passed")),
                    "hard_oos": row.get("hard_oos"),
                    "oos_summary": (row.get("oos") or {}).get("summary"),
                }
                for code, row in (pack.get("factors") or {}).items()
                if isinstance(row, dict)
            },
        }
        self.repo.insert_freeze(
            {
                "freeze_id": freeze_id,
                "evidence_run_id": request.evidence_run_id,
                "universe_code": str(
                    pack.get("universe_code") or run.get("universe_code") or ""
                ),
                "start_date": str(pack.get("start") or run.get("start_date"))[:10],
                "end_date": str(pack.get("end") or run.get("end_date"))[:10],
                "status": "frozen",
                "split_mode": str(pack.get("split_mode") or "year"),
                "hard_gates": request.hard_oos_gates or {},
                "summary": summary,
                "artifact_hash": h,
                "actor": request.actor,
                "reason": request.reason,
                "job_id": request.job_id,
                "meta": {
                    "force": request.force,
                    "eligible_factors": eligibility.get("eligible_factors"),
                },
                "created_at": created,
            }
        )
        return FreezeResult(
            status="frozen",
            freeze_id=freeze_id,
            evidence_run_id=request.evidence_run_id,
            artifact_hash=h,
            message=f"frozen factors={eligibility.get('eligible_factors')}",
            meta=summary,
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
            meta["freeze_eligibility"] = pack_freeze_eligibility(meta)
            meta["artifact_hash"] = artifact_hash(meta)
            meta["report_text"] = format_evidence_pack(meta)
            conn.execute(
                "UPDATE research_run SET meta_json=? WHERE run_id=?",
                (json.dumps(meta, ensure_ascii=False), run_id),
            )
