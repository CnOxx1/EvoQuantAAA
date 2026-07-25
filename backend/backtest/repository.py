from __future__ import annotations

import json
from typing import Any

from backtest.models import CostParams
from shared.db import get_conn


def _ph(n: int) -> str:
    return ",".join("?" * n)


class BacktestRepository:
    def load_cost(self, version: str) -> CostParams:
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
        return CostParams(
            version=str(row["version"]),
            commission_rate=float(row["commission_rate"]),
            min_commission=float(row["min_commission"]),
            stamp_tax_rate=float(row["stamp_tax_rate"]),
            slippage_rate=float(row["slippage_rate"]),
            lot_size=int(row["lot_size"] or 100),
        )

    def require_dq_passed(
        self, *, start: str, end: str, factor_type: str
    ) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT status, dq_run_id FROM dq_gate
                WHERE scope='CORE' AND start_date=? AND end_date=? AND factor_type=?
                """,
                (start, end, factor_type),
            ).fetchone()
        return dict(row) if row else None

    def load_universe_symbols(
        self, *, universe_code: str, as_of: str, as_of_end: str | None = None
    ) -> tuple[str | None, list[str]]:
        """点时：优先 as_of 当日或之前最近快照；若无则（样本期）允许 <= as_of_end。"""
        with get_conn() as conn:
            head = conn.execute(
                """
                SELECT universe_snapshot_id, as_of_date FROM universe_snapshot
                WHERE universe_code=? AND as_of_date<=? AND status='committed'
                ORDER BY as_of_date DESC LIMIT 1
                """,
                (universe_code, as_of),
            ).fetchone()
            if not head and as_of_end:
                head = conn.execute(
                    """
                    SELECT universe_snapshot_id, as_of_date FROM universe_snapshot
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

    def load_equity_bars(
        self,
        *,
        start: str,
        end: str,
        symbols: list[str],
        factor_type: str,
    ) -> list[dict[str, Any]]:
        if not symbols:
            return []
        sql = f"""
            SELECT symbol, trade_date, adj_open, adj_close, close,
                   can_buy, can_sell, is_suspended, is_limit_up, is_limit_down
            FROM processed_equity_bar_1d
            WHERE factor_type=? AND trade_date>=? AND trade_date<=?
              AND symbol IN ({_ph(len(symbols))})
            ORDER BY trade_date, symbol
        """
        params: list[Any] = [factor_type, start, end, *symbols]
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def load_index_bars(
        self, *, start: str, end: str, index_symbol: str
    ) -> list[dict[str, Any]]:
        with get_conn() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT index_symbol, trade_date, close, ret_1d
                    FROM processed_index_bar_1d
                    WHERE index_symbol=? AND trade_date>=? AND trade_date<=?
                    ORDER BY trade_date
                    """,
                    (index_symbol, start, end),
                ).fetchall()
            ]

    def load_research_factor_values(
        self,
        *,
        factor_code: str,
        universe_code: str,
        start: str,
        end: str,
        symbols: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """只读 research_factor_value（经库；不 import research_lab）。"""
        if symbols is not None and not symbols:
            return []
        if symbols:
            sql = f"""
                SELECT symbol, trade_date, value
                FROM research_factor_value
                WHERE factor_code=? AND universe_code=?
                  AND trade_date>=? AND trade_date<=?
                  AND symbol IN ({_ph(len(symbols))})
                ORDER BY trade_date, symbol
            """
            params: list[Any] = [factor_code, universe_code, start, end, *symbols]
        else:
            sql = """
                SELECT symbol, trade_date, value
                FROM research_factor_value
                WHERE factor_code=? AND universe_code=?
                  AND trade_date>=? AND trade_date<=?
                ORDER BY trade_date, symbol
            """
            params = [factor_code, universe_code, start, end]
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def create_run(self, row: dict[str, Any]) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO backtest_run (
                    run_id, strategy_code, status, start_date, end_date,
                    universe_code, universe_snapshot_id, factor_type, cost_version,
                    benchmark_index, initial_cash, dq_required, job_id, meta_json,
                    created_at
                ) VALUES (?, ?, 'running', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["run_id"],
                    row["strategy_code"],
                    row["start_date"],
                    row["end_date"],
                    row.get("universe_code"),
                    row.get("universe_snapshot_id"),
                    row["factor_type"],
                    row["cost_version"],
                    row.get("benchmark_index"),
                    row["initial_cash"],
                    row["dq_required"],
                    row.get("job_id"),
                    json.dumps(row.get("meta") or {}, ensure_ascii=False),
                    row["created_at"],
                ),
            )

    def finish_run(self, *, run_id: str, status: str, stats: dict[str, Any], finished_at: str) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE backtest_run SET
                    status=?,
                    final_nav=?,
                    total_return=?,
                    benchmark_return=?,
                    max_drawdown=?,
                    trade_count=?,
                    meta_json=COALESCE(?, meta_json),
                    error_message=?,
                    finished_at=?
                WHERE run_id=?
                """,
                (
                    status,
                    stats.get("final_nav"),
                    stats.get("total_return"),
                    stats.get("benchmark_return"),
                    stats.get("max_drawdown"),
                    stats.get("trade_count"),
                    json.dumps(stats.get("meta"), ensure_ascii=False)
                    if stats.get("meta") is not None
                    else None,
                    stats.get("error_message"),
                    finished_at,
                    run_id,
                ),
            )

    def write_nav(self, run_id: str, rows: list[dict[str, Any]]) -> None:
        with get_conn() as conn:
            for r in rows:
                conn.execute(
                    """
                    INSERT INTO backtest_nav (
                        run_id, trade_date, nav, cash, market_value, benchmark_nav
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(run_id, trade_date) DO UPDATE SET
                        nav=excluded.nav,
                        cash=excluded.cash,
                        market_value=excluded.market_value,
                        benchmark_nav=excluded.benchmark_nav
                    """,
                    (
                        run_id,
                        r["trade_date"],
                        r["nav"],
                        r["cash"],
                        r["market_value"],
                        r.get("benchmark_nav"),
                    ),
                )

    def write_trades(self, run_id: str, rows: list[dict[str, Any]]) -> None:
        with get_conn() as conn:
            conn.execute("DELETE FROM backtest_trade WHERE run_id=?", (run_id,))
            for r in rows:
                conn.execute(
                    """
                    INSERT INTO backtest_trade (
                        run_id, trade_date, symbol, side, shares, price, amount, cost, reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        r["trade_date"],
                        r["symbol"],
                        r["side"],
                        r["shares"],
                        r["price"],
                        r["amount"],
                        r["cost"],
                        r.get("reason"),
                    ),
                )
