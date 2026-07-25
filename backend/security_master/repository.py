from __future__ import annotations

import json
from typing import Any

from shared.db import get_conn


class SecurityMasterRepository:
    def resolve_as_of(self, as_of: str, *, exchange: str = "SSE") -> tuple[str, bool]:
        """返回 (实际使用日, 是否调整过)。优先当日开市，否则上一开市日。"""
        d = as_of[:10]
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT is_open FROM raw_trade_calendar
                WHERE exchange=? AND trade_date=? AND source='akshare'
                LIMIT 1
                """,
                (exchange, d),
            ).fetchone()
            if row and int(row["is_open"]) == 1:
                return d, False
            prev = conn.execute(
                """
                SELECT trade_date FROM raw_trade_calendar
                WHERE exchange=? AND trade_date<=? AND is_open=1 AND source='akshare'
                ORDER BY trade_date DESC LIMIT 1
                """,
                (exchange, d),
            ).fetchone()
            if prev:
                return str(prev["trade_date"])[:10], True
            # 无日历时原样使用
            return d, False

    def load_listings(self, *, as_of: str, preferred_source: str) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT symbol, name, exchange, board, list_date, delist_date,
                           effective_date, source
                    FROM raw_security_listing
                    WHERE effective_date <= ?
                    ORDER BY symbol, effective_date DESC, source
                    """,
                    (as_of,),
                ).fetchall()
            ]
        # 每标的取最新 effective_date，优先 preferred_source
        best: dict[str, dict[str, Any]] = {}
        for r in rows:
            sym = str(r["symbol"])
            cur = best.get(sym)
            if cur is None:
                best[sym] = r
                continue
            if str(r["effective_date"]) > str(cur["effective_date"]):
                best[sym] = r
            elif (
                str(r["effective_date"]) == str(cur["effective_date"])
                and r.get("source") == preferred_source
                and cur.get("source") != preferred_source
            ):
                best[sym] = r
        out = []
        for r in best.values():
            list_date = (r.get("list_date") or "")[:10] or None
            delist = (r.get("delist_date") or "")[:10] or None
            if list_date and list_date > as_of:
                continue
            if delist and delist <= as_of:
                continue
            out.append(r)
        return out

    def load_industry_map(
        self, *, as_of: str, standard: str, preferred_source: str
    ) -> dict[str, dict[str, Any]]:
        with get_conn() as conn:
            rows = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT symbol, industry_code, industry_name, effective_date, source
                    FROM raw_industry_class
                    WHERE standard=? AND effective_date<=?
                    ORDER BY symbol, effective_date DESC
                    """,
                    (standard, as_of),
                ).fetchall()
            ]
        best: dict[str, dict[str, Any]] = {}
        for r in rows:
            sym = str(r["symbol"])
            cur = best.get(sym)
            if cur is None or str(r["effective_date"]) > str(cur["effective_date"]):
                best[sym] = r
            elif (
                str(r["effective_date"]) == str(cur["effective_date"])
                and r.get("source") == preferred_source
            ):
                best[sym] = r
        return best

    def load_st_map(self, *, as_of: str) -> dict[str, dict[str, Any]]:
        with get_conn() as conn:
            rows = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT symbol, treat_type, effective_date, end_date, source
                    FROM raw_special_treat
                    WHERE effective_date <= ?
                    ORDER BY symbol, effective_date DESC
                    """,
                    (as_of,),
                ).fetchall()
            ]
        active: dict[str, dict[str, Any]] = {}
        for r in rows:
            sym = str(r["symbol"])
            end = (r.get("end_date") or "")[:10] or None
            if end and end <= as_of:
                continue
            # 已按 effective_date DESC；首次命中即为最新仍生效
            if sym not in active:
                active[sym] = r
        return active

    def load_share_capital_map(self, *, as_of: str) -> dict[str, dict[str, Any]]:
        """点时最新股本（effective_date <= as_of）。"""
        with get_conn() as conn:
            rows = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT symbol, total_shares, float_shares, effective_date, source
                    FROM raw_share_capital
                    WHERE effective_date <= ?
                    ORDER BY symbol, effective_date DESC
                    """,
                    (as_of,),
                ).fetchall()
            ]
        best: dict[str, dict[str, Any]] = {}
        for r in rows:
            sym = str(r["symbol"])
            if sym not in best:
                best[sym] = r
        return best

    def load_latest_close_map(self, *, as_of: str) -> dict[str, float]:
        """
        仅用库内已有日线收盘（不触发拉取）。
        若无行情则返回空 dict，排名回退到股本本身。
        """
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT ON (symbol) symbol, close
                FROM raw_equity_bar_1d
                WHERE trade_date <= ? AND close IS NOT NULL AND close > 0
                ORDER BY symbol, trade_date DESC
                """,
                (as_of,),
            ).fetchall()
        out: dict[str, float] = {}
        for r in rows:
            try:
                out[str(r["symbol"])] = float(r["close"])
            except (TypeError, ValueError):
                continue
        return out

    def load_index_members(
        self, *, index_symbol: str, as_of: str, preferred_source: str
    ) -> tuple[list[dict[str, Any]], str | None, bool]:
        """
        点时成分：取 trade_date <= as_of 的最近一期。
        若无（本地仅有一期且日期晚于 as_of），回退该期并标记 fallback=True。
        返回 (members, member_effective_date, used_fallback)。
        """
        used_fallback = False
        with get_conn() as conn:
            day = conn.execute(
                """
                SELECT MAX(trade_date) AS d FROM raw_index_member
                WHERE index_symbol=? AND trade_date<=?
                """,
                (index_symbol, as_of),
            ).fetchone()
            trade_date = day["d"] if day and day["d"] else None
            if not trade_date:
                day = conn.execute(
                    """
                    SELECT MAX(trade_date) AS d FROM raw_index_member
                    WHERE index_symbol=?
                    """,
                    (index_symbol,),
                ).fetchone()
                trade_date = day["d"] if day else None
                used_fallback = trade_date is not None
            if not trade_date:
                return [], None, False
            rows = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT index_symbol, symbol, trade_date, weight, source
                    FROM raw_index_member
                    WHERE index_symbol=? AND trade_date=?
                    """,
                    (index_symbol, trade_date),
                ).fetchall()
            ]
        best: dict[str, dict[str, Any]] = {}
        for r in rows:
            sym = str(r["symbol"])
            if sym not in best or r.get("source") == preferred_source:
                best[sym] = r
        return list(best.values()), str(trade_date)[:10], used_fallback

    def replace_snapshot(
        self,
        *,
        snapshot_id: str,
        as_of_date: str,
        universe_code: str,
        members: list[dict[str, Any]],
        meta: dict[str, Any],
        job_id: str | None,
        created_at: str,
        source_note: str,
    ) -> None:
        with get_conn() as conn:
            # 幂等：同 (as_of, code) 先删旧成员与头
            old = conn.execute(
                """
                SELECT universe_snapshot_id FROM universe_snapshot
                WHERE as_of_date=? AND universe_code=?
                """,
                (as_of_date, universe_code),
            ).fetchone()
            if old:
                oid = old["universe_snapshot_id"]
                conn.execute(
                    "DELETE FROM universe_snapshot_member WHERE universe_snapshot_id=?",
                    (oid,),
                )
                conn.execute(
                    "DELETE FROM universe_snapshot WHERE universe_snapshot_id=?",
                    (oid,),
                )
            conn.execute(
                """
                INSERT INTO universe_snapshot (
                    universe_snapshot_id, as_of_date, universe_code, status,
                    member_count, source_note, job_id, meta_json, created_at
                ) VALUES (?, ?, ?, 'committed', ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    as_of_date,
                    universe_code,
                    len(members),
                    source_note,
                    job_id,
                    json.dumps(meta, ensure_ascii=False),
                    created_at,
                ),
            )
            for m in members:
                conn.execute(
                    """
                    INSERT INTO universe_snapshot_member (
                        universe_snapshot_id, symbol, name, exchange, board,
                        list_date, delist_date, industry_code, industry_name,
                        is_st, treat_type, index_weight, is_eligible
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot_id,
                        m["symbol"],
                        m.get("name"),
                        m.get("exchange"),
                        m.get("board"),
                        m.get("list_date"),
                        m.get("delist_date"),
                        m.get("industry_code"),
                        m.get("industry_name"),
                        m.get("is_st", 0),
                        m.get("treat_type"),
                        m.get("index_weight"),
                        m.get("is_eligible", 1),
                    ),
                )
