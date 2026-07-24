from __future__ import annotations

from typing import Any

from data_ingest.alpha_announcement.timeutil import utc_now_iso
from data_ingest.core_ref.models import FetchBundle, IngestKind, UpsertStats
from shared.db import get_conn

_UPSERT_SQL: dict[IngestKind, tuple[str, tuple[str, ...]]] = {
    "calendar": (
        """
        INSERT INTO raw_trade_calendar (
            batch_id, exchange, trade_date, is_open, is_half_day, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(exchange, trade_date, source) DO UPDATE SET
            batch_id=excluded.batch_id,
            is_open=excluded.is_open,
            is_half_day=excluded.is_half_day,
            ingested_at=excluded.ingested_at
        """,
        ("exchange", "trade_date", "is_open", "is_half_day", "source"),
    ),
    "listing": (
        """
        INSERT INTO raw_security_listing (
            batch_id, symbol, name, exchange, board, list_date, delist_date,
            effective_date, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, effective_date, source) DO UPDATE SET
            batch_id=excluded.batch_id,
            name=excluded.name,
            exchange=excluded.exchange,
            board=excluded.board,
            list_date=excluded.list_date,
            delist_date=excluded.delist_date,
            ingested_at=excluded.ingested_at
        """,
        (
            "symbol",
            "name",
            "exchange",
            "board",
            "list_date",
            "delist_date",
            "effective_date",
            "source",
        ),
    ),
    "industry": (
        """
        INSERT INTO raw_industry_class (
            batch_id, symbol, standard, industry_code, industry_name,
            effective_date, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, effective_date, standard, source) DO UPDATE SET
            batch_id=excluded.batch_id,
            industry_code=excluded.industry_code,
            industry_name=excluded.industry_name,
            ingested_at=excluded.ingested_at
        """,
        (
            "symbol",
            "standard",
            "industry_code",
            "industry_name",
            "effective_date",
            "source",
        ),
    ),
    "share_capital": (
        """
        INSERT INTO raw_share_capital (
            batch_id, symbol, total_shares, float_shares, effective_date, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, effective_date, source) DO UPDATE SET
            batch_id=excluded.batch_id,
            total_shares=excluded.total_shares,
            float_shares=excluded.float_shares,
            ingested_at=excluded.ingested_at
        """,
        ("symbol", "total_shares", "float_shares", "effective_date", "source"),
    ),
    "index_member": (
        """
        INSERT INTO raw_index_member (
            batch_id, index_symbol, symbol, trade_date, weight, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(index_symbol, symbol, trade_date, source) DO UPDATE SET
            batch_id=excluded.batch_id,
            weight=excluded.weight,
            ingested_at=excluded.ingested_at
        """,
        ("index_symbol", "symbol", "trade_date", "weight", "source"),
    ),
    "special_treat": (
        """
        INSERT INTO raw_special_treat (
            batch_id, symbol, treat_type, effective_date, end_date, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, effective_date, treat_type, source) DO UPDATE SET
            batch_id=excluded.batch_id,
            end_date=excluded.end_date,
            ingested_at=excluded.ingested_at
        """,
        ("symbol", "treat_type", "effective_date", "end_date", "source"),
    ),
}

_EXIST_SQL: dict[IngestKind, tuple[str, tuple[str, ...]]] = {
    "calendar": (
        "SELECT 1 FROM raw_trade_calendar WHERE exchange=? AND trade_date=? AND source=?",
        ("exchange", "trade_date", "source"),
    ),
    "listing": (
        "SELECT 1 FROM raw_security_listing WHERE symbol=? AND effective_date=? AND source=?",
        ("symbol", "effective_date", "source"),
    ),
    "industry": (
        "SELECT 1 FROM raw_industry_class WHERE symbol=? AND effective_date=? AND standard=? AND source=?",
        ("symbol", "effective_date", "standard", "source"),
    ),
    "share_capital": (
        "SELECT 1 FROM raw_share_capital WHERE symbol=? AND effective_date=? AND source=?",
        ("symbol", "effective_date", "source"),
    ),
    "index_member": (
        "SELECT 1 FROM raw_index_member WHERE index_symbol=? AND symbol=? AND trade_date=? AND source=?",
        ("index_symbol", "symbol", "trade_date", "source"),
    ),
    "special_treat": (
        "SELECT 1 FROM raw_special_treat WHERE symbol=? AND effective_date=? AND treat_type=? AND source=?",
        ("symbol", "effective_date", "treat_type", "source"),
    ),
}


class CoreRefRepository:
    def upsert_bundle(self, batch_id: str, bundle: FetchBundle) -> UpsertStats:
        stats = UpsertStats()
        if not bundle.rows:
            return stats
        sql, value_keys = _UPSERT_SQL[bundle.kind]
        exist_sql, exist_keys = _EXIST_SQL[bundle.kind]
        ingested_at = utc_now_iso()
        with get_conn() as conn:
            for row in bundle.rows:
                exist_params = tuple(row[k] for k in exist_keys)
                existed = conn.execute(exist_sql, exist_params).fetchone()
                values = (batch_id, *(row[k] for k in value_keys), ingested_at)
                # value_keys already includes source; sql placeholders match
                conn.execute(sql, values)
                if existed:
                    stats.updated += 1
                else:
                    stats.inserted += 1
        return stats

    def counts(self) -> dict[str, int]:
        tables = [
            "raw_trade_calendar",
            "raw_security_listing",
            "raw_industry_class",
            "raw_share_capital",
            "raw_index_member",
            "raw_special_treat",
        ]
        out: dict[str, int] = {}
        with get_conn() as conn:
            for t in tables:
                out[t] = int(conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"])
        return out
