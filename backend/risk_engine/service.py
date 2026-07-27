from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from risk_engine.models import RiskReviewRequest, RiskReviewResult
from risk_engine.repository import RiskRepository
from risk_engine.rules import evaluate_portfolio

logger = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class RiskEngineService:
    def __init__(self, *, repo: RiskRepository | None = None) -> None:
        self.repo = repo or RiskRepository()

    def review(self, request: RiskReviewRequest) -> RiskReviewResult:
        pf = self.repo.get_portfolio(request.portfolio_id)
        if not pf:
            return RiskReviewResult(
                status="failed",
                portfolio_id=request.portfolio_id,
                message="portfolio_id 不存在",
            )
        st = str(pf.get("status") or "")
        if st not in ("draft", "approved", "rejected"):
            return RiskReviewResult(
                status="invalid",
                portfolio_id=request.portfolio_id,
                message=f"不可审核状态: {st}",
            )
        if st != "draft" and not request.force:
            return RiskReviewResult(
                status="skipped",
                portfolio_id=request.portfolio_id,
                account_id=str(pf.get("account_id") or ""),
                message=f"已是 {st}（加 --force 可重审）",
            )

        account_id = str(pf.get("account_id") or "paper_default")
        kill_on, kill_scopes = self.repo.is_kill_on(account_id=account_id)
        try:
            limits = self.repo.load_limits(request.limits_version)
        except RuntimeError as exc:
            return RiskReviewResult(
                status="failed",
                portfolio_id=request.portfolio_id,
                account_id=account_id,
                message=str(exc),
            )
        limits.lot_size = self.repo.load_lot_size(
            str(pf.get("cost_version") or "v1_ashare_default")
        )

        positions = self.repo.list_positions(request.portfolio_id)
        breaches = evaluate_portfolio(
            positions=positions,
            nav=float(pf.get("nav") or 0),
            invested_value=(
                float(pf["invested_value"])
                if pf.get("invested_value") is not None
                else None
            ),
            kill_switch_on=kill_on,
            limits=limits,
        )
        decision_status = "approved" if not breaches else "rejected"
        decision_id = f"rd_{uuid.uuid4().hex}"
        created = _utcnow()
        meta: dict[str, Any] = {
            "limits_version": limits.version,
            "kill_scopes": kill_scopes,
            "strategy_version": pf.get("strategy_version"),
            "position_count": len(positions),
            "force": request.force,
        }
        self.repo.insert_decision(
            {
                "decision_id": decision_id,
                "portfolio_id": request.portfolio_id,
                "account_id": account_id,
                "as_of_date": str(pf.get("as_of_date") or "")[:10] or None,
                "status": decision_status,
                "kill_switch_on": 1 if kill_on else 0,
                "breach_count": len(breaches),
                "breaches": breaches,
                "meta": meta,
                "actor": request.actor,
                "job_id": request.job_id,
                "created_at": created,
            }
        )
        logger.info(
            "risk %s decision=%s portfolio=%s breaches=%s",
            decision_status,
            decision_id,
            request.portfolio_id,
            len(breaches),
        )
        return RiskReviewResult(
            status=decision_status,
            decision_id=decision_id,
            portfolio_id=request.portfolio_id,
            account_id=account_id,
            breach_count=len(breaches),
            breaches=breaches,
            meta=meta,
            message="" if decision_status == "approved" else "存在硬规则违约",
        )

    def review_drafts(
        self,
        *,
        as_of: str | None = None,
        account_id: str | None = None,
        limits_version: str = "v1_default",
        actor: str = "cli",
        job_id: str | None = None,
        force: bool = False,
        limit: int = 50,
    ) -> list[RiskReviewResult]:
        drafts = self.repo.list_draft_portfolios(
            as_of=as_of, account_id=account_id, limit=limit
        )
        if not drafts:
            return [
                RiskReviewResult(
                    status="skipped", message="无 draft 组合可审核"
                )
            ]
        return [
            self.review(
                RiskReviewRequest(
                    portfolio_id=str(d["portfolio_id"]),
                    limits_version=limits_version,
                    actor=actor,
                    job_id=job_id,
                    force=force,
                )
            )
            for d in drafts
        ]

    def set_kill(
        self,
        *,
        scope_key: str,
        is_on: bool,
        reason: str | None = None,
        actor: str = "cli",
    ) -> dict[str, Any]:
        key = (scope_key or "GLOBAL").strip() or "GLOBAL"
        now = _utcnow()
        self.repo.set_kill_switch(
            scope_key=key,
            is_on=is_on,
            reason=reason or ("armed" if is_on else "disarmed"),
            actor=actor,
            updated_at=now,
        )
        return self.repo.get_kill_switch(key)
