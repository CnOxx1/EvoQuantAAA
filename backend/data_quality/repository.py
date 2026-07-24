from __future__ import annotations

import json
from typing import Any

from shared.db import get_conn


def _ph(n: int) -> str:
    return ",".join("?" * n)


class DqRepository:
    def load_processed_equity(
        self,
        *,
        start: str | None,
        end: str | None,
        symbols: list[str],
        factor_type: str,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT symbol, trade_date, open, high, low, close,
                   adj_factor, adj_close, ret_1d,
                   is_suspended, is_limit_up, is_limit_down, can_buy, can_sell,
                   factor_type, source
            FROM processed_equity_bar_1d
            WHERE factor_type = ?
        """
        params: list[Any] = [factor_type]
        if start:
            sql += " AND trade_date >= ?"
            params.append(start[:10])
        if end:
            sql += " AND trade_date <= ?"
            params.append(end[:10])
        if symbols:
            sql += f" AND symbol IN ({_ph(len(symbols))})"
            params.extend(symbols)
        sql += " ORDER BY symbol, trade_date"
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def load_processed_index(
        self,
        *,
        start: str | None,
        end: str | None,
        index_symbols: list[str],
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT index_symbol, trade_date, open, high, low, close, ret_1d, source
            FROM processed_index_bar_1d
            WHERE 1=1
        """
        params: list[Any] = []
        if start:
            sql += " AND trade_date >= ?"
            params.append(start[:10])
        if end:
            sql += " AND trade_date <= ?"
            params.append(end[:10])
        if index_symbols:
            sql += f" AND index_symbol IN ({_ph(len(index_symbols))})"
            params.extend(index_symbols)
        sql += " ORDER BY index_symbol, trade_date"
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def load_open_calendar_dates(
        self, *, start: str | None, end: str | None, exchange: str = "SSE"
    ) -> set[str]:
        sql = """
            SELECT DISTINCT trade_date
            FROM raw_trade_calendar
            WHERE exchange = ? AND is_open = 1
        """
        params: list[Any] = [exchange]
        if start:
            sql += " AND trade_date >= ?"
            params.append(start[:10])
        if end:
            sql += " AND trade_date <= ?"
            params.append(end[:10])
        with get_conn() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return {str(r["trade_date"])[:10] for r in rows}

    def create_run(
        self,
        *,
        dq_run_id: str,
        scope: str,
        start: str | None,
        end: str | None,
        factor_type: str,
        job_id: str | None,
        meta: dict[str, Any],
        created_at: str,
    ) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO dq_run (
                    dq_run_id, scope, status, start_date, end_date, factor_type,
                    job_id, meta_json, created_at
                ) VALUES (?, ?, 'created', ?, ?, ?, ?, ?, ?)
                """,
                (
                    dq_run_id,
                    scope,
                    start,
                    end,
                    factor_type,
                    job_id,
                    json.dumps(meta, ensure_ascii=False),
                    created_at,
                ),
            )

    def write_results(
        self,
        *,
        dq_run_id: str,
        outcomes: list[Any],
        checked_at: str,
    ) -> None:
        with get_conn() as conn:
            for o in outcomes:
                conn.execute(
                    """
                    INSERT INTO dq_result (
                        dq_run_id, rule_code, severity, status, message,
                        detail_json, checked_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(dq_run_id, rule_code) DO UPDATE SET
                        severity=excluded.severity,
                        status=excluded.status,
                        message=excluded.message,
                        detail_json=excluded.detail_json,
                        checked_at=excluded.checked_at
                    """,
                    (
                        dq_run_id,
                        o.rule_code,
                        o.severity,
                        o.status,
                        o.message,
                        json.dumps(o.detail, ensure_ascii=False),
                        checked_at,
                    ),
                )

    def finish_run(
        self,
        *,
        dq_run_id: str,
        status: str,
        summary: dict[str, Any],
        finished_at: str,
    ) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE dq_run
                SET status = ?, summary_json = ?, finished_at = ?
                WHERE dq_run_id = ?
                """,
                (
                    status,
                    json.dumps(summary, ensure_ascii=False),
                    finished_at,
                    dq_run_id,
                ),
            )

    def upsert_gate(
        self,
        *,
        scope: str,
        start: str,
        end: str,
        factor_type: str,
        status: str,
        dq_run_id: str,
        updated_at: str,
    ) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO dq_gate (
                    scope, start_date, end_date, factor_type, status, dq_run_id, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(scope, start_date, end_date, factor_type) DO UPDATE SET
                    status=excluded.status,
                    dq_run_id=excluded.dq_run_id,
                    updated_at=excluded.updated_at
                """,
                (scope, start, end, factor_type, status, dq_run_id, updated_at),
            )

    def latest_gate(
        self,
        *,
        scope: str,
        start: str,
        end: str,
        factor_type: str,
    ) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT scope, start_date, end_date, factor_type, status, dq_run_id, updated_at
                FROM dq_gate
                WHERE scope=? AND start_date=? AND end_date=? AND factor_type=?
                """,
                (scope, start, end, factor_type),
            ).fetchone()
        return dict(row) if row else None
