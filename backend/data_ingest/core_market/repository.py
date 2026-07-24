from __future__ import annotations

from typing import Any

from data_ingest.alpha_announcement.timeutil import utc_now_iso
from data_ingest.core_market.models import FetchBundle, IngestKind, UpsertStats
from shared.db import get_conn

_UPSERT_SQL: dict[IngestKind, tuple[str, tuple[str, ...]]] = {
    "equity_1d": (
        """
        INSERT INTO raw_equity_bar_1d (
            batch_id, symbol, trade_date, open, high, low, close,
            volume, amount, turnover, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, trade_date, source) DO UPDATE SET
            batch_id=excluded.batch_id,
            open=excluded.open, high=excluded.high, low=excluded.low,
            close=excluded.close, volume=excluded.volume, amount=excluded.amount,
            turnover=excluded.turnover, ingested_at=excluded.ingested_at
        """,
        (
            "symbol",
            "trade_date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
            "turnover",
            "source",
        ),
    ),
    "adj_factor": (
        """
        INSERT INTO raw_adj_factor (
            batch_id, symbol, trade_date, factor_type, factor, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, trade_date, factor_type, source) DO UPDATE SET
            batch_id=excluded.batch_id,
            factor=excluded.factor,
            ingested_at=excluded.ingested_at
        """,
        ("symbol", "trade_date", "factor_type", "factor", "source"),
    ),
    "suspend": (
        """
        INSERT INTO raw_suspend (
            batch_id, symbol, trade_date, event_type, suspend_type, reason,
            resume_date, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, trade_date, event_type, source) DO UPDATE SET
            batch_id=excluded.batch_id,
            suspend_type=excluded.suspend_type,
            reason=excluded.reason,
            resume_date=excluded.resume_date,
            ingested_at=excluded.ingested_at
        """,
        (
            "symbol",
            "trade_date",
            "event_type",
            "suspend_type",
            "reason",
            "resume_date",
            "source",
        ),
    ),
    "limit": (
        """
        INSERT INTO raw_limit_board (
            batch_id, symbol, trade_date, event_type, close, pct_chg, amount,
            first_time, last_time, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, trade_date, event_type, source) DO UPDATE SET
            batch_id=excluded.batch_id,
            close=excluded.close,
            pct_chg=excluded.pct_chg,
            amount=excluded.amount,
            first_time=excluded.first_time,
            last_time=excluded.last_time,
            ingested_at=excluded.ingested_at
        """,
        (
            "symbol",
            "trade_date",
            "event_type",
            "close",
            "pct_chg",
            "amount",
            "first_time",
            "last_time",
            "source",
        ),
    ),
    "index_1d": (
        """
        INSERT INTO raw_index_bar_1d (
            batch_id, index_symbol, trade_date, open, high, low, close,
            volume, amount, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(index_symbol, trade_date, source) DO UPDATE SET
            batch_id=excluded.batch_id,
            open=excluded.open, high=excluded.high, low=excluded.low,
            close=excluded.close, volume=excluded.volume, amount=excluded.amount,
            ingested_at=excluded.ingested_at
        """,
        (
            "index_symbol",
            "trade_date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
            "source",
        ),
    ),
    "corp_action": (
        """
        INSERT INTO raw_corp_action (
            batch_id, symbol, ex_date, action_type, raw_payload, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, ex_date, action_type, source) DO UPDATE SET
            batch_id=excluded.batch_id,
            raw_payload=excluded.raw_payload,
            ingested_at=excluded.ingested_at
        """,
        ("symbol", "ex_date", "action_type", "raw_payload", "source"),
    ),
}

_EXIST_SQL: dict[IngestKind, tuple[str, tuple[str, ...]]] = {
    "equity_1d": (
        "SELECT 1 FROM raw_equity_bar_1d WHERE symbol=? AND trade_date=? AND source=?",
        ("symbol", "trade_date", "source"),
    ),
    "adj_factor": (
        "SELECT 1 FROM raw_adj_factor WHERE symbol=? AND trade_date=? AND factor_type=? AND source=?",
        ("symbol", "trade_date", "factor_type", "source"),
    ),
    "suspend": (
        "SELECT 1 FROM raw_suspend WHERE symbol=? AND trade_date=? AND event_type=? AND source=?",
        ("symbol", "trade_date", "event_type", "source"),
    ),
    "limit": (
        "SELECT 1 FROM raw_limit_board WHERE symbol=? AND trade_date=? AND event_type=? AND source=?",
        ("symbol", "trade_date", "event_type", "source"),
    ),
    "index_1d": (
        "SELECT 1 FROM raw_index_bar_1d WHERE index_symbol=? AND trade_date=? AND source=?",
        ("index_symbol", "trade_date", "source"),
    ),
    "corp_action": (
        "SELECT 1 FROM raw_corp_action WHERE symbol=? AND ex_date=? AND action_type=? AND source=?",
        ("symbol", "ex_date", "action_type", "source"),
    ),
}


class CoreMarketRepository:
    def upsert_bundle(self, batch_id: str, bundle: FetchBundle) -> UpsertStats:
        stats = UpsertStats()
        if not bundle.rows:
            return stats
        sql, value_keys = _UPSERT_SQL[bundle.kind]
        exist_sql, exist_keys = _EXIST_SQL[bundle.kind]
        ingested_at = utc_now_iso()
        with get_conn() as conn:
            for row in bundle.rows:
                existed = conn.execute(
                    exist_sql, tuple(row[k] for k in exist_keys)
                ).fetchone()
                values = (batch_id, *(row[k] for k in value_keys), ingested_at)
                conn.execute(sql, values)
                if existed:
                    stats.updated += 1
                else:
                    stats.inserted += 1
        return stats

    def counts(self) -> dict[str, int]:
        tables = [
            "raw_equity_bar_1d",
            "raw_adj_factor",
            "raw_suspend",
            "raw_limit_board",
            "raw_index_bar_1d",
            "raw_corp_action",
        ]
        out: dict[str, int] = {}
        with get_conn() as conn:
            for t in tables:
                out[t] = int(
                    conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
                )
        return out
