from __future__ import annotations

import json
from typing import Any

from shared.db import get_conn


def _ph(n: int) -> str:
    return ",".join("?" * n)


class PortfolioRepository:
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

    def list_runnable_versions(self, *, statuses: set[str] | None = None) -> list[dict[str, Any]]:
        want = statuses or {"LIVE", "PAPER"}
        placeholders = _ph(len(want))
        with get_conn() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM strategy_version
                WHERE status IN ({placeholders})
                ORDER BY status DESC, strategy_code
                """,
                tuple(sorted(want)),
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

    def load_lot_size(self, cost_version: str) -> int:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT lot_size FROM cost_params WHERE version=?",
                (cost_version,),
            ).fetchone()
        if not row:
            raise RuntimeError(f"cost_params 不存在: {cost_version}")
        return int(row["lot_size"] or 100)

    def load_latest_signal_weights(
        self,
        *,
        strategy_version: str,
        as_of: str,
        signal_batch_id: str | None = None,
    ) -> tuple[str | None, str | None, list[dict[str, Any]]]:
        """
        返回 (signal_trade_date, signal_batch_id, rows)。
        仅消费 status='committed' 的 signal_batch。
        """
        with get_conn() as conn:
            if signal_batch_id:
                batch = conn.execute(
                    """
                    SELECT signal_batch_id, status FROM signal_batch
                    WHERE signal_batch_id=?
                    """,
                    (signal_batch_id,),
                ).fetchone()
                if not batch or str(batch["status"]) != "committed":
                    return None, signal_batch_id, []
                rows = conn.execute(
                    """
                    SELECT trade_date, symbol, weight, signal_value, signal_batch_id
                    FROM signal_prod_weight
                    WHERE strategy_version=? AND signal_batch_id=?
                      AND trade_date<=?
                    ORDER BY trade_date DESC, symbol
                    """,
                    (strategy_version, signal_batch_id, as_of[:10]),
                ).fetchall()
                if not rows:
                    return None, signal_batch_id, []
                latest = str(rows[0]["trade_date"])[:10]
                picked = [dict(r) for r in rows if str(r["trade_date"])[:10] == latest]
                bid = str(picked[0].get("signal_batch_id") or signal_batch_id)
                return latest, bid, picked

            head = conn.execute(
                """
                SELECT w.trade_date, w.signal_batch_id
                FROM signal_prod_weight w
                JOIN signal_batch b ON b.signal_batch_id=w.signal_batch_id
                WHERE w.strategy_version=? AND w.trade_date<=?
                  AND b.status='committed'
                ORDER BY w.trade_date DESC
                LIMIT 1
                """,
                (strategy_version, as_of[:10]),
            ).fetchone()
            if not head:
                return None, None, []
            latest = str(head["trade_date"])[:10]
            bid = str(head["signal_batch_id"]) if head.get("signal_batch_id") else None
            rows = conn.execute(
                """
                SELECT trade_date, symbol, weight, signal_value, signal_batch_id
                FROM signal_prod_weight
                WHERE strategy_version=? AND trade_date=?
                  AND signal_batch_id=?
                ORDER BY symbol
                """,
                (strategy_version, latest, bid),
            ).fetchall()
        return latest, bid, [dict(r) for r in rows]

    def find_active_target(
        self,
        *,
        strategy_version: str,
        as_of: str,
        account_id: str,
    ) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM portfolio_target
                WHERE strategy_version=? AND as_of_date=? AND account_id=?
                  AND status IN ('running', 'draft', 'approved', 'executed')
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (strategy_version, as_of[:10], account_id),
            ).fetchone()
        return dict(row) if row else None

    def estimate_account_nav(
        self,
        *,
        account_id: str,
        as_of: str,
        factor_type: str = "qfq",
    ) -> float:
        """现金 + 持仓市值（点时最近未复权 close）；无账本则回退 opening_cash。"""
        with get_conn() as conn:
            cash_row = conn.execute(
                """
                SELECT qty FROM ledger_balance
                WHERE account_id=? AND asset_type='CASH' AND symbol=''
                """,
                (account_id,),
            ).fetchone()
            acct = conn.execute(
                "SELECT opening_cash FROM ledger_account WHERE account_id=?",
                (account_id,),
            ).fetchone()
            pos_rows = conn.execute(
                """
                SELECT symbol, qty FROM ledger_balance
                WHERE account_id=? AND asset_type='POSITION' AND qty<>0
                """,
                (account_id,),
            ).fetchall()
        if cash_row:
            cash = float(cash_row["qty"])
        elif acct:
            cash = float(acct["opening_cash"])
        else:
            cash = 0.0
        symbols = [str(r["symbol"]) for r in pos_rows]
        if not symbols:
            return cash
        bars = self.load_bars_as_of(
            as_of=as_of, symbols=symbols, factor_type=factor_type
        )
        equity = cash
        for r in pos_rows:
            sym = str(r["symbol"])
            b = bars.get(sym) or {}
            px = b.get("close") if b.get("close") is not None else b.get("adj_close")
            if px is None:
                continue
            equity += float(r["qty"]) * float(px)
        return equity

    def load_capital_weights(
        self, *, account_id: str, strategy_versions: list[str]
    ) -> dict[str, float]:
        """返回 strategy_version → capital_weight；缺省等权。"""
        if not strategy_versions:
            return {}
        with get_conn() as conn:
            rows = conn.execute(
                f"""
                SELECT strategy_version, capital_weight
                FROM strategy_capital_alloc
                WHERE account_id=? AND strategy_version IN ({_ph(len(strategy_versions))})
                """,
                (account_id, *strategy_versions),
            ).fetchall()
        found = {str(r["strategy_version"]): float(r["capital_weight"]) for r in rows}
        missing = [v for v in strategy_versions if v not in found]
        if missing:
            eq = 1.0 / len(strategy_versions)
            for v in strategy_versions:
                found.setdefault(v, eq)
        # 归一到合计 1（若登记权重和>0）
        total = sum(max(0.0, w) for w in found.values())
        if total <= 0:
            eq = 1.0 / len(strategy_versions)
            return {v: eq for v in strategy_versions}
        return {v: max(0.0, found[v]) / total for v in strategy_versions}

    def load_bars_as_of(
        self,
        *,
        as_of: str,
        symbols: list[str],
        factor_type: str = "qfq",
    ) -> dict[str, dict[str, Any]]:
        """点时：每个 symbol 取 trade_date<=as_of 最近一根 processed 日线。"""
        if not symbols:
            return {}
        # 点时窗口：as_of 前回看，再按 symbol 取最新一根。
        from datetime import date, timedelta

        start = (date.fromisoformat(as_of[:10]) - timedelta(days=60)).isoformat()
        sql = f"""
            SELECT symbol, trade_date, close, adj_close, can_buy, can_sell
            FROM processed_equity_bar_1d
            WHERE factor_type=? AND trade_date>=? AND trade_date<=?
              AND symbol IN ({_ph(len(symbols))})
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

    def create_target(self, row: dict[str, Any]) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO portfolio_target (
                    portfolio_id, strategy_version, signal_batch_id, signal_trade_date,
                    as_of_date, account_id, status, nav, cost_version, universe_code,
                    row_count, invested_value, cash_residual, job_id, meta_json,
                    error_message, created_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["portfolio_id"],
                    row["strategy_version"],
                    row.get("signal_batch_id"),
                    row.get("signal_trade_date"),
                    row["as_of_date"],
                    row["account_id"],
                    row["status"],
                    row["nav"],
                    row["cost_version"],
                    row.get("universe_code"),
                    row.get("row_count"),
                    row.get("invested_value"),
                    row.get("cash_residual"),
                    row.get("job_id"),
                    json.dumps(row.get("meta") or {}, ensure_ascii=False),
                    row.get("error_message"),
                    row["created_at"],
                    row.get("finished_at"),
                ),
            )

    def finish_target(
        self,
        *,
        portfolio_id: str,
        status: str,
        row_count: int,
        invested_value: float,
        cash_residual: float,
        finished_at: str,
        error_message: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE portfolio_target
                SET status=?, row_count=?, invested_value=?, cash_residual=?,
                    finished_at=?, error_message=?,
                    meta_json=COALESCE(?, meta_json)
                WHERE portfolio_id=?
                """,
                (
                    status,
                    row_count,
                    invested_value,
                    cash_residual,
                    finished_at,
                    error_message,
                    json.dumps(meta, ensure_ascii=False) if meta is not None else None,
                    portfolio_id,
                ),
            )

    def upsert_positions(
        self,
        *,
        portfolio_id: str,
        rows: list[dict[str, Any]],
        created_at: str,
    ) -> int:
        if not rows:
            return 0
        sql = """
            INSERT INTO portfolio_target_position (
                portfolio_id, symbol, target_weight, target_value, target_shares,
                price, signal_value, signal_weight, can_buy, can_sell, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (portfolio_id, symbol) DO UPDATE SET
                target_weight=EXCLUDED.target_weight,
                target_value=EXCLUDED.target_value,
                target_shares=EXCLUDED.target_shares,
                price=EXCLUDED.price,
                signal_value=EXCLUDED.signal_value,
                signal_weight=EXCLUDED.signal_weight,
                can_buy=EXCLUDED.can_buy,
                can_sell=EXCLUDED.can_sell,
                status=EXCLUDED.status,
                created_at=EXCLUDED.created_at
        """
        params = [
            (
                portfolio_id,
                str(r["symbol"]),
                float(r["target_weight"]),
                float(r["target_value"]),
                float(r["target_shares"]),
                float(r["price"]),
                None if r.get("signal_value") is None else float(r["signal_value"]),
                None if r.get("signal_weight") is None else float(r["signal_weight"]),
                int(r.get("can_buy") if r.get("can_buy") is not None else 1),
                int(r.get("can_sell") if r.get("can_sell") is not None else 1),
                str(r.get("status") or "draft"),
                created_at,
            )
            for r in rows
        ]
        with get_conn() as conn:
            conn.executemany(sql, params)
        return len(params)

    def get_target(self, portfolio_id: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM portfolio_target WHERE portfolio_id=?",
                (portfolio_id,),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["meta"] = json.loads(str(d.get("meta_json") or "{}"))
        except json.JSONDecodeError:
            d["meta"] = {}
        return d

    def list_positions(self, portfolio_id: str) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM portfolio_target_position
                WHERE portfolio_id=?
                ORDER BY target_weight DESC, symbol
                """,
                (portfolio_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def list_targets(
        self,
        *,
        strategy_version: str | None = None,
        account_id: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM portfolio_target WHERE 1=1"
        params: list[Any] = []
        if strategy_version:
            sql += " AND strategy_version=?"
            params.append(strategy_version)
        if account_id:
            sql += " AND account_id=?"
            params.append(account_id)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(limit, 200)))
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]
