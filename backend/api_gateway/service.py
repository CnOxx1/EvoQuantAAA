from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from api_gateway.models import fail, ok
from api_gateway.repository import GatewayRepository


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class GatewayService:
    """只读经本模块 repository；写命令转发各领域 Service（与 main.py CLI 同口径）。"""

    def __init__(self, *, repo: GatewayRepository | None = None) -> None:
        self.repo = repo or GatewayRepository()

    def _audit(
        self,
        *,
        actor: str,
        method: str,
        path: str,
        status_code: int,
        request: dict[str, Any] | None,
        result: dict[str, Any],
    ) -> None:
        try:
            self.repo.insert_audit(
                {
                    "audit_id": f"aa_{uuid.uuid4().hex}",
                    "actor": actor,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "request": request or {},
                    "result": {
                        "ok": result.get("ok"),
                        "error": result.get("error"),
                    },
                    "created_at": _utcnow(),
                }
            )
        except Exception:  # noqa: BLE001
            # 审计失败不影响主流程
            pass

    def list_strategies(self, *, status: str | None = None, limit: int = 50) -> dict:
        return ok(self.repo.list_strategies(status=status, limit=limit))

    def get_strategy(self, strategy_version: str) -> dict:
        row = self.repo.get_strategy(strategy_version)
        if not row:
            return fail("NOT_FOUND", "strategy_version 不存在", status=404)
        return ok(row)

    def get_research_run(self, run_id: str) -> dict:
        row = self.repo.get_research_run(run_id)
        if not row:
            return fail("NOT_FOUND", "research run 不存在", status=404)
        return ok(row)

    def get_decision(self, decision_id: str) -> dict:
        row = self.repo.get_risk_decision(decision_id)
        if not row:
            return fail("NOT_FOUND", "decision 不存在", status=404)
        return ok(row)

    def ops_pipeline(self) -> dict:
        return ok(self.repo.ops_pipeline())

    def list_signal_batches(
        self, *, strategy_version: str | None = None, limit: int = 50
    ) -> dict:
        return ok(
            self.repo.list_signal_batches(
                strategy_version=strategy_version, limit=limit
            )
        )

    def promote_strategy(
        self,
        *,
        strategy_version: str,
        to_status: str,
        backtest_run: str | None,
        reason: str | None,
        actor: str,
        skip_gates: bool = False,
        gate_version: str | None = None,
    ) -> dict:
        from strategy_registry.models import PromoteRequest
        from strategy_registry.service import StrategyRegistryService

        result = StrategyRegistryService().promote(
            PromoteRequest(
                strategy_version=strategy_version,
                to_status=to_status,  # type: ignore[arg-type]
                backtest_run_id=backtest_run,
                reason=reason,
                actor=actor,
                skip_gates=skip_gates,
                gate_version=gate_version,
            )
        )
        if result.status == "ok":
            body = ok(
                {
                    "status": result.status,
                    "strategy_version": result.strategy_version,
                    "from_status": result.from_status,
                    "to_status": result.to_status,
                    "meta": result.meta,
                }
            )
            code = 200
        else:
            body = fail(
                result.status.upper(),
                result.message or result.status,
                status=400,
                strategy_version=result.strategy_version,
                meta=result.meta or None,
            )
            code = 400
        self._audit(
            actor=actor,
            method="POST",
            path=f"/v1/strategies/{strategy_version}/promote",
            status_code=code,
            request={
                "to": to_status,
                "backtest_run": backtest_run,
                "reason": reason,
                "skip_gates": skip_gates,
                "gate_version": gate_version,
            },
            result=body,
        )
        return body

    def list_portfolios(
        self, *, status: str | None = None, as_of: str | None = None, limit: int = 50
    ) -> dict:
        return ok(
            self.repo.list_portfolios(status=status, as_of=as_of, limit=limit)
        )

    def get_portfolio(self, portfolio_id: str) -> dict:
        row = self.repo.get_portfolio(portfolio_id)
        if not row:
            return fail("NOT_FOUND", "portfolio_id 不存在", status=404)
        return ok(row)

    def risk_status(self) -> dict:
        return ok({"kill_switches": self.repo.list_kill_switches()})

    def set_kill(
        self,
        *,
        scope: str,
        is_on: bool,
        reason: str | None,
        actor: str,
    ) -> dict:
        from risk_engine.service import RiskEngineService

        sw = RiskEngineService().set_kill(
            scope_key=scope, is_on=is_on, reason=reason, actor=actor
        )
        body = ok(sw)
        self._audit(
            actor=actor,
            method="POST",
            path="/v1/risk/kill",
            status_code=200,
            request={"scope": scope, "on": is_on, "reason": reason},
            result=body,
        )
        return body

    def risk_review(
        self,
        *,
        portfolio_id: str | None,
        drafts: bool,
        as_of: str | None,
        actor: str,
        force: bool = False,
    ) -> dict:
        from risk_engine.models import RiskReviewRequest
        from risk_engine.service import RiskEngineService

        svc = RiskEngineService()
        if drafts:
            results = svc.review_drafts(
                as_of=as_of, actor=actor, force=force
            )
        elif portfolio_id:
            results = [
                svc.review(
                    RiskReviewRequest(
                        portfolio_id=portfolio_id, actor=actor, force=force
                    )
                )
            ]
        else:
            return fail("INVALID", "需要 portfolio_id 或 drafts=true")

        payload = [
            {
                "status": r.status,
                "decision_id": r.decision_id,
                "portfolio_id": r.portfolio_id,
                "breach_count": r.breach_count,
                "breaches": r.breaches,
                "message": r.message,
            }
            for r in results
        ]
        body = ok(payload)
        self._audit(
            actor=actor,
            method="POST",
            path="/v1/risk/review",
            status_code=200,
            request={
                "portfolio_id": portfolio_id,
                "drafts": drafts,
                "as_of": as_of,
            },
            result=body,
        )
        return body

    def list_decisions(self, *, portfolio_id: str | None = None, limit: int = 20) -> dict:
        return ok(
            self.repo.list_risk_decisions(portfolio_id=portfolio_id, limit=limit)
        )

    def get_execution(self, execution_id: str) -> dict:
        row = self.repo.get_execution(execution_id)
        if not row:
            return fail("NOT_FOUND", "execution_id 不存在", status=404)
        return ok(row)

    def list_executions(
        self, *, account_id: str | None = None, limit: int = 50
    ) -> dict:
        return ok(self.repo.list_executions(account_id=account_id, limit=limit))

    def list_pending(
        self,
        *,
        account_id: str | None = None,
        status: str | None = "open",
        limit: int = 100,
    ) -> dict:
        return ok(
            self.repo.list_pending(
                account_id=account_id, status=status, limit=limit
            )
        )

    def list_research_runs(self, *, limit: int = 50) -> dict:
        return ok(self.repo.list_research_runs(limit=limit))

    def list_market_ranks(
        self,
        *,
        trade_date: str | None = None,
        rank_type: str | None = None,
        limit: int = 100,
    ) -> dict:
        return ok(
            self.repo.list_market_ranks(
                trade_date=trade_date, rank_type=rank_type, limit=limit
            )
        )

    def market_rank_meta(self) -> dict:
        return ok(self.repo.list_rank_meta())

    def list_abnormal_moves(
        self,
        *,
        trade_date: str | None = None,
        change_type: str | None = None,
        limit: int = 100,
    ) -> dict:
        return ok(
            self.repo.list_abnormal_moves(
                trade_date=trade_date, change_type=change_type, limit=limit
            )
        )

    def list_news(
        self,
        *,
        channel: str | None = None,
        symbol: str | None = None,
        limit: int = 50,
    ) -> dict:
        return ok(
            self.repo.list_news(channel=channel, symbol=symbol, limit=limit)
        )

    def list_dragon_tiger(
        self, *, trade_date: str | None = None, limit: int = 100
    ) -> dict:
        return ok(
            self.repo.list_dragon_tiger(trade_date=trade_date, limit=limit)
        )

    def list_equity_bars(
        self,
        *,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
        factor_type: str = "qfq",
        limit: int = 120,
        freq: str | None = None,
    ) -> dict:
        sym = (symbol or "").strip()
        if not sym:
            return fail("BAD_REQUEST", "symbol 必填", status=400)
        fq = (freq or "1d").strip().lower()
        if fq in ("15m", "60m"):
            rows = self.repo.list_equity_min_bars(
                symbol=sym,
                freq=fq,
                start=start,
                end=end,
                factor_type=factor_type,
                limit=limit,
            )
            return ok(
                {
                    "symbol": sym,
                    "freq": fq,
                    "factor_type": factor_type or "qfq",
                    "count": len(rows),
                    "bars": rows,
                }
            )
        if fq not in ("1d", "d", "day", ""):
            return fail(
                "BAD_REQUEST",
                "freq 仅支持 1d / 15m / 60m",
                status=400,
            )
        rows = self.repo.list_equity_bars(
            symbol=sym,
            start=start,
            end=end,
            factor_type=factor_type,
            limit=limit,
        )
        return ok(
            {
                "symbol": sym,
                "freq": "1d",
                "factor_type": factor_type or "qfq",
                "count": len(rows),
                "bars": rows,
            }
        )

    def list_backtest_runs(self, *, status: str | None = None, limit: int = 50) -> dict:
        return ok(self.repo.list_backtest_runs(status=status, limit=limit))

    def get_backtest_run(self, run_id: str) -> dict:
        row = self.repo.get_backtest_run(run_id)
        if not row:
            return fail("NOT_FOUND", "backtest run 不存在", status=404)
        return ok(row)

    def search_securities(
        self, *, q: str, as_of: str | None = None, limit: int = 20
    ) -> dict:
        query = (q or "").strip()
        if not query:
            return fail("BAD_REQUEST", "q 必填", status=400)
        rows = self.repo.search_securities(q=query, as_of=as_of, limit=limit)
        return ok({"q": query, "count": len(rows), "items": rows})

    def list_boards(
        self,
        *,
        trade_date: str | None = None,
        board_type: str | None = None,
        limit: int = 100,
    ) -> dict:
        rows = self.repo.list_board_bars(
            trade_date=trade_date, board_type=board_type, limit=limit
        )
        td = rows[0].get("trade_date") if rows else trade_date
        return ok({"trade_date": td, "count": len(rows), "items": rows})

    def list_board_history(
        self,
        *,
        board_name: str,
        board_type: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = 120,
    ) -> dict:
        name = (board_name or "").strip()
        if not name:
            return fail("BAD_REQUEST", "board_name 必填", status=400)
        rows = self.repo.list_board_history(
            board_name=name,
            board_type=board_type,
            start=start,
            end=end,
            limit=limit,
        )
        return ok({"board_name": name, "count": len(rows), "bars": rows})

    def list_board_members(
        self,
        *,
        industry_name: str | None = None,
        industry_code: str | None = None,
        as_of: str | None = None,
        limit: int = 200,
    ) -> dict:
        if not industry_name and not industry_code:
            return fail("BAD_REQUEST", "industry_name 或 industry_code 必填", status=400)
        rows = self.repo.list_board_members(
            industry_name=industry_name,
            industry_code=industry_code,
            as_of=as_of,
            limit=limit,
        )
        return ok({"count": len(rows), "items": rows})

    def list_dq_runs(self, *, scope: str | None = None, limit: int = 50) -> dict:
        return ok(self.repo.list_dq_runs(scope=scope, limit=limit))

    def get_dq_run(self, dq_run_id: str) -> dict:
        row = self.repo.get_dq_run(dq_run_id)
        if not row:
            return fail("NOT_FOUND", "dq_run 不存在", status=404)
        return ok(row)

    def list_dq_gates(self, *, scope: str | None = None, limit: int = 50) -> dict:
        return ok(self.repo.list_dq_gates(scope=scope, limit=limit))

    def data_coverage(
        self,
        *,
        start: str,
        end: str,
        symbols: str | None = None,
    ) -> dict:
        from ops_monitor.coverage import build_coverage_matrix

        sym_list = None
        if symbols:
            sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
        return ok(build_coverage_matrix(start=start, end=end, symbols=sym_list))

    def get_f10(self, symbol: str, *, as_of: str | None = None) -> dict:
        row = self.repo.get_f10(symbol, as_of=as_of)
        if not row:
            return fail("NOT_FOUND", "未找到该标的资料", status=404)
        return ok(row)

    def list_market_events(
        self,
        *,
        start: str | None = None,
        end: str | None = None,
        symbol: str | None = None,
        limit: int = 100,
    ) -> dict:
        rows = self.repo.list_market_events(
            start=start, end=end, symbol=symbol, limit=limit
        )
        return ok({"count": len(rows), "items": rows})

    def list_econ_calendar(
        self,
        *,
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
    ) -> dict:
        return ok(
            self.repo.list_econ_calendar(start=start, end=end, limit=limit)
        )

    def tech_indicator_meta(self, *, symbol: str | None = None) -> dict:
        return ok(self.repo.list_tech_indicator_meta(symbol=symbol))

    def list_tech_indicators(
        self,
        *,
        symbol: str,
        codes: str | None = None,
        start: str | None = None,
        end: str | None = None,
        factor_type: str = "qfq",
        limit: int = 180,
    ) -> dict:
        sym = (symbol or "").strip()
        if not sym:
            return fail("BAD_REQUEST", "symbol 必填", status=400)
        code_list = None
        if codes:
            code_list = [c.strip() for c in codes.split(",") if c.strip()]
        return ok(
            self.repo.list_tech_indicators(
                symbol=sym,
                codes=code_list,
                start=start,
                end=end,
                factor_type=factor_type,
                limit=limit,
            )
        )

    def get_ledger(self, account_id: str, *, as_of: str | None = None) -> dict:
        row = self.repo.get_ledger_account(account_id)
        if not row:
            return fail("NOT_FOUND", "account 不存在", status=404)
        if as_of:
            from ledger.service import LedgerService

            row["sellable"] = LedgerService().sellable_report(
                account_id=account_id, as_of=as_of
            )
        return ok(row)

    def list_alerts(self, *, limit: int = 20) -> dict:
        return ok(self.repo.list_alerts(limit=limit))

    def run_signal(
        self,
        *,
        as_of: str,
        strategy_version: str | None,
        paper: bool,
        live: bool,
        require_dq: bool,
        actor: str,
    ) -> dict:
        from signal_prod.models import SignalRunRequest
        from signal_prod.service import SignalProdService

        day = (as_of or "")[:10]
        if not day:
            return fail("BAD_REQUEST", "as_of 必填", status=400)
        svc = SignalProdService()
        results = []
        if strategy_version:
            results = [
                svc.run(
                    SignalRunRequest(
                        strategy_version=strategy_version,
                        start=day,
                        end=day,
                        as_of=day,
                        require_dq=require_dq,
                    )
                )
            ]
        elif live or paper:
            statuses: set[str] = set()
            if live:
                statuses.add("LIVE")
            if paper:
                statuses.add("PAPER")
            results = svc.run_all_runnable(
                start=day,
                end=day,
                as_of=day,
                require_dq=require_dq,
                statuses=statuses,
            )
        else:
            return fail("BAD_REQUEST", "需要 strategy_version 或 paper/live", status=400)

        payload = [
            {
                "status": r.status,
                "signal_batch_id": r.signal_batch_id,
                "strategy_version": r.strategy_version,
                "strategy_code": r.strategy_code,
                "row_count": r.row_count,
                "message": r.message,
                "meta": r.meta,
            }
            for r in results
        ]
        ok_any = any(r.status in ("committed", "skipped") for r in results)
        body = ok(payload) if ok_any or results else fail("FAILED", "无结果", status=400)
        if results and not ok_any:
            body = fail(
                "FAILED",
                results[0].message or results[0].status,
                status=400,
                results=payload,
            )
        self._audit(
            actor=actor,
            method="POST",
            path="/v1/signal/run",
            status_code=200 if body.get("ok") else 400,
            request={
                "as_of": day,
                "strategy_version": strategy_version,
                "paper": paper,
                "live": live,
            },
            result=body,
        )
        return body

    def build_portfolio(
        self,
        *,
        as_of: str,
        strategy_version: str | None,
        account_id: str,
        paper: bool,
        live: bool,
        nav: float,
        use_ledger_nav: bool,
        force: bool,
        signal_batch_id: str | None,
        actor: str,
    ) -> dict:
        from portfolio_construct.models import PortfolioBuildRequest
        from portfolio_construct.service import PortfolioConstructService

        day = (as_of or "")[:10]
        if not day:
            return fail("BAD_REQUEST", "as_of 必填", status=400)
        svc = PortfolioConstructService()
        results = []
        if strategy_version:
            results = [
                svc.build(
                    PortfolioBuildRequest(
                        strategy_version=strategy_version,
                        as_of=day,
                        nav=float(nav),
                        account_id=account_id,
                        signal_batch_id=signal_batch_id,
                        use_ledger_nav=use_ledger_nav,
                        force=force,
                    )
                )
            ]
        elif live or paper:
            statuses: set[str] = set()
            if live:
                statuses.add("LIVE")
            if paper:
                statuses.add("PAPER")
            results = svc.build_all_runnable(
                as_of=day,
                nav=float(nav),
                account_id=account_id,
                statuses=statuses,
                use_ledger_nav=use_ledger_nav,
                force=force,
            )
        else:
            return fail("BAD_REQUEST", "需要 strategy_version 或 paper/live", status=400)

        payload = [
            {
                "status": r.status,
                "portfolio_id": r.portfolio_id,
                "strategy_version": r.strategy_version,
                "strategy_code": r.strategy_code,
                "row_count": r.row_count,
                "invested_value": r.invested_value,
                "cash_residual": r.cash_residual,
                "message": r.message,
                "meta": r.meta,
            }
            for r in results
        ]
        ok_any = any(r.status in ("draft", "skipped", "committed") for r in results)
        body = ok(payload) if ok_any or not results else fail(
            "FAILED",
            (results[0].message or results[0].status) if results else "无结果",
            status=400,
            results=payload,
        )
        if results and ok_any:
            body = ok(payload)
        self._audit(
            actor=actor,
            method="POST",
            path="/v1/portfolios/build",
            status_code=200 if body.get("ok") else 400,
            request={
                "as_of": day,
                "strategy_version": strategy_version,
                "account_id": account_id,
                "paper": paper,
            },
            result=body,
        )
        return body

    def run_execution(
        self,
        *,
        portfolio_id: str | None,
        approved: bool,
        as_of: str | None,
        account_id: str | None,
        adapter: str,
        force: bool,
        actor: str,
    ) -> dict:
        from execution.models import ExecutionRequest
        from execution.service import ExecutionService

        ad = (adapter or "paper").strip() or "paper"
        if ad == "live_gated":
            return fail(
                "FORBIDDEN",
                "UI 禁止 live_gated；请用 paper 或 CLI",
                status=400,
            )
        svc = ExecutionService()
        results = []
        if approved:
            results = svc.run_approved(
                as_of=as_of,
                account_id=account_id,
                force=force,
                adapter=ad,
            )
        elif portfolio_id:
            results = [
                svc.run(
                    ExecutionRequest(
                        portfolio_id=portfolio_id,
                        adapter=ad,  # type: ignore[arg-type]
                        force=force,
                    )
                )
            ]
        else:
            return fail("BAD_REQUEST", "需要 portfolio_id 或 approved=true", status=400)

        payload = [
            {
                "status": r.status,
                "execution_id": r.execution_id,
                "portfolio_id": r.portfolio_id,
                "message": r.message,
                "meta": r.meta,
            }
            for r in results
        ]
        ok_any = any(r.status in ("committed", "skipped") for r in results)
        body = (
            ok(payload)
            if ok_any
            else fail(
                "FAILED",
                (results[0].message or results[0].status) if results else "无结果",
                status=400,
                results=payload,
            )
        )
        self._audit(
            actor=actor,
            method="POST",
            path="/v1/executions/run",
            status_code=200 if body.get("ok") else 400,
            request={
                "portfolio_id": portfolio_id,
                "approved": approved,
                "adapter": ad,
            },
            result=body,
        )
        return body

    def resume_pending(
        self,
        *,
        as_of: str,
        account_id: str,
        adapter: str,
        strategy_version: str | None,
        actor: str,
    ) -> dict:
        from execution.service import ExecutionService

        day = (as_of or "")[:10]
        if not day:
            return fail("BAD_REQUEST", "as_of 必填", status=400)
        ad = (adapter or "paper").strip() or "paper"
        if ad == "live_gated":
            return fail("FORBIDDEN", "UI 禁止 live_gated", status=400)
        results = ExecutionService().resume_pending(
            as_of=day,
            account_id=account_id or "paper_default",
            strategy_version=strategy_version,
            adapter=ad,
        )
        payload = [
            {
                "status": r.status,
                "execution_id": r.execution_id,
                "portfolio_id": r.portfolio_id,
                "message": r.message,
                "meta": r.meta,
            }
            for r in results
        ]
        ok_any = any(r.status in ("committed", "skipped") for r in results) or not results
        body = ok(payload) if ok_any else fail(
            "FAILED",
            (results[0].message or results[0].status) if results else "失败",
            status=400,
            results=payload,
        )
        self._audit(
            actor=actor,
            method="POST",
            path="/v1/execution/pending/resume",
            status_code=200 if body.get("ok") else 400,
            request={"as_of": day, "account_id": account_id, "adapter": ad},
            result=body,
        )
        return body

    def post_ledger(
        self,
        *,
        execution_id: str,
        account_id: str | None,
        force: bool,
        actor: str,
    ) -> dict:
        from ledger.models import PostRequest
        from ledger.service import LedgerService

        if not (execution_id or "").strip():
            return fail("BAD_REQUEST", "execution_id 必填", status=400)
        r = LedgerService().post(
            PostRequest(
                execution_id=execution_id.strip(),
                account_id=account_id,
                force=force,
            )
        )
        payload = {
            "status": r.status,
            "posting_id": r.posting_id,
            "execution_id": r.execution_id,
            "account_id": r.account_id,
            "entry_count": r.entry_count,
            "cash_after": r.cash_after,
            "message": r.message,
            "meta": r.meta,
        }
        body = (
            ok(payload)
            if r.status in ("committed", "skipped")
            else fail("FAILED", r.message or r.status, status=400, **payload)
        )
        self._audit(
            actor=actor,
            method="POST",
            path="/v1/ledger/post",
            status_code=200 if body.get("ok") else 400,
            request={"execution_id": execution_id, "account_id": account_id},
            result=body,
        )
        return body
