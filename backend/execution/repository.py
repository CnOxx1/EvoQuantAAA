from __future__ import annotations

import json
from typing import Any

from shared.db import get_conn
from execution.models import CostSnapshot


class ExecutionRepository:
    def load_cost(self, version: str) -> CostSnapshot:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT version, commission_rate, min_commission, stamp_tax_rate,
                       slippage_rate, lot_size
                FROM cost_params WHERE version=?
                """,
                (version,),
            ).fetchone()
        if not row:
            raise RuntimeError(f"cost_params 不存在: {version}")
        return CostSnapshot(
            version=str(row["version"]),
            commission_rate=float(row["commission_rate"]),
            min_commission=float(row["min_commission"]),
            stamp_tax_rate=float(row["stamp_tax_rate"]),
            slippage_rate=float(row["slippage_rate"]),
            lot_size=int(row["lot_size"] or 100),
        )

    def get_portfolio(self, portfolio_id: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM portfolio_target WHERE portfolio_id=?",
                (portfolio_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_positions(self, portfolio_id: str) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM portfolio_target_position
                WHERE portfolio_id=?
                ORDER BY symbol
                """,
                (portfolio_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def latest_decision(self, portfolio_id: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM risk_decision
                WHERE portfolio_id=?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (portfolio_id,),
            ).fetchone()
        return dict(row) if row else None

    def is_kill_on(self, *, account_id: str) -> tuple[bool, list[str]]:
        scopes: list[str] = []
        with get_conn() as conn:
            for key in ("GLOBAL", account_id):
                row = conn.execute(
                    "SELECT is_on FROM kill_switch WHERE scope_key=?",
                    (key,),
                ).fetchone()
                if row and int(row["is_on"] or 0) == 1:
                    scopes.append(key)
        return bool(scopes), scopes

    def find_committed_execution(self, portfolio_id: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM execution_run
                WHERE portfolio_id=? AND status='committed'
                LIMIT 1
                """,
                (portfolio_id,),
            ).fetchone()
        return dict(row) if row else None

    def find_running_execution(self, portfolio_id: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM execution_run
                WHERE portfolio_id=? AND status='running'
                LIMIT 1
                """,
                (portfolio_id,),
            ).fetchone()
        return dict(row) if row else None

    def fail_running_execution(self, portfolio_id: str, *, finished_at: str, reason: str) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE execution_run
                SET status='failed', finished_at=?, error_message=?
                WHERE portfolio_id=? AND status='running'
                """,
                (finished_at, reason, portfolio_id),
            )

    def load_ledger_cash(self, account_id: str) -> float:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT qty FROM ledger_balance
                WHERE account_id=? AND asset_type='CASH' AND symbol=''
                """,
                (account_id,),
            ).fetchone()
            if row:
                return float(row["qty"])
            acct = conn.execute(
                "SELECT opening_cash FROM ledger_account WHERE account_id=?",
                (account_id,),
            ).fetchone()
        return float(acct["opening_cash"]) if acct else 0.0

    def load_ledger_shares(
        self, account_id: str, *, strategy_version: str | None = None
    ) -> dict[str, float]:
        """持仓：有 strategy_version 时读 sleeve，否则读账户合计 POSITION。"""
        if strategy_version is not None:
            with get_conn() as conn:
                rows = conn.execute(
                    """
                    SELECT symbol, qty FROM ledger_sleeve_position
                    WHERE account_id=? AND strategy_version=? AND qty<>0
                    """,
                    (account_id, strategy_version),
                ).fetchall()
            return {str(r["symbol"]): float(r["qty"]) for r in rows}
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT symbol, qty FROM ledger_balance
                WHERE account_id=? AND asset_type='POSITION' AND qty<>0
                """,
                (account_id,),
            ).fetchall()
        return {str(r["symbol"]): float(r["qty"]) for r in rows}

    def load_sellable_shares(
        self,
        account_id: str,
        as_of: str,
        *,
        strategy_version: str | None = None,
    ) -> dict[str, float]:
        """T+1：buy_date < as_of 的 lot 可卖数量合计（可按 sleeve 过滤）。"""
        sql = """
            SELECT symbol, SUM(qty_remaining) AS qty
            FROM ledger_lot
            WHERE account_id=? AND qty_remaining>0 AND buy_date<?
        """
        params: list[Any] = [account_id, as_of[:10]]
        if strategy_version is not None:
            sql += " AND strategy_version=?"
            params.append(strategy_version)
        sql += " GROUP BY symbol"
        with get_conn() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return {str(r["symbol"]): float(r["qty"] or 0) for r in rows}

    def has_committed_posting_for_portfolio(self, portfolio_id: str) -> bool:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT 1
                FROM execution_run e
                JOIN ledger_posting p ON p.execution_id=e.execution_id
                WHERE e.portfolio_id=? AND e.status='committed'
                  AND p.status='committed'
                LIMIT 1
                """,
                (portfolio_id,),
            ).fetchone()
        return bool(row)

    def load_bars_as_of(
        self,
        *,
        as_of: str,
        symbols: list[str],
        factor_type: str = "qfq",
        lookback_days: int = 60,
    ) -> dict[str, dict[str, Any]]:
        if not symbols:
            return {}
        from datetime import date, timedelta

        start = (date.fromisoformat(as_of[:10]) - timedelta(days=lookback_days)).isoformat()
        ph = ",".join("?" * len(symbols))
        sql = f"""
            SELECT symbol, trade_date, close, adj_close, can_buy, can_sell
            FROM processed_equity_bar_1d
            WHERE factor_type=? AND trade_date>=? AND trade_date<=?
              AND symbol IN ({ph})
            ORDER BY symbol, trade_date DESC
        """
        with get_conn() as conn:
            rows = conn.execute(
                sql, (factor_type, start, as_of[:10], *symbols)
            ).fetchall()
        out: dict[str, dict[str, Any]] = {}
        for r in rows:
            sym = str(r["symbol"])
            if sym in out:
                continue
            out[sym] = dict(r)
        return out

    def list_approved_portfolios(
        self, *, as_of: str | None = None, account_id: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM portfolio_target WHERE status='approved'"
        params: list[Any] = []
        if as_of:
            sql += " AND as_of_date=?"
            params.append(as_of[:10])
        if account_id:
            sql += " AND account_id=?"
            params.append(account_id)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(limit, 200)))
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def create_run(self, row: dict[str, Any]) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO execution_run (
                    execution_id, portfolio_id, account_id, adapter, status,
                    as_of_date, decision_id, cost_version, order_count, fill_count,
                    job_id, meta_json, error_message, created_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["execution_id"],
                    row["portfolio_id"],
                    row["account_id"],
                    row["adapter"],
                    row["status"],
                    row.get("as_of_date"),
                    row.get("decision_id"),
                    row["cost_version"],
                    row.get("order_count"),
                    row.get("fill_count"),
                    row.get("job_id"),
                    json.dumps(row.get("meta") or {}, ensure_ascii=False),
                    row.get("error_message"),
                    row["created_at"],
                    row.get("finished_at"),
                ),
            )

    def finish_run(
        self,
        *,
        execution_id: str,
        status: str,
        order_count: int,
        fill_count: int,
        finished_at: str,
        error_message: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE execution_run
                SET status=?, order_count=?, fill_count=?, finished_at=?,
                    error_message=?, meta_json=COALESCE(?, meta_json)
                WHERE execution_id=?
                """,
                (
                    status,
                    order_count,
                    fill_count,
                    finished_at,
                    error_message,
                    json.dumps(meta, ensure_ascii=False) if meta is not None else None,
                    execution_id,
                ),
            )

    def insert_order_events(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        sql = """
            INSERT INTO order_event (
                event_id, order_id, execution_id, portfolio_id, account_id,
                symbol, side, qty, limit_price, status, event_type, reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = [
            (
                r["event_id"],
                r["order_id"],
                r["execution_id"],
                r["portfolio_id"],
                r["account_id"],
                r["symbol"],
                r["side"],
                float(r["qty"]),
                r.get("limit_price"),
                r["status"],
                r["event_type"],
                r.get("reason"),
                r["created_at"],
            )
            for r in rows
        ]
        with get_conn() as conn:
            conn.executemany(sql, params)

    def insert_fills(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        sql = """
            INSERT INTO fill_event (
                fill_id, order_id, execution_id, portfolio_id, account_id,
                symbol, side, qty, price, amount, commission, stamp_tax,
                slippage_cost, trade_date, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = [
            (
                r["fill_id"],
                r["order_id"],
                r["execution_id"],
                r["portfolio_id"],
                r["account_id"],
                r["symbol"],
                r["side"],
                float(r["qty"]),
                float(r["price"]),
                float(r["amount"]),
                float(r["commission"]),
                float(r.get("stamp_tax") or 0),
                float(r.get("slippage_cost") or 0),
                r["trade_date"],
                r["created_at"],
            )
            for r in rows
        ]
        with get_conn() as conn:
            conn.executemany(sql, params)

    def commit_execution_atomic(
        self,
        *,
        run_row: dict[str, Any],
        order_events: list[dict[str, Any]],
        fill_events: list[dict[str, Any]],
        order_count: int,
        fill_count: int,
        finished_at: str,
        meta: dict[str, Any],
        mark_portfolio_executed: bool = True,
    ) -> None:
        """单事务：INSERT run(running) → orders/fills → run=committed → portfolio=executed。"""
        order_sql = """
            INSERT INTO order_event (
                event_id, order_id, execution_id, portfolio_id, account_id,
                symbol, side, qty, limit_price, status, event_type, reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        fill_sql = """
            INSERT INTO fill_event (
                fill_id, order_id, execution_id, portfolio_id, account_id,
                symbol, side, qty, price, amount, commission, stamp_tax,
                slippage_cost, trade_date, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO execution_run (
                    execution_id, portfolio_id, account_id, adapter, status,
                    as_of_date, decision_id, cost_version, order_count, fill_count,
                    job_id, meta_json, error_message, created_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_row["execution_id"],
                    run_row["portfolio_id"],
                    run_row["account_id"],
                    run_row["adapter"],
                    "running",
                    run_row.get("as_of_date"),
                    run_row.get("decision_id"),
                    run_row["cost_version"],
                    0,
                    0,
                    run_row.get("job_id"),
                    json.dumps(run_row.get("meta") or {}, ensure_ascii=False),
                    None,
                    run_row["created_at"],
                    None,
                ),
            )
            if order_events:
                conn.executemany(
                    order_sql,
                    [
                        (
                            r["event_id"],
                            r["order_id"],
                            r["execution_id"],
                            r["portfolio_id"],
                            r["account_id"],
                            r["symbol"],
                            r["side"],
                            float(r["qty"]),
                            r.get("limit_price"),
                            r["status"],
                            r["event_type"],
                            r.get("reason"),
                            r["created_at"],
                        )
                        for r in order_events
                    ],
                )
            if fill_events:
                conn.executemany(
                    fill_sql,
                    [
                        (
                            r["fill_id"],
                            r["order_id"],
                            r["execution_id"],
                            r["portfolio_id"],
                            r["account_id"],
                            r["symbol"],
                            r["side"],
                            float(r["qty"]),
                            float(r["price"]),
                            float(r["amount"]),
                            float(r["commission"]),
                            float(r.get("stamp_tax") or 0),
                            float(r.get("slippage_cost") or 0),
                            r["trade_date"],
                            r["created_at"],
                        )
                        for r in fill_events
                    ],
                )
            conn.execute(
                """
                UPDATE execution_run
                SET status='committed', order_count=?, fill_count=?, finished_at=?,
                    error_message=NULL, meta_json=?
                WHERE execution_id=?
                """,
                (
                    order_count,
                    fill_count,
                    finished_at,
                    json.dumps(meta, ensure_ascii=False),
                    run_row["execution_id"],
                ),
            )
            if mark_portfolio_executed:
                conn.execute(
                    "UPDATE portfolio_target SET status='executed' WHERE portfolio_id=?",
                    (run_row["portfolio_id"],),
                )

    def supersede_committed(self, portfolio_id: str, *, finished_at: str) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE execution_run
                SET status='superseded', finished_at=COALESCE(finished_at, ?)
                WHERE portfolio_id=? AND status='committed'
                """,
                (finished_at, portfolio_id),
            )

    def mark_portfolio_status(self, portfolio_id: str, status: str) -> None:
        with get_conn() as conn:
            conn.execute(
                "UPDATE portfolio_target SET status=? WHERE portfolio_id=?",
                (status, portfolio_id),
            )

    def mark_portfolio_executed(self, portfolio_id: str) -> None:
        self.mark_portfolio_status(portfolio_id, "executed")

    def get_run(self, execution_id: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM execution_run WHERE execution_id=?",
                (execution_id,),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["meta"] = json.loads(str(d.get("meta_json") or "{}"))
        except json.JSONDecodeError:
            d["meta"] = {}
        return d

    def list_orders(self, execution_id: str) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM order_event
                WHERE execution_id=?
                ORDER BY created_at, symbol
                """,
                (execution_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def list_fills(self, execution_id: str) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM fill_event
                WHERE execution_id=?
                ORDER BY created_at, symbol
                """,
                (execution_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def list_runs(
        self,
        *,
        portfolio_id: str | None = None,
        account_id: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM execution_run WHERE 1=1"
        params: list[Any] = []
        if portfolio_id:
            sql += " AND portfolio_id=?"
            params.append(portfolio_id)
        if account_id:
            sql += " AND account_id=?"
            params.append(account_id)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(limit, 200)))
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]
