from __future__ import annotations

from typing import Any

from shared.db import get_conn


def _placeholders(n: int) -> str:
    return ",".join("?" * n)


class ProcessRepository:
    """读已提交 raw_*，幂等写 processed_*。"""

    def load_equity_bars(
        self,
        *,
        start: str | None,
        end: str | None,
        symbols: list[str],
        preferred_source: str,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT symbol, trade_date, open, high, low, close,
                   volume, amount, source
            FROM raw_equity_bar_1d
            WHERE 1=1
        """
        params: list[Any] = []
        if start:
            sql += " AND trade_date >= ?"
            params.append(start[:10])
        if end:
            sql += " AND trade_date <= ?"
            params.append(end[:10])
        if symbols:
            sql += f" AND symbol IN ({_placeholders(len(symbols))})"
            params.extend(symbols)
        sql += " ORDER BY symbol, trade_date, source"
        with get_conn() as conn:
            rows = [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]
        return _prefer_source(rows, key_fields=("symbol", "trade_date"), preferred=preferred_source)

    def load_adj_factors(
        self,
        *,
        start: str | None,
        end: str | None,
        symbols: list[str],
        factor_type: str,
        preferred_source: str,
    ) -> dict[tuple[str, str], float]:
        sql = """
            SELECT symbol, trade_date, factor, source
            FROM raw_adj_factor
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
            sql += f" AND symbol IN ({_placeholders(len(symbols))})"
            params.extend(symbols)
        with get_conn() as conn:
            rows = [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]
        picked = _prefer_source(
            rows, key_fields=("symbol", "trade_date"), preferred=preferred_source
        )
        out: dict[tuple[str, str], float] = {}
        for r in picked:
            out[(str(r["symbol"]), str(r["trade_date"])[:10])] = float(r["factor"])
        return out

    def load_suspend_keys(
        self,
        *,
        start: str | None,
        end: str | None,
        symbols: list[str],
    ) -> set[tuple[str, str]]:
        sql = "SELECT DISTINCT symbol, trade_date FROM raw_suspend WHERE 1=1"
        params: list[Any] = []
        if start:
            sql += " AND trade_date >= ?"
            params.append(start[:10])
        if end:
            sql += " AND trade_date <= ?"
            params.append(end[:10])
        if symbols:
            sql += f" AND symbol IN ({_placeholders(len(symbols))})"
            params.extend(symbols)
        with get_conn() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return {(str(r["symbol"]), str(r["trade_date"])[:10]) for r in rows}

    def load_limit_keys(
        self,
        *,
        start: str | None,
        end: str | None,
        symbols: list[str],
    ) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
        sql = """
            SELECT DISTINCT symbol, trade_date, UPPER(event_type) AS event_type
            FROM raw_limit_board
            WHERE 1=1
        """
        params: list[Any] = []
        if start:
            sql += " AND trade_date >= ?"
            params.append(start[:10])
        if end:
            sql += " AND trade_date <= ?"
            params.append(end[:10])
        if symbols:
            sql += f" AND symbol IN ({_placeholders(len(symbols))})"
            params.extend(symbols)
        up: set[tuple[str, str]] = set()
        down: set[tuple[str, str]] = set()
        with get_conn() as conn:
            for r in conn.execute(sql, tuple(params)).fetchall():
                key = (str(r["symbol"]), str(r["trade_date"])[:10])
                et = str(r["event_type"] or "")
                if et in ("UP", "LIMIT_UP", "U"):
                    up.add(key)
                elif et in ("DOWN", "LIMIT_DOWN", "D"):
                    down.add(key)
        return up, down

    def load_index_bars(
        self,
        *,
        start: str | None,
        end: str | None,
        index_symbols: list[str],
        preferred_source: str,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT index_symbol, trade_date, open, high, low, close,
                   volume, amount, source
            FROM raw_index_bar_1d
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
            sql += f" AND index_symbol IN ({_placeholders(len(index_symbols))})"
            params.extend(index_symbols)
        sql += " ORDER BY index_symbol, trade_date, source"
        with get_conn() as conn:
            rows = [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]
        return _prefer_source(
            rows, key_fields=("index_symbol", "trade_date"), preferred=preferred_source
        )

    def upsert_equity_rows(self, rows: list[dict[str, Any]]) -> tuple[int, int]:
        if not rows:
            return 0, 0
        inserted = 0
        updated = 0
        sql = """
            INSERT INTO processed_equity_bar_1d (
                process_batch_id, symbol, trade_date,
                open, high, low, close, volume, amount,
                adj_factor, factor_type,
                adj_open, adj_high, adj_low, adj_close, ret_1d,
                is_suspended, is_limit_up, is_limit_down, can_buy, can_sell,
                source, processed_at
            ) VALUES (
                ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?
            )
            ON CONFLICT(symbol, trade_date, factor_type) DO UPDATE SET
                process_batch_id=excluded.process_batch_id,
                open=excluded.open, high=excluded.high, low=excluded.low,
                close=excluded.close, volume=excluded.volume, amount=excluded.amount,
                adj_factor=excluded.adj_factor,
                adj_open=excluded.adj_open, adj_high=excluded.adj_high,
                adj_low=excluded.adj_low, adj_close=excluded.adj_close,
                ret_1d=excluded.ret_1d,
                is_suspended=excluded.is_suspended,
                is_limit_up=excluded.is_limit_up,
                is_limit_down=excluded.is_limit_down,
                can_buy=excluded.can_buy, can_sell=excluded.can_sell,
                source=excluded.source, processed_at=excluded.processed_at
        """
        exists_sql = """
            SELECT 1 FROM processed_equity_bar_1d
            WHERE symbol=? AND trade_date=? AND factor_type=?
        """
        with get_conn() as conn:
            for row in rows:
                existed = conn.execute(
                    exists_sql,
                    (row["symbol"], row["trade_date"], row["factor_type"]),
                ).fetchone()
                conn.execute(
                    sql,
                    (
                        row["process_batch_id"],
                        row["symbol"],
                        row["trade_date"],
                        row["open"],
                        row["high"],
                        row["low"],
                        row["close"],
                        row["volume"],
                        row["amount"],
                        row["adj_factor"],
                        row["factor_type"],
                        row["adj_open"],
                        row["adj_high"],
                        row["adj_low"],
                        row["adj_close"],
                        row["ret_1d"],
                        row["is_suspended"],
                        row["is_limit_up"],
                        row["is_limit_down"],
                        row["can_buy"],
                        row["can_sell"],
                        row["source"],
                        row["processed_at"],
                    ),
                )
                if existed:
                    updated += 1
                else:
                    inserted += 1
        return inserted, updated

    def upsert_index_rows(self, rows: list[dict[str, Any]]) -> tuple[int, int]:
        if not rows:
            return 0, 0
        inserted = 0
        updated = 0
        sql = """
            INSERT INTO processed_index_bar_1d (
                process_batch_id, index_symbol, trade_date,
                open, high, low, close, volume, amount, ret_1d,
                source, processed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(index_symbol, trade_date) DO UPDATE SET
                process_batch_id=excluded.process_batch_id,
                open=excluded.open, high=excluded.high, low=excluded.low,
                close=excluded.close, volume=excluded.volume, amount=excluded.amount,
                ret_1d=excluded.ret_1d, source=excluded.source,
                processed_at=excluded.processed_at
        """
        exists_sql = """
            SELECT 1 FROM processed_index_bar_1d
            WHERE index_symbol=? AND trade_date=?
        """
        with get_conn() as conn:
            for row in rows:
                existed = conn.execute(
                    exists_sql, (row["index_symbol"], row["trade_date"])
                ).fetchone()
                conn.execute(
                    sql,
                    (
                        row["process_batch_id"],
                        row["index_symbol"],
                        row["trade_date"],
                        row["open"],
                        row["high"],
                        row["low"],
                        row["close"],
                        row["volume"],
                        row["amount"],
                        row["ret_1d"],
                        row["source"],
                        row["processed_at"],
                    ),
                )
                if existed:
                    updated += 1
                else:
                    inserted += 1
        return inserted, updated

    def count_processed(self, table: str) -> int:
        with get_conn() as conn:
            return int(conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])


def _prefer_source(
    rows: list[dict[str, Any]],
    *,
    key_fields: tuple[str, ...],
    preferred: str,
) -> list[dict[str, Any]]:
    """同一业务键多源时优先 preferred，否则取字典序第一个 source。"""
    buckets: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for r in rows:
        key = tuple(r[k] for k in key_fields)
        buckets.setdefault(key, []).append(r)
    out: list[dict[str, Any]] = []
    for key in sorted(buckets.keys()):
        group = buckets[key]
        preferred_rows = [r for r in group if r.get("source") == preferred]
        chosen = preferred_rows[0] if preferred_rows else sorted(
            group, key=lambda x: str(x.get("source") or "")
        )[0]
        out.append(chosen)
    return out
