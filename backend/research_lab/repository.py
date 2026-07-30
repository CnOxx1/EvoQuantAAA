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


class ResearchRepository:
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
        lookback_calendar_days: int = 0,
    ) -> list[dict[str, Any]]:
        if not symbols:
            return []
        load_start = (
            _lookback_start(start, lookback_calendar_days)
            if lookback_calendar_days > 0
            else start
        )
        sql = f"""
            SELECT symbol, trade_date, adj_close, close, amount, ret_1d
            FROM processed_equity_bar_1d
            WHERE factor_type=? AND trade_date>=? AND trade_date<=?
              AND symbol IN ({_ph(len(symbols))})
            ORDER BY symbol, trade_date
        """
        params: list[Any] = [factor_type, load_start, end, *symbols]
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def load_valuations(
        self, *, start: str, end: str, symbols: list[str]
    ) -> list[dict[str, Any]]:
        if not symbols:
            return []
        sql = f"""
            SELECT symbol, trade_date, pe_ttm, pb
            FROM raw_valuation_1d
            WHERE trade_date>=? AND trade_date<=?
              AND symbol IN ({_ph(len(symbols))})
            ORDER BY trade_date, symbol
        """
        with get_conn() as conn:
            return [
                dict(r)
                for r in conn.execute(sql, (start, end, *symbols)).fetchall()
            ]

    def load_stock_flows(
        self,
        *,
        start: str,
        end: str,
        symbols: list[str],
        lookback_calendar_days: int = 14,
    ) -> list[dict[str, Any]]:
        if not symbols:
            return []
        load_start = _lookback_start(start, lookback_calendar_days)
        sql = f"""
            SELECT scope, trade_date, flow_type, net_amount, source
            FROM raw_money_flow
            WHERE trade_date>=? AND trade_date<=?
              AND flow_type IN ('STOCK_FLOW', 'STOCK_NORTHBOUND')
              AND scope IN ({_ph(len(symbols))})
            ORDER BY scope, trade_date
        """
        with get_conn() as conn:
            return [
                dict(r)
                for r in conn.execute(sql, (load_start, end, *symbols)).fetchall()
            ]

    def load_tech_indicators(
        self,
        *,
        start: str,
        end: str,
        symbols: list[str],
        factor_type: str,
        indicator_codes: list[str],
    ) -> list[dict[str, Any]]:
        """只读 processed_tech_indicator_1d（经库；不 import data_process）。"""
        if not symbols or not indicator_codes:
            return []
        sql = f"""
            SELECT symbol, trade_date, indicator_code, value, category
            FROM processed_tech_indicator_1d
            WHERE factor_type=? AND trade_date>=? AND trade_date<=?
              AND symbol IN ({_ph(len(symbols))})
              AND indicator_code IN ({_ph(len(indicator_codes))})
            ORDER BY symbol, trade_date, indicator_code
        """
        params: list[Any] = [
            factor_type,
            start[:10],
            end[:10],
            *symbols,
            *indicator_codes,
        ]
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def create_run(self, row: dict[str, Any]) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO research_run (
                    run_id, factor_code, universe_code, start_date, end_date,
                    status, meta_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["run_id"],
                    row["factor_code"],
                    row["universe_code"],
                    row["start_date"],
                    row["end_date"],
                    row["status"],
                    json.dumps(row.get("meta") or {}, ensure_ascii=False),
                    row["created_at"],
                ),
            )

    def finish_run(
        self,
        *,
        run_id: str,
        status: str,
        meta: dict[str, Any] | None = None,
    ) -> None:
        with get_conn() as conn:
            if meta is not None:
                conn.execute(
                    """
                    UPDATE research_run
                    SET status=?, meta_json=?
                    WHERE run_id=?
                    """,
                    (status, json.dumps(meta, ensure_ascii=False), run_id),
                )
            else:
                conn.execute(
                    "UPDATE research_run SET status=? WHERE run_id=?",
                    (status, run_id),
                )

    def upsert_factor_values(
        self,
        *,
        rows: list[dict[str, Any]],
        factor_code: str,
        universe_code: str,
        run_id: str,
        created_at: str,
    ) -> int:
        if not rows:
            return 0
        sql = """
            INSERT INTO research_factor_value (
                factor_code, symbol, trade_date, value,
                universe_code, run_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (factor_code, symbol, trade_date, universe_code)
            DO UPDATE SET
                value=EXCLUDED.value,
                run_id=EXCLUDED.run_id,
                created_at=EXCLUDED.created_at
        """
        params = [
            (
                factor_code,
                str(r["symbol"]),
                str(r["trade_date"])[:10],
                None if r.get("value") is None else float(r["value"]),
                universe_code,
                run_id,
                created_at,
            )
            for r in rows
        ]
        chunk = 500
        with get_conn() as conn:
            for i in range(0, len(params), chunk):
                conn.executemany(sql, params[i : i + chunk])
        return len(params)

    def load_factor_values(
        self,
        *,
        factor_code: str,
        universe_code: str,
        start: str,
        end: str,
        symbols: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        if symbols is not None and not symbols:
            return []
        if symbols:
            sql = f"""
                SELECT factor_code, symbol, trade_date, value, universe_code, run_id
                FROM research_factor_value
                WHERE factor_code=? AND universe_code=?
                  AND trade_date>=? AND trade_date<=?
                  AND symbol IN ({_ph(len(symbols))})
                ORDER BY trade_date, symbol
            """
            params: list[Any] = [factor_code, universe_code, start, end, *symbols]
        else:
            sql = """
                SELECT factor_code, symbol, trade_date, value, universe_code, run_id
                FROM research_factor_value
                WHERE factor_code=? AND universe_code=?
                  AND trade_date>=? AND trade_date<=?
                ORDER BY trade_date, symbol
            """
            params = [factor_code, universe_code, start, end]
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def count_factor_values(
        self, *, factor_code: str, universe_code: str, start: str, end: str
    ) -> int:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS n FROM research_factor_value
                WHERE factor_code=? AND universe_code=?
                  AND trade_date>=? AND trade_date<=?
                """,
                (factor_code, universe_code, start, end),
            ).fetchone()
        return int(row["n"])

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM research_run WHERE run_id=?",
                (run_id,),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        meta = d.get("meta_json")
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except json.JSONDecodeError:
                meta = {}
        d["meta"] = meta if isinstance(meta, dict) else {}
        return d

    def find_freeze_by_hash(self, artifact_hash: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM research_evidence_freeze
                WHERE artifact_hash=? AND status='frozen'
                LIMIT 1
                """,
                (artifact_hash,),
            ).fetchone()
        return dict(row) if row else None

    def insert_freeze(self, row: dict[str, Any]) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO research_evidence_freeze (
                    freeze_id, evidence_run_id, universe_code, start_date, end_date,
                    status, split_mode, hard_gates_json, summary_json, artifact_hash,
                    actor, reason, job_id, meta_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["freeze_id"],
                    row["evidence_run_id"],
                    row["universe_code"],
                    row["start_date"],
                    row["end_date"],
                    row["status"],
                    row["split_mode"],
                    json.dumps(row.get("hard_gates") or {}, ensure_ascii=False),
                    json.dumps(row.get("summary") or {}, ensure_ascii=False),
                    row["artifact_hash"],
                    row.get("actor"),
                    row.get("reason"),
                    row.get("job_id"),
                    json.dumps(row.get("meta") or {}, ensure_ascii=False),
                    row["created_at"],
                ),
            )

    def list_freezes(
        self,
        *,
        universe_code: str | None = None,
        status: str = "frozen",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM research_evidence_freeze WHERE 1=1"
        params: list[Any] = []
        if status:
            sql += " AND status=?"
            params.append(status)
        if universe_code:
            sql += " AND universe_code=?"
            params.append(universe_code)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(int(limit), 200)))
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def list_factor_defs(
        self, *, status: str | None = "ACTIVE", limit: int = 200
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM research_factor_def WHERE 1=1"
        params: list[Any] = []
        if status:
            sql += " AND status=?"
            params.append(status)
        sql += " ORDER BY is_builtin DESC, factor_code ASC LIMIT ?"
        params.append(max(1, min(int(limit), 500)))
        with get_conn() as conn:
            rows = [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]
        for r in rows:
            try:
                r["params"] = json.loads(str(r.get("params_json") or "{}"))
            except json.JSONDecodeError:
                r["params"] = {}
        return rows

    def get_factor_def(self, factor_code: str) -> dict[str, Any] | None:
        code = (factor_code or "").strip()
        if not code:
            return None
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM research_factor_def WHERE factor_code=?",
                (code,),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["params"] = json.loads(str(d.get("params_json") or "{}"))
        except json.JSONDecodeError:
            d["params"] = {}
        return d

    def upsert_factor_def(self, row: dict[str, Any]) -> dict[str, Any]:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO research_factor_def (
                    factor_code, display_name, template, params_json, description,
                    status, is_builtin, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (factor_code) DO UPDATE SET
                    display_name=excluded.display_name,
                    template=excluded.template,
                    params_json=excluded.params_json,
                    description=excluded.description,
                    status=excluded.status,
                    updated_at=excluded.updated_at
                """,
                (
                    row["factor_code"],
                    row.get("display_name") or row["factor_code"],
                    row["template"],
                    json.dumps(row.get("params") or {}, ensure_ascii=False),
                    row.get("description"),
                    row.get("status") or "ACTIVE",
                    int(row.get("is_builtin") or 0),
                    row.get("created_by"),
                    row["created_at"],
                    row["updated_at"],
                ),
            )
        got = self.get_factor_def(row["factor_code"])
        assert got is not None
        return got

    def update_factor_def(
        self, factor_code: str, patch: dict[str, Any]
    ) -> dict[str, Any] | None:
        cur = self.get_factor_def(factor_code)
        if not cur:
            return None
        if int(cur.get("is_builtin") or 0) == 1:
            if "template" in patch and patch["template"] != cur["template"]:
                raise ValueError("内置因子不可更换模板")
        merged = {
            "factor_code": cur["factor_code"],
            "display_name": patch.get("display_name", cur.get("display_name")),
            "template": patch.get("template", cur["template"]),
            "params": patch.get("params", cur.get("params") or {}),
            "description": patch.get("description", cur.get("description")),
            "status": patch.get("status", cur.get("status") or "ACTIVE"),
            "is_builtin": int(cur.get("is_builtin") or 0),
            "created_by": cur.get("created_by"),
            "created_at": cur.get("created_at"),
            "updated_at": patch["updated_at"],
        }
        return self.upsert_factor_def(merged)
