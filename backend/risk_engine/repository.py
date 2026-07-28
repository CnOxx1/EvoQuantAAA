from __future__ import annotations

import json
from typing import Any

from shared.db import get_conn
from risk_engine.models import RiskLimits


class RiskRepository:
    def load_limits(self, version: str) -> RiskLimits:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT version, max_single_weight, max_names, max_gross_exposure, min_names,
                       max_industry_weight, max_adv_participation, adv_lookback_days,
                       industry_standard
                FROM risk_limits WHERE version=?
                """,
                (version,),
            ).fetchone()
        if not row:
            raise RuntimeError(f"risk_limits 不存在: {version}")
        d = dict(row)
        return RiskLimits(
            version=str(d["version"]),
            max_single_weight=float(d["max_single_weight"]),
            max_names=int(d["max_names"]),
            max_gross_exposure=float(d["max_gross_exposure"]),
            min_names=int(d["min_names"] or 1),
            max_industry_weight=(
                float(d["max_industry_weight"])
                if d.get("max_industry_weight") is not None
                else None
            ),
            max_adv_participation=(
                float(d["max_adv_participation"])
                if d.get("max_adv_participation") is not None
                else None
            ),
            adv_lookback_days=int(d.get("adv_lookback_days") or 20),
            industry_standard=str(d.get("industry_standard") or "SW2021"),
        )

    def load_adv_map(
        self,
        *,
        symbols: list[str],
        as_of: str,
        lookback_days: int = 20,
        factor_type: str = "qfq",
    ) -> dict[str, float]:
        """as_of 及之前 lookback 个交易日的平均成交额。"""
        if not symbols:
            return {}
        lookback = max(1, int(lookback_days))
        with get_conn() as conn:
            # 取 as_of 及之前的交易日序列
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
            placeholders = ",".join("?" * len(symbols))
            date_ph = ",".join("?" * len(dates))
            rows = conn.execute(
                f"""
                SELECT symbol, AVG(amount) AS adv
                FROM processed_equity_bar_1d
                WHERE factor_type=?
                  AND trade_date IN ({date_ph})
                  AND symbol IN ({placeholders})
                  AND amount IS NOT NULL AND amount > 0
                GROUP BY symbol
                """,
                (factor_type, *dates, *symbols),
            ).fetchall()
        return {str(r["symbol"]): float(r["adv"]) for r in rows if r["adv"] is not None}

    def load_industry_map(
        self,
        *,
        symbols: list[str],
        as_of: str,
        standard: str = "SW2021",
        universe_code: str | None = None,
    ) -> dict[str, str]:
        """优先 universe 快照成员行业；否则 raw_industry_class 点时。"""
        out: dict[str, str] = {}
        if not symbols:
            return out
        placeholders = ",".join("?" * len(symbols))
        with get_conn() as conn:
            if universe_code:
                snap = conn.execute(
                    """
                    SELECT universe_snapshot_id FROM universe_snapshot
                    WHERE universe_code=? AND as_of_date<=? AND status='committed'
                    ORDER BY as_of_date DESC
                    LIMIT 1
                    """,
                    (universe_code, as_of[:10]),
                ).fetchone()
                if snap:
                    rows = conn.execute(
                        f"""
                        SELECT symbol, industry_code FROM universe_snapshot_member
                        WHERE universe_snapshot_id=?
                          AND symbol IN ({placeholders})
                          AND industry_code IS NOT NULL AND industry_code <> ''
                        """,
                        (str(snap["universe_snapshot_id"]), *symbols),
                    ).fetchall()
                    for r in rows:
                        out[str(r["symbol"])] = str(r["industry_code"])
            missing = [s for s in symbols if s not in out]
            if missing:
                mph = ",".join("?" * len(missing))
                rows = conn.execute(
                    f"""
                    SELECT DISTINCT ON (symbol) symbol, industry_code
                    FROM raw_industry_class
                    WHERE standard=? AND effective_date<=?
                      AND symbol IN ({mph})
                      AND industry_code IS NOT NULL AND industry_code <> ''
                    ORDER BY symbol, effective_date DESC
                    """,
                    (standard, as_of[:10], *missing),
                ).fetchall()
                for r in rows:
                    out[str(r["symbol"])] = str(r["industry_code"])
        return out

    def load_lot_size(self, cost_version: str) -> int:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT lot_size FROM cost_params WHERE version=?",
                (cost_version,),
            ).fetchone()
        if not row:
            return 100
        return int(row["lot_size"] or 100)

    def get_kill_switch(self, scope_key: str) -> dict[str, Any]:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM kill_switch WHERE scope_key=?",
                (scope_key,),
            ).fetchone()
        if not row:
            return {
                "scope_key": scope_key,
                "is_on": 0,
                "reason": None,
                "actor": None,
                "updated_at": None,
            }
        return dict(row)

    def is_kill_on(self, *, account_id: str) -> tuple[bool, list[str]]:
        """GLOBAL 或账户任一开启即 True；返回 (on, scopes)。"""
        scopes: list[str] = []
        global_sw = self.get_kill_switch("GLOBAL")
        if int(global_sw.get("is_on") or 0) == 1:
            scopes.append("GLOBAL")
        acct = self.get_kill_switch(account_id)
        if int(acct.get("is_on") or 0) == 1:
            scopes.append(account_id)
        return bool(scopes), scopes

    def set_kill_switch(
        self,
        *,
        scope_key: str,
        is_on: bool,
        reason: str | None,
        actor: str,
        updated_at: str,
    ) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO kill_switch (scope_key, is_on, reason, actor, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (scope_key) DO UPDATE SET
                    is_on=EXCLUDED.is_on,
                    reason=EXCLUDED.reason,
                    actor=EXCLUDED.actor,
                    updated_at=EXCLUDED.updated_at
                """,
                (scope_key, 1 if is_on else 0, reason, actor, updated_at),
            )

    def list_kill_switches(self) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM kill_switch ORDER BY scope_key"
            ).fetchall()
        return [dict(r) for r in rows]

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

    def list_draft_portfolios(
        self, *, as_of: str | None = None, account_id: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM portfolio_target WHERE status='draft'"
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

    def list_account_active_portfolios(
        self,
        *,
        account_id: str,
        as_of: str,
        exclude_portfolio_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """同账户同日 draft/approved/executed，用于合并敞口。"""
        if not as_of:
            return []
        sql = """
            SELECT * FROM portfolio_target
            WHERE account_id=? AND as_of_date=?
              AND status IN ('draft', 'approved', 'executed')
        """
        params: list[Any] = [account_id, as_of[:10]]
        if exclude_portfolio_id:
            sql += " AND portfolio_id<>?"
            params.append(exclude_portfolio_id)
        sql += " ORDER BY created_at"
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

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

    def insert_decision(self, row: dict[str, Any]) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO risk_decision (
                    decision_id, portfolio_id, account_id, as_of_date, status,
                    kill_switch_on, breach_count, breaches_json, meta_json,
                    actor, job_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["decision_id"],
                    row["portfolio_id"],
                    row["account_id"],
                    row.get("as_of_date"),
                    row["status"],
                    row["kill_switch_on"],
                    row["breach_count"],
                    json.dumps(row.get("breaches") or [], ensure_ascii=False),
                    json.dumps(row.get("meta") or {}, ensure_ascii=False),
                    row.get("actor"),
                    row.get("job_id"),
                    row["created_at"],
                ),
            )
            conn.execute(
                """
                UPDATE portfolio_target
                SET status=?
                WHERE portfolio_id=?
                """,
                (row["status"], row["portfolio_id"]),
            )

    def get_decision(self, decision_id: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM risk_decision WHERE decision_id=?",
                (decision_id,),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["breaches"] = json.loads(str(d.get("breaches_json") or "[]"))
        except json.JSONDecodeError:
            d["breaches"] = []
        try:
            d["meta"] = json.loads(str(d.get("meta_json") or "{}"))
        except json.JSONDecodeError:
            d["meta"] = {}
        return d

    def list_decisions(
        self,
        *,
        portfolio_id: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM risk_decision WHERE 1=1"
        params: list[Any] = []
        if portfolio_id:
            sql += " AND portfolio_id=?"
            params.append(portfolio_id)
        if status:
            sql += " AND status=?"
            params.append(status)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(limit, 200)))
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]
