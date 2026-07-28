from __future__ import annotations

import json
from typing import Any

from shared.db import get_conn


class GatewayRepository:
    def list_strategies(
        self, *, status: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM strategy_version WHERE 1=1"
        params: list[Any] = []
        if status:
            sql += " AND status=?"
            params.append(status)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(max(1, min(limit, 200)))
        with get_conn() as conn:
            rows = [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]
        for r in rows:
            try:
                r["params"] = json.loads(str(r.pop("params_json", None) or "{}"))
            except json.JSONDecodeError:
                r["params"] = {}
        return rows

    def get_strategy(self, strategy_version: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM strategy_version WHERE strategy_version=?",
                (strategy_version,),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["params"] = json.loads(str(d.pop("params_json", None) or "{}"))
        except json.JSONDecodeError:
            d["params"] = {}
        return d

    def list_portfolios(
        self,
        *,
        status: str | None = None,
        as_of: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM portfolio_target WHERE 1=1"
        params: list[Any] = []
        if status:
            sql += " AND status=?"
            params.append(status)
        if as_of:
            sql += " AND as_of_date=?"
            params.append(as_of[:10])
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(limit, 200)))
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def get_portfolio(self, portfolio_id: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            head = conn.execute(
                "SELECT * FROM portfolio_target WHERE portfolio_id=?",
                (portfolio_id,),
            ).fetchone()
            if not head:
                return None
            positions = conn.execute(
                """
                SELECT symbol, target_weight, target_shares, target_value, price, status
                FROM portfolio_target_position
                WHERE portfolio_id=?
                ORDER BY target_weight DESC, symbol
                """,
                (portfolio_id,),
            ).fetchall()
        d = dict(head)
        d["positions"] = [dict(p) for p in positions]
        return d

    def list_kill_switches(self) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM kill_switch ORDER BY scope_key"
            ).fetchall()
        return [dict(r) for r in rows]

    def list_risk_decisions(
        self, *, portfolio_id: str | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM risk_decision WHERE 1=1"
        params: list[Any] = []
        if portfolio_id:
            sql += " AND portfolio_id=?"
            params.append(portfolio_id)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(limit, 100)))
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def get_execution(self, execution_id: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            run = conn.execute(
                "SELECT * FROM execution_run WHERE execution_id=?",
                (execution_id,),
            ).fetchone()
            if not run:
                return None
            fills = conn.execute(
                """
                SELECT fill_id, symbol, side, qty, price, amount, commission, stamp_tax, trade_date
                FROM fill_event WHERE execution_id=?
                ORDER BY symbol
                """,
                (execution_id,),
            ).fetchall()
            orders = conn.execute(
                """
                SELECT event_id, order_id, symbol, side, qty, limit_price, status,
                       event_type, reason, created_at
                FROM order_event WHERE execution_id=?
                ORDER BY created_at, symbol
                """,
                (execution_id,),
            ).fetchall()
        d = dict(run)
        d["fills"] = [dict(f) for f in fills]
        d["orders"] = [dict(o) for o in orders]
        return d

    def list_executions(
        self,
        *,
        account_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM execution_run WHERE 1=1"
        params: list[Any] = []
        if account_id:
            sql += " AND account_id=?"
            params.append(account_id)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(limit, 200)))
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
        params.append(max(1, min(limit, 200)))
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def list_research_runs(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM research_run
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 200)),),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            try:
                d["meta"] = json.loads(str(d.get("meta_json") or "{}"))
            except json.JSONDecodeError:
                d["meta"] = {}
            out.append(d)
        return out

    def list_market_ranks(
        self,
        *,
        trade_date: str | None = None,
        rank_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT trade_date, rank_type, rank_no, symbol, name, metric_value,
                   close, pct_chg, volume, amount, turnover, source
            FROM raw_market_rank_1d WHERE 1=1
        """
        params: list[Any] = []
        if trade_date:
            sql += " AND trade_date=?"
            params.append(trade_date[:10])
        else:
            sql += """
                AND trade_date=(
                    SELECT MAX(trade_date) FROM raw_market_rank_1d
                )
            """
        if rank_type:
            sql += " AND rank_type=?"
            params.append(rank_type)
        sql += " ORDER BY rank_type, rank_no ASC LIMIT ?"
        params.append(max(1, min(limit, 500)))
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def list_rank_meta(self) -> dict[str, Any]:
        with get_conn() as conn:
            dates = [
                str(r["d"])
                for r in conn.execute(
                    """
                    SELECT DISTINCT trade_date AS d FROM raw_market_rank_1d
                    ORDER BY trade_date DESC LIMIT 30
                    """
                ).fetchall()
            ]
            types = [
                str(r["rank_type"])
                for r in conn.execute(
                    """
                    SELECT DISTINCT rank_type FROM raw_market_rank_1d
                    ORDER BY rank_type
                    """
                ).fetchall()
            ]
        return {"trade_dates": dates, "rank_types": types}

    def list_abnormal_moves(
        self,
        *,
        trade_date: str | None = None,
        change_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT trade_date, event_time, symbol, name, change_type,
                   related_info, source_event_id, source
            FROM raw_abnormal_move WHERE 1=1
        """
        params: list[Any] = []
        if trade_date:
            sql += " AND trade_date=?"
            params.append(trade_date[:10])
        else:
            sql += """
                AND trade_date=(
                    SELECT MAX(trade_date) FROM raw_abnormal_move
                )
            """
        if change_type:
            sql += " AND change_type=?"
            params.append(change_type)
        sql += " ORDER BY event_time DESC NULLS LAST, symbol LIMIT ?"
        params.append(max(1, min(limit, 500)))
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def list_news(
        self,
        *,
        channel: str | None = None,
        symbol: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT source_news_id, symbol, title, summary, publish_time, url,
                   media_source, channel, source, content_type, extra_json
            FROM raw_news_media WHERE 1=1
        """
        params: list[Any] = []
        if channel:
            sql += " AND channel=?"
            params.append(channel)
        if symbol:
            sql += " AND symbol=?"
            params.append(symbol)
        sql += " ORDER BY publish_time DESC LIMIT ?"
        params.append(max(1, min(limit, 200)))
        with get_conn() as conn:
            rows = [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]
        for r in rows:
            try:
                r["extra"] = json.loads(str(r.pop("extra_json", None) or "{}"))
            except json.JSONDecodeError:
                r["extra"] = {}
        return rows

    def list_dragon_tiger(
        self,
        *,
        trade_date: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT symbol, trade_date, reason, close, pct_chg, net_amount,
                   buy_amount, sell_amount, source_event_id, source
            FROM raw_dragon_tiger WHERE 1=1
        """
        params: list[Any] = []
        if trade_date:
            sql += " AND trade_date=?"
            params.append(trade_date[:10])
        else:
            sql += """
                AND trade_date=(
                    SELECT MAX(trade_date) FROM raw_dragon_tiger
                )
            """
        sql += " ORDER BY ABS(COALESCE(net_amount,0)) DESC, symbol LIMIT ?"
        params.append(max(1, min(limit, 300)))
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def get_ledger_account(self, account_id: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            acct = conn.execute(
                "SELECT * FROM ledger_account WHERE account_id=?",
                (account_id,),
            ).fetchone()
            if not acct:
                return None
            cash = conn.execute(
                """
                SELECT qty FROM ledger_balance
                WHERE account_id=? AND asset_type='CASH' AND symbol=''
                """,
                (account_id,),
            ).fetchone()
            positions = conn.execute(
                """
                SELECT symbol, qty FROM ledger_balance
                WHERE account_id=? AND asset_type='POSITION' AND qty<>0
                ORDER BY symbol
                """,
                (account_id,),
            ).fetchall()
        d = dict(acct)
        d["cash"] = float(cash["qty"]) if cash else float(d.get("opening_cash") or 0)
        d["positions"] = [dict(p) for p in positions]
        return d

    def list_alerts(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM ops_alert
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 100)),),
            ).fetchall()
        return [dict(r) for r in rows]

    def insert_audit(self, row: dict[str, Any]) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO api_audit_log (
                    audit_id, actor, method, path, status_code,
                    request_json, result_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["audit_id"],
                    row.get("actor"),
                    row["method"],
                    row["path"],
                    row.get("status_code"),
                    json.dumps(row.get("request") or {}, ensure_ascii=False),
                    json.dumps(row.get("result") or {}, ensure_ascii=False),
                    row["created_at"],
                ),
            )
