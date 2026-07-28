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
                       slippage_rate, lot_size,
                       impact_model, impact_coef, adv_lookback_days
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
            impact_model=str(row["impact_model"] or "flat"),
            impact_coef=float(row["impact_coef"] or 0),
            adv_lookback_days=int(row["adv_lookback_days"] or 20),
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
                  AND COALESCE(run_kind, 'portfolio')='portfolio'
                LIMIT 1
                """,
                (portfolio_id,),
            ).fetchone()
        return dict(row) if row else None

    def find_pending_resume_committed(
        self, *, account_id: str, as_of: str, strategy_version: str
    ) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM execution_run
                WHERE account_id=? AND as_of_date=? AND strategy_version=?
                  AND status='committed' AND run_kind='pending_resume'
                LIMIT 1
                """,
                (account_id, as_of[:10], strategy_version),
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
        include_amount: bool = False,
    ) -> dict[str, dict[str, Any]]:
        if not symbols:
            return {}
        from datetime import date, timedelta

        start = (date.fromisoformat(as_of[:10]) - timedelta(days=lookback_days)).isoformat()
        ph = ",".join("?" * len(symbols))
        amt_col = ", amount" if include_amount else ""
        sql = f"""
            SELECT symbol, trade_date, close, adj_close, can_buy, can_sell{amt_col}
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

    def load_adv_map(
        self,
        *,
        symbols: list[str],
        as_of: str,
        lookback_days: int = 20,
        factor_type: str = "qfq",
    ) -> dict[str, float]:
        """as_of 及以前 lookback 个交易日的平均成交额。"""
        if not symbols:
            return {}
        lookback = max(1, int(lookback_days))
        ph = ",".join("?" * len(symbols))
        with get_conn() as conn:
            date_rows = conn.execute(
                """
                SELECT DISTINCT trade_date FROM processed_equity_bar_1d
                WHERE trade_date <= ? AND factor_type=?
                ORDER BY trade_date DESC
                LIMIT ?
                """,
                (as_of[:10], factor_type, lookback),
            ).fetchall()
            dates = [str(r["trade_date"])[:10] for r in date_rows]
            if not dates:
                return {}
            date_ph = ",".join("?" * len(dates))
            rows = conn.execute(
                f"""
                SELECT symbol, AVG(amount) AS adv
                FROM processed_equity_bar_1d
                WHERE factor_type=?
                  AND trade_date IN ({date_ph})
                  AND symbol IN ({ph})
                  AND amount IS NOT NULL AND amount > 0
                GROUP BY symbol
                """,
                (factor_type, *dates, *symbols),
            ).fetchall()
        return {
            str(r["symbol"]): float(r["adv"])
            for r in rows
            if r["adv"] is not None
        }

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
        pending_upserts: list[dict[str, Any]] | None = None,
        pending_closes: list[dict[str, Any]] | None = None,
        pending_events: list[dict[str, Any]] | None = None,
        supersede_open_pending: dict[str, str] | None = None,
    ) -> None:
        """
        单事务：INSERT run(running) → orders/fills → pending 维护 → committed
        → 可选 portfolio=executed。
        supersede_open_pending: {account_id, strategy_version} 先关闭该 sleeve 全部 open。
        """
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
        run_kind = str(run_row.get("run_kind") or "portfolio")
        strategy_version = run_row.get("strategy_version")
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO execution_run (
                    execution_id, portfolio_id, account_id, adapter, status,
                    as_of_date, decision_id, cost_version, order_count, fill_count,
                    job_id, meta_json, error_message, created_at, finished_at,
                    run_kind, strategy_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    run_kind,
                    strategy_version,
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

            if supersede_open_pending:
                conn.execute(
                    """
                    UPDATE execution_pending
                    SET status='superseded', updated_at=?,
                        source_execution_id=COALESCE(?, source_execution_id)
                    WHERE account_id=? AND strategy_version=? AND status='open'
                    """,
                    (
                        finished_at,
                        run_row["execution_id"],
                        supersede_open_pending["account_id"],
                        supersede_open_pending["strategy_version"],
                    ),
                )

            for p in pending_closes or []:
                conn.execute(
                    """
                    UPDATE execution_pending
                    SET status=?, qty_remaining=?, last_reason=?,
                        source_execution_id=?, updated_at=?
                    WHERE pending_id=?
                    """,
                    (
                        p["status"],
                        float(p["qty_remaining"]),
                        p.get("last_reason"),
                        p.get("source_execution_id"),
                        finished_at,
                        p["pending_id"],
                    ),
                )

            for p in pending_upserts or []:
                existing = conn.execute(
                    """
                    SELECT pending_id FROM execution_pending
                    WHERE account_id=? AND strategy_version=? AND symbol=? AND side=?
                      AND status='open'
                    LIMIT 1
                    """,
                    (
                        p["account_id"],
                        p["strategy_version"],
                        p["symbol"],
                        p["side"],
                    ),
                ).fetchone()
                if existing:
                    conn.execute(
                        """
                        UPDATE execution_pending
                        SET qty_remaining=?, qty_origin=?, last_reason=?,
                            source_portfolio_id=?, source_execution_id=?,
                            updated_at=?, meta_json=?
                        WHERE pending_id=?
                        """,
                        (
                            float(p["qty_remaining"]),
                            float(p["qty_origin"]),
                            p.get("last_reason"),
                            p["source_portfolio_id"],
                            p.get("source_execution_id"),
                            finished_at,
                            json.dumps(p.get("meta") or {}, ensure_ascii=False),
                            str(existing["pending_id"]),
                        ),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO execution_pending (
                            pending_id, account_id, strategy_version, symbol, side,
                            qty_remaining, qty_origin, source_portfolio_id,
                            source_execution_id, origin_as_of, last_reason, status,
                            meta_json, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?)
                        """,
                        (
                            p["pending_id"],
                            p["account_id"],
                            p["strategy_version"],
                            p["symbol"],
                            p["side"],
                            float(p["qty_remaining"]),
                            float(p["qty_origin"]),
                            p["source_portfolio_id"],
                            p.get("source_execution_id"),
                            p["origin_as_of"],
                            p.get("last_reason"),
                            json.dumps(p.get("meta") or {}, ensure_ascii=False),
                            finished_at,
                            finished_at,
                        ),
                    )

            for ev in pending_events or []:
                conn.execute(
                    """
                    INSERT INTO execution_pending_event (
                        event_id, pending_id, execution_id, trade_date,
                        qty_before, qty_after, reason, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ev["event_id"],
                        ev["pending_id"],
                        ev.get("execution_id"),
                        ev.get("trade_date"),
                        float(ev["qty_before"]),
                        float(ev["qty_after"]),
                        ev.get("reason"),
                        finished_at,
                    ),
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

    def list_open_pending(
        self,
        *,
        account_id: str,
        strategy_version: str | None = None,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT * FROM execution_pending
            WHERE account_id=? AND status='open'
        """
        params: list[Any] = [account_id]
        if strategy_version is not None:
            sql += " AND strategy_version=?"
            params.append(strategy_version)
        sql += " ORDER BY strategy_version, symbol, side"
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def list_pending(
        self,
        *,
        account_id: str | None = None,
        status: str | None = "open",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM execution_pending WHERE 1=1"
        params: list[Any] = []
        if account_id:
            sql += " AND account_id=?"
            params.append(account_id)
        if status:
            sql += " AND status=?"
            params.append(status)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(max(1, min(limit, 500)))
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def supersede_committed(self, portfolio_id: str, *, finished_at: str) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE execution_run
                SET status='superseded', finished_at=COALESCE(finished_at, ?)
                WHERE portfolio_id=? AND status='committed'
                  AND COALESCE(run_kind, 'portfolio')='portfolio'
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
