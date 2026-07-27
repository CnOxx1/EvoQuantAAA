from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from shared.db import get_conn


def _ph(n: int) -> str:
    return ",".join("?" * n)


def _lookback_start(start: str, calendar_days: int) -> str:
    d = date.fromisoformat(start[:10]) - timedelta(days=calendar_days)
    return d.isoformat()


class SignalProdRepository:
    def load_strategy(self, strategy_version: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM strategy_version WHERE strategy_version=?",
                (strategy_version,),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["params"] = json.loads(str(d.get("params_json") or "{}"))
        except json.JSONDecodeError:
            d["params"] = {}
        return d

    def list_runnable_versions(self) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM strategy_version
                WHERE status IN ('PAPER', 'LIVE')
                ORDER BY status DESC, strategy_code
                """
            ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            d = dict(row)
            try:
                d["params"] = json.loads(str(d.get("params_json") or "{}"))
            except json.JSONDecodeError:
                d["params"] = {}
            out.append(d)
        return out

    def require_dq_passed(
        self, *, start: str, end: str, factor_type: str
    ) -> dict[str, Any] | None:
        """区间被某条已 passed 的 CORE gate 覆盖即可（适配日更 as_of 短窗）。"""
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT status, dq_run_id, start_date, end_date FROM dq_gate
                WHERE scope='CORE' AND factor_type=? AND status='passed'
                  AND start_date<=? AND end_date>=?
                ORDER BY end_date DESC, start_date ASC
                LIMIT 1
                """,
                (factor_type, start[:10], end[:10]),
            ).fetchone()
        return dict(row) if row else None

    def load_universe_symbols(
        self, *, universe_code: str, as_of: str, as_of_end: str | None = None
    ) -> tuple[str | None, list[str]]:
        with get_conn() as conn:
            head = conn.execute(
                """
                SELECT universe_snapshot_id FROM universe_snapshot
                WHERE universe_code=? AND as_of_date<=? AND status='committed'
                ORDER BY as_of_date DESC LIMIT 1
                """,
                (universe_code, as_of),
            ).fetchone()
            if not head and as_of_end:
                head = conn.execute(
                    """
                    SELECT universe_snapshot_id FROM universe_snapshot
                    WHERE universe_code=? AND as_of_date<=? AND status='committed'
                    ORDER BY as_of_date DESC LIMIT 1
                    """,
                    (universe_code, as_of_end),
                ).fetchone()
            if not head:
                return None, []
            sid = str(head["universe_snapshot_id"])
            rows = conn.execute(
                """
                SELECT symbol FROM universe_snapshot_member
                WHERE universe_snapshot_id=? AND is_eligible=1
                ORDER BY symbol
                """,
                (sid,),
            ).fetchall()
        return sid, [str(r["symbol"]) for r in rows]

    def load_trade_dates_with_bars(
        self,
        *,
        start: str,
        end: str,
        symbols: list[str],
        factor_type: str,
    ) -> tuple[list[str], dict[str, set[str]]]:
        if not symbols:
            return [], {}
        sql = f"""
            SELECT DISTINCT trade_date, symbol
            FROM processed_equity_bar_1d
            WHERE factor_type=? AND trade_date>=? AND trade_date<=?
              AND symbol IN ({_ph(len(symbols))})
              AND adj_close IS NOT NULL
            ORDER BY trade_date, symbol
        """
        with get_conn() as conn:
            rows = conn.execute(
                sql, (factor_type, start[:10], end[:10], *symbols)
            ).fetchall()
        by_date: dict[str, set[str]] = {}
        for r in rows:
            d = str(r["trade_date"])[:10]
            by_date.setdefault(d, set()).add(str(r["symbol"]))
        return sorted(by_date.keys()), by_date

    def load_factor_values(
        self,
        *,
        factor_code: str,
        universe_code: str,
        start: str,
        end: str,
        symbols: list[str],
        lookback_calendar_days: int = 40,
    ) -> list[dict[str, Any]]:
        if not symbols:
            return []
        load_start = _lookback_start(start, lookback_calendar_days)
        sql = f"""
            SELECT symbol, trade_date, value
            FROM research_factor_value
            WHERE factor_code=? AND universe_code=?
              AND trade_date>=? AND trade_date<=?
              AND symbol IN ({_ph(len(symbols))})
            ORDER BY trade_date, symbol
        """
        with get_conn() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    sql,
                    (factor_code, universe_code, load_start, end[:10], *symbols),
                ).fetchall()
            ]

    def create_batch(self, row: dict[str, Any]) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO signal_batch (
                    signal_batch_id, strategy_version, status, start_date, end_date,
                    as_of_date, universe_code, universe_snapshot_id, row_count,
                    job_id, meta_json, error_message, created_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["signal_batch_id"],
                    row["strategy_version"],
                    row["status"],
                    row["start_date"],
                    row["end_date"],
                    row.get("as_of_date"),
                    row.get("universe_code"),
                    row.get("universe_snapshot_id"),
                    row.get("row_count"),
                    row.get("job_id"),
                    json.dumps(row.get("meta") or {}, ensure_ascii=False),
                    row.get("error_message"),
                    row["created_at"],
                    row.get("finished_at"),
                ),
            )

    def finish_batch(
        self,
        *,
        signal_batch_id: str,
        status: str,
        row_count: int,
        finished_at: str,
        error_message: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE signal_batch
                SET status=?, row_count=?, finished_at=?, error_message=?,
                    meta_json=COALESCE(?, meta_json)
                WHERE signal_batch_id=?
                """,
                (
                    status,
                    row_count,
                    finished_at,
                    error_message,
                    json.dumps(meta, ensure_ascii=False) if meta is not None else None,
                    signal_batch_id,
                ),
            )

    def upsert_weights(
        self,
        *,
        rows: list[dict[str, Any]],
        strategy_version: str,
        signal_batch_id: str,
        created_at: str,
    ) -> int:
        if not rows:
            return 0
        sql = """
            INSERT INTO signal_prod_weight (
                strategy_version, trade_date, symbol, weight,
                signal_value, signal_batch_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (strategy_version, trade_date, symbol) DO UPDATE SET
                weight=EXCLUDED.weight,
                signal_value=EXCLUDED.signal_value,
                signal_batch_id=EXCLUDED.signal_batch_id,
                created_at=EXCLUDED.created_at
        """
        params = [
            (
                strategy_version,
                str(r["trade_date"])[:10],
                str(r["symbol"]),
                float(r["weight"]),
                None if r.get("signal_value") is None else float(r["signal_value"]),
                signal_batch_id,
                created_at,
            )
            for r in rows
        ]
        chunk = 500
        with get_conn() as conn:
            for i in range(0, len(params), chunk):
                conn.executemany(sql, params[i : i + chunk])
        return len(params)

    def list_batches(
        self, *, strategy_version: str | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM signal_batch WHERE 1=1"
        params: list[Any] = []
        if strategy_version:
            sql += " AND strategy_version=?"
            params.append(strategy_version)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(limit, 200)))
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]
