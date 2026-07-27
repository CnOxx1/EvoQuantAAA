from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from execution.models import ExecutionRequest, ExecutionResult
from execution.paper import build_paper_intents, simulate_paper_fills
from execution.repository import ExecutionRepository

logger = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _portfolio_meta(pf: dict[str, Any]) -> dict[str, Any]:
    raw = pf.get("meta") or pf.get("meta_json") or {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(str(raw) or "{}")
    except json.JSONDecodeError:
        return {}


class ExecutionService:
    def __init__(self, *, repo: ExecutionRepository | None = None) -> None:
        self.repo = repo or ExecutionRepository()

    def run(self, request: ExecutionRequest) -> ExecutionResult:
        execution_id = f"ex_{uuid.uuid4().hex}"
        created = _utcnow()

        pf = self.repo.get_portfolio(request.portfolio_id)
        if not pf:
            return ExecutionResult(
                status="failed",
                execution_id=execution_id,
                portfolio_id=request.portfolio_id,
                message="portfolio_id 不存在",
            )

        account_id = str(pf.get("account_id") or "paper_default")
        as_of = str(pf.get("as_of_date") or "")[:10]
        st = str(pf.get("status") or "")

        if st == "executed" and not request.force:
            return ExecutionResult(
                status="skipped",
                execution_id=execution_id,
                portfolio_id=request.portfolio_id,
                account_id=account_id,
                message="portfolio 已 executed（加 --force 可重跑，需先无 committed 唯一约束冲突）",
            )
        if request.force and self.repo.has_committed_posting_for_portfolio(
            request.portfolio_id
        ):
            return ExecutionResult(
                status="blocked",
                execution_id=execution_id,
                portfolio_id=request.portfolio_id,
                account_id=account_id,
                message="已有 committed ledger_posting，禁止 --force 重跑（需冲正后再处理）",
            )
        if st != "approved" and not (request.force and st == "executed"):
            return ExecutionResult(
                status="blocked",
                execution_id=execution_id,
                portfolio_id=request.portfolio_id,
                account_id=account_id,
                message=f"仅 approved 可执行，当前={st}",
            )

        existing = self.repo.find_committed_execution(request.portfolio_id)
        if existing and not request.force:
            return ExecutionResult(
                status="skipped",
                execution_id=str(existing["execution_id"]),
                portfolio_id=request.portfolio_id,
                account_id=account_id,
                message="已有 committed execution_run",
            )
        if existing and request.force:
            self.repo.supersede_committed(request.portfolio_id, finished_at=created)
            if st == "executed":
                self.repo.mark_portfolio_status(request.portfolio_id, "approved")
                st = "approved"

        stuck = self.repo.find_running_execution(request.portfolio_id)
        if stuck and not request.force:
            return ExecutionResult(
                status="blocked",
                execution_id=str(stuck["execution_id"]),
                portfolio_id=request.portfolio_id,
                account_id=account_id,
                message="已有 running execution_run（加 --force 标记失败后重跑）",
            )
        if stuck and request.force:
            self.repo.fail_running_execution(
                request.portfolio_id,
                finished_at=created,
                reason="superseded_by_force",
            )

        decision = self.repo.latest_decision(request.portfolio_id)
        if not decision or str(decision.get("status")) != "approved":
            return ExecutionResult(
                status="blocked",
                execution_id=execution_id,
                portfolio_id=request.portfolio_id,
                account_id=account_id,
                message="缺少 approved 的 risk_decision",
            )

        kill_on, kill_scopes = self.repo.is_kill_on(account_id=account_id)
        if kill_on:
            return ExecutionResult(
                status="blocked",
                execution_id=execution_id,
                portfolio_id=request.portfolio_id,
                account_id=account_id,
                message=f"Kill Switch 开启: {','.join(kill_scopes)}",
                meta={"kill_scopes": kill_scopes},
            )

        if request.adapter != "paper":
            return ExecutionResult(
                status="invalid",
                execution_id=execution_id,
                portfolio_id=request.portfolio_id,
                message=f"暂不支持 adapter={request.adapter}",
            )

        try:
            cost = self.repo.load_cost(request.cost_version)
        except RuntimeError as exc:
            return ExecutionResult(
                status="failed",
                execution_id=execution_id,
                portfolio_id=request.portfolio_id,
                account_id=account_id,
                message=str(exc),
            )

        positions = self.repo.list_positions(request.portfolio_id)
        strategy_version = str(pf.get("strategy_version") or "")
        current_shares = self.repo.load_ledger_shares(
            account_id, strategy_version=strategy_version
        )
        trade_date = as_of or created[:10]
        sellable = self.repo.load_sellable_shares(
            account_id, trade_date, strategy_version=strategy_version
        )
        cash = self.repo.load_ledger_cash(account_id)

        # 持仓中但不在目标表的标的：补价/掩码，便于卖出差额（仅本 sleeve）
        pmeta = _portfolio_meta(pf)
        factor_type = str(pmeta.get("factor_type") or "qfq")
        pos_syms = {str(p["symbol"]) for p in positions}
        need_syms = sorted(set(current_shares) - pos_syms)
        if need_syms and trade_date:
            bars = self.repo.load_bars_as_of(
                as_of=trade_date, symbols=need_syms, factor_type=factor_type
            )
            for sym in need_syms:
                b = bars.get(sym) or {}
                # 成交用未复权 close；缺 close 再退 adj_close
                px = b.get("close") if b.get("close") is not None else b.get("adj_close")
                positions.append(
                    {
                        "symbol": sym,
                        "target_shares": 0.0,
                        "price": px,
                        "can_buy": b.get("can_buy"),
                        "can_sell": b.get("can_sell"),
                    }
                )

        intents = build_paper_intents(
            positions=positions,
            current_shares=current_shares,
            sellable_shares=sellable,
        )
        orders_raw, fills_raw = simulate_paper_fills(
            intents=intents,
            cost=cost,
            trade_date=trade_date,
            cash=cash,
            lot_size=cost.lot_size,
        )

        meta: dict[str, Any] = {
            "adapter": request.adapter,
            "decision_id": decision.get("decision_id"),
            "kill_scopes": kill_scopes,
            "intent_count": len(intents),
            "job_id": request.job_id,
            "assumption": "ledger_delta_to_target_sleeve",
            "strategy_version": strategy_version,
            "ledger_position_count": len(current_shares),
            "factor_type": factor_type,
            "pricing": "unadjusted_close",
            "cash_before": cash,
        }

        order_events: list[dict[str, Any]] = []
        fill_events: list[dict[str, Any]] = []
        fill_i = 0
        for o in orders_raw:
            order_id = f"ord_{uuid.uuid4().hex}"
            order_events.append(
                {
                    "event_id": f"oe_{uuid.uuid4().hex}",
                    "order_id": order_id,
                    "execution_id": execution_id,
                    "portfolio_id": request.portfolio_id,
                    "account_id": account_id,
                    "symbol": o["symbol"],
                    "side": o["side"],
                    "qty": o["qty"],
                    "limit_price": o.get("limit_price"),
                    "status": o["status"],
                    "event_type": "NEW",
                    "reason": o.get("reason"),
                    "created_at": created,
                }
            )
            if o["status"] == "FILLED":
                order_events.append(
                    {
                        "event_id": f"oe_{uuid.uuid4().hex}",
                        "order_id": order_id,
                        "execution_id": execution_id,
                        "portfolio_id": request.portfolio_id,
                        "account_id": account_id,
                        "symbol": o["symbol"],
                        "side": o["side"],
                        "qty": o["qty"],
                        "limit_price": o.get("limit_price"),
                        "status": "FILLED",
                        "event_type": "STATUS",
                        "reason": None,
                        "created_at": created,
                    }
                )
                f = fills_raw[fill_i]
                fill_i += 1
                fill_events.append(
                    {
                        "fill_id": f"fl_{uuid.uuid4().hex}",
                        "order_id": order_id,
                        "execution_id": execution_id,
                        "portfolio_id": request.portfolio_id,
                        "account_id": account_id,
                        "symbol": f["symbol"],
                        "side": f["side"],
                        "qty": f["qty"],
                        "price": f["price"],
                        "amount": f["amount"],
                        "commission": f["commission"],
                        "stamp_tax": f["stamp_tax"],
                        "slippage_cost": f["slippage_cost"],
                        "trade_date": f["trade_date"],
                        "created_at": created,
                    }
                )

        try:
            self.repo.commit_execution_atomic(
                run_row={
                    "execution_id": execution_id,
                    "portfolio_id": request.portfolio_id,
                    "account_id": account_id,
                    "adapter": request.adapter,
                    "as_of_date": as_of or None,
                    "decision_id": decision.get("decision_id"),
                    "cost_version": request.cost_version,
                    "job_id": request.job_id,
                    "meta": meta,
                    "created_at": created,
                },
                order_events=order_events,
                fill_events=fill_events,
                order_count=len(orders_raw),
                fill_count=len(fill_events),
                finished_at=_utcnow(),
                meta=meta,
            )
            logger.info(
                "execution committed id=%s portfolio=%s orders=%s fills=%s",
                execution_id,
                request.portfolio_id,
                len(orders_raw),
                len(fill_events),
            )
            return ExecutionResult(
                status="committed",
                execution_id=execution_id,
                portfolio_id=request.portfolio_id,
                account_id=account_id,
                order_count=len(orders_raw),
                fill_count=len(fill_events),
                meta=meta,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("execution failed")
            # 原子提交失败时不应留下 running；若有残留则标记 failed
            stuck = self.repo.find_running_execution(request.portfolio_id)
            if stuck and str(stuck.get("execution_id")) == execution_id:
                self.repo.finish_run(
                    execution_id=execution_id,
                    status="failed",
                    order_count=0,
                    fill_count=0,
                    finished_at=_utcnow(),
                    error_message=str(exc),
                    meta=meta,
                )
            return ExecutionResult(
                status="failed",
                execution_id=execution_id,
                portfolio_id=request.portfolio_id,
                account_id=account_id,
                message=str(exc),
            )

    def run_approved(
        self,
        *,
        as_of: str | None = None,
        account_id: str | None = None,
        cost_version: str = "v1_ashare_default",
        force: bool = False,
        job_id: str | None = None,
        limit: int = 50,
    ) -> list[ExecutionResult]:
        rows = self.repo.list_approved_portfolios(
            as_of=as_of, account_id=account_id, limit=limit
        )
        if not rows:
            return [
                ExecutionResult(
                    status="skipped", message="无 approved 组合可执行"
                )
            ]
        return [
            self.run(
                ExecutionRequest(
                    portfolio_id=str(r["portfolio_id"]),
                    cost_version=cost_version,
                    force=force,
                    job_id=job_id,
                )
            )
            for r in rows
        ]
