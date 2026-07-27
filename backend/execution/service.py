from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from execution.models import ExecutionRequest, ExecutionResult
from execution.paper import (
    build_paper_intents,
    build_pending_intents,
    compute_residuals,
    simulate_paper_fills,
)
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


def _build_order_fill_events(
    *,
    orders_raw: list[dict[str, Any]],
    fills_raw: list[dict[str, Any]],
    execution_id: str,
    portfolio_id: str,
    account_id: str,
    created: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
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
                "portfolio_id": portfolio_id,
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
                    "portfolio_id": portfolio_id,
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
                    "portfolio_id": portfolio_id,
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
    return order_events, fill_events


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
                execution_id=execution_id,
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
        residuals = compute_residuals(
            intents=intents,
            orders=orders_raw,
            fills=fills_raw,
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
            "run_kind": "portfolio",
            "pending_residual_count": len(residuals),
        }

        order_events, fill_events = _build_order_fill_events(
            orders_raw=orders_raw,
            fills_raw=fills_raw,
            execution_id=execution_id,
            portfolio_id=request.portfolio_id,
            account_id=account_id,
            created=created,
        )

        pending_upserts = [
            {
                "pending_id": f"ep_{uuid.uuid4().hex}",
                "account_id": account_id,
                "strategy_version": strategy_version,
                "symbol": r["symbol"],
                "side": r["side"],
                "qty_remaining": r["qty_remaining"],
                "qty_origin": r["qty_origin"],
                "source_portfolio_id": request.portfolio_id,
                "source_execution_id": execution_id,
                "origin_as_of": trade_date,
                "last_reason": r.get("last_reason"),
                "meta": {"from": "portfolio_execution"},
            }
            for r in residuals
        ]

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
                    "run_kind": "portfolio",
                    "strategy_version": strategy_version,
                },
                order_events=order_events,
                fill_events=fill_events,
                order_count=len(orders_raw),
                fill_count=len(fill_events),
                finished_at=_utcnow(),
                meta=meta,
                mark_portfolio_executed=True,
                supersede_open_pending={
                    "account_id": account_id,
                    "strategy_version": strategy_version,
                },
                pending_upserts=pending_upserts,
            )
            logger.info(
                "execution committed id=%s portfolio=%s orders=%s fills=%s pending=%s",
                execution_id,
                request.portfolio_id,
                len(orders_raw),
                len(fill_events),
                len(pending_upserts),
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

    def resume_pending(
        self,
        *,
        as_of: str,
        account_id: str = "paper_default",
        cost_version: str = "v1_ashare_default",
        strategy_version: str | None = None,
        job_id: str | None = None,
        factor_type: str = "qfq",
    ) -> list[ExecutionResult]:
        """续撮 open pending（按 sleeve）；同日同 sleeve 幂等跳过。"""
        as_of_d = as_of[:10]
        kill_on, kill_scopes = self.repo.is_kill_on(account_id=account_id)
        if kill_on:
            return [
                ExecutionResult(
                    status="blocked",
                    account_id=account_id,
                    message=f"Kill Switch 开启: {','.join(kill_scopes)}",
                    meta={"kill_scopes": kill_scopes},
                )
            ]

        open_rows = self.repo.list_open_pending(
            account_id=account_id, strategy_version=strategy_version
        )
        if not open_rows:
            return [
                ExecutionResult(
                    status="skipped",
                    account_id=account_id,
                    message="无 open execution_pending",
                )
            ]

        try:
            cost = self.repo.load_cost(cost_version)
        except RuntimeError as exc:
            return [
                ExecutionResult(
                    status="failed", account_id=account_id, message=str(exc)
                )
            ]

        by_sv: dict[str, list[dict[str, Any]]] = {}
        for row in open_rows:
            by_sv.setdefault(str(row["strategy_version"]), []).append(row)

        results: list[ExecutionResult] = []
        for sv, pendings in sorted(by_sv.items()):
            existing = self.repo.find_pending_resume_committed(
                account_id=account_id, as_of=as_of_d, strategy_version=sv
            )
            if existing:
                results.append(
                    ExecutionResult(
                        status="skipped",
                        execution_id=str(existing["execution_id"]),
                        account_id=account_id,
                        message=f"当日 pending_resume 已 committed sleeve={sv}",
                        meta={"strategy_version": sv},
                    )
                )
                continue
            results.append(
                self._resume_sleeve(
                    as_of=as_of_d,
                    account_id=account_id,
                    strategy_version=sv,
                    pendings=pendings,
                    cost=cost,
                    cost_version=cost_version,
                    job_id=job_id,
                    factor_type=factor_type,
                )
            )
        return results

    def _resume_sleeve(
        self,
        *,
        as_of: str,
        account_id: str,
        strategy_version: str,
        pendings: list[dict[str, Any]],
        cost: Any,
        cost_version: str,
        job_id: str | None,
        factor_type: str,
    ) -> ExecutionResult:
        execution_id = f"ex_{uuid.uuid4().hex}"
        created = _utcnow()
        # 合成 portfolio_id，避免与 portfolio 类 committed/running 唯一冲突
        portfolio_id = f"pf_pend_{uuid.uuid4().hex}"
        source_pf = str(pendings[0].get("source_portfolio_id") or portfolio_id)

        symbols = sorted({str(p["symbol"]) for p in pendings})
        bars = self.repo.load_bars_as_of(
            as_of=as_of, symbols=symbols, factor_type=factor_type
        )
        sellable = self.repo.load_sellable_shares(
            account_id, as_of, strategy_version=strategy_version
        )
        cash = self.repo.load_ledger_cash(account_id)

        intents = build_pending_intents(
            pendings=pendings, bars=bars, sellable_shares=sellable
        )
        orders_raw, fills_raw = simulate_paper_fills(
            intents=intents,
            cost=cost,
            trade_date=as_of,
            cash=cash,
            lot_size=cost.lot_size,
        )
        residuals = compute_residuals(
            intents=intents,
            orders=orders_raw,
            fills=fills_raw,
            lot_size=cost.lot_size,
        )
        residual_key = {(r["symbol"], r["side"]): r for r in residuals}

        order_events, fill_events = _build_order_fill_events(
            orders_raw=orders_raw,
            fills_raw=fills_raw,
            execution_id=execution_id,
            portfolio_id=portfolio_id,
            account_id=account_id,
            created=created,
        )

        pending_closes: list[dict[str, Any]] = []
        pending_upserts: list[dict[str, Any]] = []
        pending_events: list[dict[str, Any]] = []
        for p in pendings:
            key = (str(p["symbol"]), str(p["side"]))
            before = float(p["qty_remaining"])
            rem = residual_key.get(key)
            after = float(rem["qty_remaining"]) if rem else 0.0
            if after + 1e-9 < cost.lot_size:
                pending_closes.append(
                    {
                        "pending_id": p["pending_id"],
                        "status": "filled",
                        "qty_remaining": 0.0,
                        "last_reason": None,
                        "source_execution_id": execution_id,
                    }
                )
                status_ev = "filled"
            else:
                pending_closes.append(
                    {
                        "pending_id": p["pending_id"],
                        "status": "open",
                        "qty_remaining": after,
                        "last_reason": rem.get("last_reason") if rem else p.get("last_reason"),
                        "source_execution_id": execution_id,
                    }
                )
                status_ev = "partial"
            pending_events.append(
                {
                    "event_id": f"epe_{uuid.uuid4().hex}",
                    "pending_id": p["pending_id"],
                    "execution_id": execution_id,
                    "trade_date": as_of,
                    "qty_before": before,
                    "qty_after": after if after + 1e-9 >= cost.lot_size else 0.0,
                    "reason": status_ev,
                }
            )

        meta: dict[str, Any] = {
            "adapter": "paper",
            "run_kind": "pending_resume",
            "resume": True,
            "strategy_version": strategy_version,
            "source_portfolio_id": source_pf,
            "pending_in": len(pendings),
            "pending_still_open": sum(
                1 for c in pending_closes if c["status"] == "open"
            ),
            "job_id": job_id,
            "pricing": "unadjusted_close",
            "cash_before": cash,
            "factor_type": factor_type,
        }

        try:
            self.repo.commit_execution_atomic(
                run_row={
                    "execution_id": execution_id,
                    "portfolio_id": portfolio_id,
                    "account_id": account_id,
                    "adapter": "paper",
                    "as_of_date": as_of,
                    "decision_id": None,
                    "cost_version": cost_version,
                    "job_id": job_id,
                    "meta": meta,
                    "created_at": created,
                    "run_kind": "pending_resume",
                    "strategy_version": strategy_version,
                },
                order_events=order_events,
                fill_events=fill_events,
                order_count=len(orders_raw),
                fill_count=len(fill_events),
                finished_at=_utcnow(),
                meta=meta,
                mark_portfolio_executed=False,
                pending_closes=pending_closes,
                pending_events=pending_events,
            )
            logger.info(
                "pending_resume committed id=%s sleeve=%s orders=%s fills=%s",
                execution_id,
                strategy_version,
                len(orders_raw),
                len(fill_events),
            )
            return ExecutionResult(
                status="committed",
                execution_id=execution_id,
                portfolio_id=portfolio_id,
                account_id=account_id,
                order_count=len(orders_raw),
                fill_count=len(fill_events),
                meta=meta,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("pending_resume failed")
            return ExecutionResult(
                status="failed",
                execution_id=execution_id,
                portfolio_id=portfolio_id,
                account_id=account_id,
                message=str(exc),
                meta=meta,
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
