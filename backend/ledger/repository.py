from __future__ import annotations

import json
from typing import Any

from shared.db import get_conn


class LedgerRepository:
    def ensure_account(
        self,
        *,
        account_id: str,
        opening_cash: float,
        created_at: str,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with get_conn() as conn:
            existing = conn.execute(
                "SELECT * FROM ledger_account WHERE account_id=?",
                (account_id,),
            ).fetchone()
            if not existing:
                conn.execute(
                    """
                    INSERT INTO ledger_account (
                        account_id, currency, opening_cash, status, meta_json, created_at
                    ) VALUES (?, 'CNY', ?, 'active', ?, ?)
                    """,
                    (
                        account_id,
                        float(opening_cash),
                        json.dumps(meta or {}, ensure_ascii=False),
                        created_at,
                    ),
                )
                opening = float(opening_cash)
            else:
                opening = float(existing["opening_cash"])

            bal = conn.execute(
                """
                SELECT qty FROM ledger_balance
                WHERE account_id=? AND asset_type='CASH' AND symbol=''
                """,
                (account_id,),
            ).fetchone()
            if not bal:
                conn.execute(
                    """
                    INSERT INTO ledger_balance (account_id, asset_type, symbol, qty, updated_at)
                    VALUES (?, 'CASH', '', ?, ?)
                    """,
                    (account_id, opening, created_at),
                )
            row = conn.execute(
                "SELECT * FROM ledger_account WHERE account_id=?",
                (account_id,),
            ).fetchone()
        return dict(row)

    def get_account(self, account_id: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM ledger_account WHERE account_id=?",
                (account_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_execution(self, execution_id: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM execution_run WHERE execution_id=?",
                (execution_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_fills(self, execution_id: str) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM fill_event
                WHERE execution_id=?
                ORDER BY trade_date, symbol, fill_id
                """,
                (execution_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def find_committed_posting(self, execution_id: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM ledger_posting
                WHERE execution_id=? AND status='committed'
                LIMIT 1
                """,
                (execution_id,),
            ).fetchone()
        return dict(row) if row else None

    def find_running_posting(self, execution_id: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM ledger_posting
                WHERE execution_id=? AND status='running'
                LIMIT 1
                """,
                (execution_id,),
            ).fetchone()
        return dict(row) if row else None

    def posting_has_entries(self, posting_id: str) -> bool:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM ledger_entry WHERE posting_id=? LIMIT 1",
                (posting_id,),
            ).fetchone()
        return bool(row)

    def fail_running_posting(
        self, execution_id: str, *, finished_at: str, reason: str
    ) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE ledger_posting
                SET status='failed', finished_at=?, error_message=?
                WHERE execution_id=? AND status='running'
                """,
                (finished_at, reason, execution_id),
            )

    def list_unposted_executions(
        self, *, account_id: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT e.*
            FROM execution_run e
            WHERE e.status='committed'
              AND NOT EXISTS (
                SELECT 1 FROM ledger_posting p
                WHERE p.execution_id=e.execution_id AND p.status='committed'
              )
        """
        params: list[Any] = []
        if account_id:
            sql += " AND e.account_id=?"
            params.append(account_id)
        sql += " ORDER BY e.created_at LIMIT ?"
        params.append(max(1, min(limit, 200)))
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def get_cash(self, account_id: str) -> float:
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
        acct = self.get_account(account_id)
        return float(acct["opening_cash"]) if acct else 0.0

    def list_positions(self, account_id: str) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM ledger_balance
                WHERE account_id=? AND asset_type='POSITION' AND qty<>0
                ORDER BY symbol
                """,
                (account_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def list_lots(self, account_id: str, *, symbol: str | None = None) -> list[dict[str, Any]]:
        sql = """
            SELECT * FROM ledger_lot
            WHERE account_id=? AND qty_remaining>0
        """
        params: list[Any] = [account_id]
        if symbol:
            sql += " AND symbol=?"
            params.append(symbol)
        sql += " ORDER BY buy_date, created_at, lot_id"
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def create_posting(self, row: dict[str, Any]) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO ledger_posting (
                    posting_id, execution_id, account_id, status, as_of_date,
                    entry_count, cash_after, job_id, meta_json, error_message,
                    created_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["posting_id"],
                    row["execution_id"],
                    row["account_id"],
                    row["status"],
                    row.get("as_of_date"),
                    row.get("entry_count"),
                    row.get("cash_after"),
                    row.get("job_id"),
                    json.dumps(row.get("meta") or {}, ensure_ascii=False),
                    row.get("error_message"),
                    row["created_at"],
                    row.get("finished_at"),
                ),
            )

    def finish_posting(
        self,
        *,
        posting_id: str,
        status: str,
        entry_count: int,
        cash_after: float,
        finished_at: str,
        error_message: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE ledger_posting
                SET status=?, entry_count=?, cash_after=?, finished_at=?,
                    error_message=?, meta_json=COALESCE(?, meta_json)
                WHERE posting_id=?
                """,
                (
                    status,
                    entry_count,
                    cash_after,
                    finished_at,
                    error_message,
                    json.dumps(meta, ensure_ascii=False) if meta is not None else None,
                    posting_id,
                ),
            )

    def supersede_committed_posting(self, execution_id: str, *, finished_at: str) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE ledger_posting
                SET status='superseded', finished_at=COALESCE(finished_at, ?)
                WHERE execution_id=? AND status='committed'
                """,
                (finished_at, execution_id),
            )

    def apply_posting_txn(
        self,
        *,
        posting_id: str,
        account_id: str,
        entries: list[dict[str, Any]],
        lot_inserts: list[dict[str, Any]],
        lot_updates: list[dict[str, Any]],
        cash_after: float,
        position_deltas: dict[str, float],
        updated_at: str,
        commit_status: str | None = None,
        entry_count: int | None = None,
        finished_at: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """单事务写入分录并更新余额/批次；可选同事务置 posting=committed。"""
        with get_conn() as conn:
            for e in entries:
                conn.execute(
                    """
                    INSERT INTO ledger_entry (
                        entry_id, posting_id, account_id, entry_type, symbol,
                        qty, amount, fill_id, trade_date, memo, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        e["entry_id"],
                        posting_id,
                        account_id,
                        e["entry_type"],
                        e.get("symbol"),
                        e.get("qty"),
                        float(e["amount"]),
                        e.get("fill_id"),
                        e.get("trade_date"),
                        e.get("memo"),
                        updated_at,
                    ),
                )

            conn.execute(
                """
                INSERT INTO ledger_balance (account_id, asset_type, symbol, qty, updated_at)
                VALUES (?, 'CASH', '', ?, ?)
                ON CONFLICT (account_id, asset_type, symbol) DO UPDATE SET
                    qty=EXCLUDED.qty, updated_at=EXCLUDED.updated_at
                """,
                (account_id, cash_after, updated_at),
            )

            for symbol, delta in position_deltas.items():
                row = conn.execute(
                    """
                    SELECT qty FROM ledger_balance
                    WHERE account_id=? AND asset_type='POSITION' AND symbol=?
                    """,
                    (account_id, symbol),
                ).fetchone()
                cur = float(row["qty"]) if row else 0.0
                new_qty = cur + float(delta)
                conn.execute(
                    """
                    INSERT INTO ledger_balance (account_id, asset_type, symbol, qty, updated_at)
                    VALUES (?, 'POSITION', ?, ?, ?)
                    ON CONFLICT (account_id, asset_type, symbol) DO UPDATE SET
                        qty=EXCLUDED.qty, updated_at=EXCLUDED.updated_at
                    """,
                    (account_id, symbol, new_qty, updated_at),
                )

            for lot in lot_inserts:
                conn.execute(
                    """
                    INSERT INTO ledger_lot (
                        lot_id, account_id, symbol, buy_date, qty_remaining,
                        fill_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        lot["lot_id"],
                        account_id,
                        lot["symbol"],
                        lot["buy_date"],
                        float(lot["qty_remaining"]),
                        lot.get("fill_id"),
                        updated_at,
                    ),
                )
            for lot in lot_updates:
                conn.execute(
                    """
                    UPDATE ledger_lot SET qty_remaining=?
                    WHERE lot_id=?
                    """,
                    (float(lot["qty_remaining"]), lot["lot_id"]),
                )

            if commit_status:
                conn.execute(
                    """
                    UPDATE ledger_posting
                    SET status=?, entry_count=?, cash_after=?, finished_at=?,
                        error_message=NULL,
                        meta_json=COALESCE(?, meta_json)
                    WHERE posting_id=?
                    """,
                    (
                        commit_status,
                        entry_count if entry_count is not None else len(entries),
                        cash_after,
                        finished_at or updated_at,
                        json.dumps(meta, ensure_ascii=False) if meta is not None else None,
                        posting_id,
                    ),
                )

    def get_posting(self, posting_id: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM ledger_posting WHERE posting_id=?",
                (posting_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_postings(
        self, *, account_id: str | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM ledger_posting WHERE 1=1"
        params: list[Any] = []
        if account_id:
            sql += " AND account_id=?"
            params.append(account_id)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(limit, 200)))
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def list_entries(self, posting_id: str) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM ledger_entry
                WHERE posting_id=?
                ORDER BY created_at, entry_id
                """,
                (posting_id,),
            ).fetchall()
        return [dict(r) for r in rows]
