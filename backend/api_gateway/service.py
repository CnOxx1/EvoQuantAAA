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
    ) -> dict:
        sym = (symbol or "").strip()
        if not sym:
            return fail("BAD_REQUEST", "symbol 必填", status=400)
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
                "factor_type": factor_type or "qfq",
                "count": len(rows),
                "bars": rows,
            }
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
