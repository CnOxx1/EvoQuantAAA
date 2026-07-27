from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from ledger.models import PostRequest, PostResult
from ledger.posting import apply_fifo_sell, build_fill_entries, sellable_qty
from ledger.repository import LedgerRepository
from shared.db import get_conn

logger = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class LedgerService:
    def __init__(self, *, repo: LedgerRepository | None = None) -> None:
        self.repo = repo or LedgerRepository()

    def ensure_account(
        self, *, account_id: str, opening_cash: float = 1_000_000.0
    ) -> dict[str, Any]:
        return self.repo.ensure_account(
            account_id=account_id,
            opening_cash=opening_cash,
            created_at=_utcnow(),
        )

    def post(self, request: PostRequest) -> PostResult:
        posting_id = f"lp_{uuid.uuid4().hex}"
        created = _utcnow()

        run = self.repo.get_execution(request.execution_id)
        if not run:
            return PostResult(
                status="failed",
                posting_id=posting_id,
                execution_id=request.execution_id,
                message="execution_id 不存在",
            )
        if str(run.get("status")) != "committed":
            return PostResult(
                status="blocked",
                posting_id=posting_id,
                execution_id=request.execution_id,
                message=f"execution 未 committed，当前={run.get('status')}",
            )

        account_id = (request.account_id or str(run.get("account_id") or "")).strip()
        if not account_id:
            return PostResult(
                status="invalid",
                posting_id=posting_id,
                execution_id=request.execution_id,
                message="缺少 account_id",
            )

        self.ensure_account(account_id=account_id)

        existing = self.repo.find_committed_posting(request.execution_id)
        if existing and not request.force:
            return PostResult(
                status="skipped",
                posting_id=str(existing["posting_id"]),
                execution_id=request.execution_id,
                account_id=account_id,
                message="已有 committed ledger_posting",
            )
        if request.force:
            return PostResult(
                status="invalid",
                posting_id=posting_id,
                execution_id=request.execution_id,
                account_id=account_id,
                message="不支持 --force 重过账（避免重复记账）；需冲正分录后再处理",
            )

        stuck = self.repo.find_running_posting(request.execution_id)
        if stuck:
            sid = str(stuck["posting_id"])
            if self.repo.posting_has_entries(sid):
                return PostResult(
                    status="failed",
                    posting_id=sid,
                    execution_id=request.execution_id,
                    account_id=account_id,
                    message="存在半完成 running posting（已有分录），需人工核对后标记 failed",
                )
            self.repo.fail_running_posting(
                request.execution_id,
                finished_at=created,
                reason="empty_running_cleared_for_retry",
            )

        fills = self.repo.list_fills(request.execution_id)
        if not fills:
            return PostResult(
                status="failed",
                posting_id=posting_id,
                execution_id=request.execution_id,
                account_id=account_id,
                message="无 fill_event 可过账",
            )

        as_of = str(run.get("as_of_date") or fills[0].get("trade_date") or "")[:10]
        strategy_version = self._strategy_version_for_execution(run)
        meta: dict[str, Any] = {
            "fill_count": len(fills),
            "job_id": request.job_id,
            "force": request.force,
            "strategy_version": strategy_version,
            "sleeve": True,
        }
        self.repo.create_posting(
            {
                "posting_id": posting_id,
                "execution_id": request.execution_id,
                "account_id": account_id,
                "status": "running",
                "as_of_date": as_of or None,
                "job_id": request.job_id,
                "meta": meta,
                "created_at": created,
                "strategy_version": strategy_version,
            }
        )

        try:
            cash = self.repo.get_cash(account_id)
            lots = self.repo.list_lots(account_id, strategy_version=strategy_version)
            lot_by_id = {str(x["lot_id"]): dict(x) for x in lots}
            position_deltas: dict[str, float] = {}
            lot_inserts: list[dict[str, Any]] = []
            lot_updates: list[dict[str, Any]] = []
            entry_rows: list[dict[str, Any]] = []

            # 先卖后买：同一 execution 内按 SELL 再 BUY，且按 trade_date
            ordered = sorted(
                fills,
                key=lambda f: (
                    str(f["trade_date"])[:10],
                    0 if str(f["side"]).upper() == "SELL" else 1,
                    str(f.get("fill_id") or ""),
                ),
            )

            for f in ordered:
                side = str(f["side"]).upper()
                symbol = str(f["symbol"])
                qty = float(f["qty"])
                amount = float(f["amount"])
                commission = float(f.get("commission") or 0)
                stamp = float(f.get("stamp_tax") or 0)
                trade_date = str(f["trade_date"])[:10]
                fill_id = str(f.get("fill_id") or "")

                if side == "BUY":
                    cost = amount + commission
                    if cash + 1e-9 < cost:
                        raise RuntimeError(
                            f"现金不足 BUY {symbol}: need={cost:.4f} cash={cash:.4f}"
                        )
                    cash -= cost
                    position_deltas[symbol] = position_deltas.get(symbol, 0.0) + qty
                    lot_id = f"ll_{uuid.uuid4().hex}"
                    lot_inserts.append(
                        {
                            "lot_id": lot_id,
                            "symbol": symbol,
                            "buy_date": trade_date,
                            "qty_remaining": qty,
                            "fill_id": fill_id,
                            "strategy_version": strategy_version,
                        }
                    )
                    lot_by_id[lot_id] = {
                        "lot_id": lot_id,
                        "symbol": symbol,
                        "buy_date": trade_date,
                        "qty_remaining": qty,
                        "created_at": created,
                        "strategy_version": strategy_version,
                    }
                elif side == "SELL":
                    lot_list = list(lot_by_id.values())
                    avail = sellable_qty(lot_list, symbol=symbol, as_of=trade_date)
                    if avail + 1e-9 < qty:
                        raise RuntimeError(
                            f"T+1 可卖不足 SELL {symbol}: need={qty} sellable={avail}"
                        )
                    new_lots, taken = apply_fifo_sell(
                        lot_list, symbol=symbol, qty=qty, as_of=trade_date
                    )
                    if abs(taken - qty) > 1e-6:
                        raise RuntimeError(f"FIFO 扣减失败 {symbol}")
                    # 同步 lot_by_id
                    for nl in new_lots:
                        lid = str(nl["lot_id"])
                        if lid in lot_by_id:
                            if abs(float(nl["qty_remaining"]) - float(lot_by_id[lid]["qty_remaining"])) > 1e-12:
                                lot_by_id[lid]["qty_remaining"] = float(nl["qty_remaining"])
                                lot_updates.append(
                                    {
                                        "lot_id": lid,
                                        "qty_remaining": float(nl["qty_remaining"]),
                                    }
                                )
                    cash += amount - commission - stamp
                    position_deltas[symbol] = position_deltas.get(symbol, 0.0) - qty
                else:
                    raise RuntimeError(f"未知 side: {side}")

                for intent in build_fill_entries([f]):
                    entry_rows.append(
                        {
                            "entry_id": f"le_{uuid.uuid4().hex}",
                            **intent,
                        }
                    )

            # 合并同一 lot 多次 update（取最后）
            upd_map = {u["lot_id"]: u for u in lot_updates}
            lot_updates = list(upd_map.values())

            finished = _utcnow()
            self.repo.apply_posting_txn(
                posting_id=posting_id,
                account_id=account_id,
                entries=entry_rows,
                lot_inserts=lot_inserts,
                lot_updates=lot_updates,
                cash_after=cash,
                position_deltas=position_deltas,
                updated_at=created,
                strategy_version=strategy_version,
                commit_status="committed",
                entry_count=len(entry_rows),
                finished_at=finished,
                meta=meta,
            )
            logger.info(
                "ledger posted posting=%s execution=%s sleeve=%s entries=%s cash=%.2f",
                posting_id,
                request.execution_id,
                strategy_version,
                len(entry_rows),
                cash,
            )
            return PostResult(
                status="committed",
                posting_id=posting_id,
                execution_id=request.execution_id,
                account_id=account_id,
                entry_count=len(entry_rows),
                cash_after=cash,
                meta=meta,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("ledger post failed")
            self.repo.finish_posting(
                posting_id=posting_id,
                status="failed",
                entry_count=0,
                cash_after=self.repo.get_cash(account_id),
                finished_at=_utcnow(),
                error_message=str(exc),
                meta=meta,
            )
            return PostResult(
                status="failed",
                posting_id=posting_id,
                execution_id=request.execution_id,
                account_id=account_id,
                message=str(exc),
            )

    def _strategy_version_for_execution(self, run: dict[str, Any]) -> str:
        """优先 execution.meta，其次 portfolio_target.strategy_version。"""
        raw = run.get("meta") or run.get("meta_json") or {}
        if isinstance(raw, str):
            try:
                raw = json.loads(raw or "{}")
            except json.JSONDecodeError:
                raw = {}
        if isinstance(raw, dict):
            sv = str(raw.get("strategy_version") or "").strip()
            if sv:
                return sv
        pid = str(run.get("portfolio_id") or "")
        if not pid:
            return ""
        with get_conn() as conn:
            row = conn.execute(
                "SELECT strategy_version FROM portfolio_target WHERE portfolio_id=?",
                (pid,),
            ).fetchone()
        return str(row["strategy_version"]) if row and row["strategy_version"] else ""

    def post_unposted(
        self,
        *,
        account_id: str | None = None,
        job_id: str | None = None,
        limit: int = 50,
    ) -> list[PostResult]:
        rows = self.repo.list_unposted_executions(account_id=account_id, limit=limit)
        if not rows:
            return [
                PostResult(status="skipped", message="无未过账的 committed execution")
            ]
        return [
            self.post(
                PostRequest(
                    execution_id=str(r["execution_id"]),
                    account_id=account_id or str(r.get("account_id") or ""),
                    job_id=job_id,
                )
            )
            for r in rows
        ]

    def sellable_report(self, *, account_id: str, as_of: str) -> list[dict[str, Any]]:
        lots = self.repo.list_lots(account_id)
        symbols = sorted({str(x["symbol"]) for x in lots})
        out: list[dict[str, Any]] = []
        for sym in symbols:
            total = sum(
                float(x["qty_remaining"])
                for x in lots
                if str(x["symbol"]) == sym
            )
            sellable = sellable_qty(lots, symbol=sym, as_of=as_of)
            out.append(
                {
                    "symbol": sym,
                    "shares": total,
                    "sellable": sellable,
                    "locked": max(0.0, total - sellable),
                }
            )
        return out
