from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from risk_engine.models import RiskLimits, RiskReviewRequest, RiskReviewResult
from risk_engine.repository import RiskRepository
from risk_engine.rules import evaluate_account_book, evaluate_portfolio

logger = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class RiskEngineService:
    def __init__(self, *, repo: RiskRepository | None = None) -> None:
        self.repo = repo or RiskRepository()

    def _enrich_liquidity_meta(
        self,
        positions: list[dict[str, Any]],
        *,
        as_of: str,
        limits: RiskLimits,
        universe_code: str | None,
        factor_type: str,
    ) -> None:
        """就地补充 industry_code / adv_20（limits 启用对应检查时）。"""
        need_ind = limits.max_industry_weight is not None
        need_adv = limits.max_adv_participation is not None
        if not (need_ind or need_adv) or not as_of:
            return
        symbols = [str(p["symbol"]) for p in positions if p.get("symbol")]
        if not symbols:
            return
        ind_map: dict[str, str] = {}
        adv_map: dict[str, float] = {}
        if need_ind:
            ind_map = self.repo.load_industry_map(
                symbols=symbols,
                as_of=as_of,
                standard=limits.industry_standard,
                universe_code=universe_code,
            )
        if need_adv:
            adv_map = self.repo.load_adv_map(
                symbols=symbols,
                as_of=as_of,
                lookback_days=limits.adv_lookback_days,
                factor_type=factor_type,
            )
        for p in positions:
            sym = str(p.get("symbol") or "")
            if sym in ind_map:
                p["industry_code"] = ind_map[sym]
            if sym in adv_map:
                p["adv_20"] = adv_map[sym]

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

        account_id = str(pf.get("account_id") or "paper_default")
        kill_on, kill_scopes = self.repo.is_kill_on(account_id=account_id)

        if st != "draft" and not request.force:
            # Kill 解除后：曾因 Kill 否决的组合可自动重审（无需 --force）
            allow_kill_retry = False
            if st == "rejected" and not kill_on:
                prev = self.repo.latest_decision(request.portfolio_id)
                if prev and int(prev.get("kill_switch_on") or 0) == 1:
                    allow_kill_retry = True
            if not allow_kill_retry:
                return RiskReviewResult(
                    status="skipped",
                    portfolio_id=request.portfolio_id,
                    account_id=account_id,
                    message=f"已是 {st}（加 --force 可重审）",
                )
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
        as_of = str(pf.get("as_of_date") or "")[:10]
        pmeta = pf.get("meta") or pf.get("meta_json") or {}
        if isinstance(pmeta, str):
            try:
                import json

                pmeta = json.loads(pmeta or "{}")
            except json.JSONDecodeError:
                pmeta = {}
        if not isinstance(pmeta, dict):
            pmeta = {}
        universe_code = (
            str(pmeta.get("universe_code") or pf.get("universe_code") or "")
            or None
        )
        factor_type = str(pmeta.get("factor_type") or "qfq")
        self._enrich_liquidity_meta(
            positions,
            as_of=as_of,
            limits=limits,
            universe_code=universe_code,
            factor_type=factor_type,
        )

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
        # 同账户同日其他活跃组合：合并敞口，防止多策略同票叠加超限
        siblings = self.repo.list_account_active_portfolios(
            account_id=account_id,
            as_of=as_of,
            exclude_portfolio_id=request.portfolio_id,
        )
        if siblings:
            books = [positions]
            for sib in siblings:
                sib_pos = self.repo.list_positions(str(sib["portfolio_id"]))
                self._enrich_liquidity_meta(
                    sib_pos,
                    as_of=as_of,
                    limits=limits,
                    universe_code=universe_code,
                    factor_type=factor_type,
                )
                books.append(sib_pos)
            # 账户分母：优先用本 pf.nav / capital_weight 反推，缺则 sum(nav)
            cw = None
            if pmeta.get("capital_weight"):
                try:
                    cw = float(pmeta["capital_weight"])
                except (TypeError, ValueError):
                    cw = None
            slice_nav = float(pf.get("nav") or 0)
            if cw and cw > 0 and slice_nav > 0:
                account_nav = slice_nav / cw
            else:
                account_nav = slice_nav + sum(
                    float(s.get("nav") or 0) for s in siblings
                )
            acct_breaches = evaluate_account_book(
                position_books=books,
                account_nav=account_nav if account_nav > 0 else slice_nav,
                limits=limits,
            )
            breaches.extend(acct_breaches)
        decision_status = "approved" if not breaches else "rejected"
        decision_id = f"rd_{uuid.uuid4().hex}"
        created = _utcnow()
        meta: dict[str, Any] = {
            "limits_version": limits.version,
            "kill_scopes": kill_scopes,
            "strategy_version": pf.get("strategy_version"),
            "position_count": len(positions),
            "sibling_portfolio_count": len(siblings) if siblings else 0,
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
