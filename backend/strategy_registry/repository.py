from __future__ import annotations

import json
from typing import Any

from shared.db import get_conn
from strategy_registry.models import StrategyRecord


def _parse_params(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(str(raw))
    except json.JSONDecodeError:
        return {}


def _row_to_record(row: Any) -> StrategyRecord:
    d = dict(row)
    return StrategyRecord(
        strategy_version=str(d["strategy_version"]),
        strategy_code=str(d["strategy_code"]),
        strategy_kind=str(d["strategy_kind"]),
        status=str(d["status"]),
        params=_parse_params(d.get("params_json")),
        research_run_id=d.get("research_run_id"),
        backtest_run_id=d.get("backtest_run_id"),
        artifact_hash=d.get("artifact_hash"),
        note=d.get("note"),
        created_at=str(d.get("created_at") or ""),
        updated_at=str(d.get("updated_at") or ""),
    )


class StrategyRegistryRepository:
    def insert_version(self, row: dict[str, Any]) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO strategy_version (
                    strategy_version, strategy_code, strategy_kind, status,
                    params_json, research_run_id, backtest_run_id, artifact_hash,
                    note, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["strategy_version"],
                    row["strategy_code"],
                    row["strategy_kind"],
                    row["status"],
                    json.dumps(row["params"], ensure_ascii=False),
                    row.get("research_run_id"),
                    row.get("backtest_run_id"),
                    row.get("artifact_hash"),
                    row.get("note"),
                    row["created_at"],
                    row["updated_at"],
                ),
            )
            conn.execute(
                """
                INSERT INTO strategy_transition (
                    transition_id, strategy_version, from_status, to_status,
                    actor, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["transition_id"],
                    row["strategy_version"],
                    "NONE",
                    row["status"],
                    row.get("actor") or "cli",
                    row.get("note") or "register",
                    row["created_at"],
                ),
            )

    def get(self, strategy_version: str) -> StrategyRecord | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM strategy_version WHERE strategy_version=?",
                (strategy_version,),
            ).fetchone()
        return _row_to_record(row) if row else None

    def list_versions(
        self,
        *,
        status: str | None = None,
        strategy_code: str | None = None,
        limit: int = 50,
    ) -> list[StrategyRecord]:
        sql = "SELECT * FROM strategy_version WHERE 1=1"
        params: list[Any] = []
        if status:
            sql += " AND status=?"
            params.append(status)
        if strategy_code:
            sql += " AND strategy_code=?"
            params.append(strategy_code)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(max(1, min(limit, 500)))
        with get_conn() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [_row_to_record(r) for r in rows]

    def list_runnable(self) -> list[StrategyRecord]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM strategy_version
                WHERE status IN ('PAPER', 'LIVE')
                ORDER BY status DESC, strategy_code
                """
            ).fetchall()
        return [_row_to_record(r) for r in rows]

    def find_live(self, strategy_code: str) -> StrategyRecord | None:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM strategy_version
                WHERE strategy_code=? AND status='LIVE'
                LIMIT 1
                """,
                (strategy_code,),
            ).fetchone()
        return _row_to_record(row) if row else None

    def backtest_exists(self, run_id: str) -> bool:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM backtest_run
                WHERE run_id=? AND status='committed'
                LIMIT 1
                """,
                (run_id,),
            ).fetchone()
        return bool(row)

    def research_exists(self, run_id: str) -> bool:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM research_run
                WHERE run_id=? AND status='committed'
                LIMIT 1
                """,
                (run_id,),
            ).fetchone()
        return bool(row)

    def apply_transition(
        self,
        *,
        strategy_version: str,
        from_status: str,
        to_status: str,
        transition_id: str,
        actor: str,
        reason: str | None,
        updated_at: str,
        backtest_run_id: str | None = None,
        retire_versions: list[tuple[str, str]] | None = None,
    ) -> None:
        """retire_versions: [(version, transition_id), ...] 同事务停用旧 LIVE。"""
        with get_conn() as conn:
            for old_ver, tid in retire_versions or []:
                conn.execute(
                    """
                    UPDATE strategy_version
                    SET status='RETIRED', updated_at=?,
                        note=COALESCE(note,'') || ' | auto-retired on LIVE promote'
                    WHERE strategy_version=? AND status='LIVE'
                    """,
                    (updated_at, old_ver),
                )
                conn.execute(
                    """
                    INSERT INTO strategy_transition (
                        transition_id, strategy_version, from_status, to_status,
                        actor, reason, created_at
                    ) VALUES (?, ?, 'LIVE', 'RETIRED', ?, ?, ?)
                    """,
                    (
                        tid,
                        old_ver,
                        actor,
                        f"auto-retired for {strategy_version}",
                        updated_at,
                    ),
                )

            sets = ["status=?", "updated_at=?"]
            params: list[Any] = [to_status, updated_at]
            if backtest_run_id:
                sets.append("backtest_run_id=?")
                params.append(backtest_run_id)
            params.extend([strategy_version, from_status])
            conn.execute(
                f"""
                UPDATE strategy_version SET {', '.join(sets)}
                WHERE strategy_version=? AND status=?
                """,
                tuple(params),
            )
            cur = conn.execute(
                "SELECT status FROM strategy_version WHERE strategy_version=?",
                (strategy_version,),
            ).fetchone()
            if not cur or str(cur["status"]) != to_status:
                raise RuntimeError(
                    f"strategy CAS 失败: expect {from_status}→{to_status}, "
                    f"got {None if not cur else cur['status']}"
                )
            conn.execute(
                """
                INSERT INTO strategy_transition (
                    transition_id, strategy_version, from_status, to_status,
                    actor, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    transition_id,
                    strategy_version,
                    from_status,
                    to_status,
                    actor,
                    reason,
                    updated_at,
                ),
            )

    def list_transitions(self, strategy_version: str) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM strategy_transition
                WHERE strategy_version=?
                ORDER BY created_at
                """,
                (strategy_version,),
            ).fetchall()
        return [dict(r) for r in rows]
