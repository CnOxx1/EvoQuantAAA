from __future__ import annotations

from data_ingest.alpha_announcement.timeutil import utc_now_iso
from data_ingest.alpha_fundamental.models import FetchBundle, IngestKind, UpsertStats
from shared.bulk_upsert import upsert_rows
from shared.db import get_conn

_UPSERT_SQL: dict[IngestKind, tuple[str, tuple[str, ...]]] = {
    "statement": (
        """
        INSERT INTO raw_fund_statement (
            batch_id, symbol, statement_type, report_period, announce_date,
            item_code, item_value, currency, report_type, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, statement_type, report_period, item_code, source) DO UPDATE SET
            batch_id=excluded.batch_id,
            announce_date=excluded.announce_date,
            item_value=excluded.item_value,
            currency=excluded.currency,
            report_type=excluded.report_type,
            ingested_at=excluded.ingested_at
        """,
        (
            "symbol",
            "statement_type",
            "report_period",
            "announce_date",
            "item_code",
            "item_value",
            "currency",
            "report_type",
            "source",
        ),
    ),
    "indicator": (
        """
        INSERT INTO raw_fund_indicator (
            batch_id, symbol, report_period, announce_date,
            indicator_code, indicator_value, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, report_period, indicator_code, source) DO UPDATE SET
            batch_id=excluded.batch_id,
            announce_date=excluded.announce_date,
            indicator_value=excluded.indicator_value,
            ingested_at=excluded.ingested_at
        """,
        (
            "symbol",
            "report_period",
            "announce_date",
            "indicator_code",
            "indicator_value",
            "source",
        ),
    ),
    "consensus": (
        """
        INSERT INTO raw_consensus_estimate (
            batch_id, symbol, asof_date, metric, period_year, value,
            version, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, asof_date, metric, period_year, source, version) DO UPDATE SET
            batch_id=excluded.batch_id,
            value=excluded.value,
            ingested_at=excluded.ingested_at
        """,
        (
            "symbol",
            "asof_date",
            "metric",
            "period_year",
            "value",
            "version",
            "source",
        ),
    ),
    "valuation": (
        """
        INSERT INTO raw_valuation_1d (
            batch_id, symbol, trade_date, close, pe_ttm, pe_static, pb, ps_ttm,
            pcf_ttm, peg, total_mv, float_mv, total_shares, float_shares,
            source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, trade_date, source) DO UPDATE SET
            batch_id=excluded.batch_id,
            close=excluded.close, pe_ttm=excluded.pe_ttm, pe_static=excluded.pe_static,
            pb=excluded.pb, ps_ttm=excluded.ps_ttm, pcf_ttm=excluded.pcf_ttm,
            peg=excluded.peg, total_mv=excluded.total_mv, float_mv=excluded.float_mv,
            total_shares=excluded.total_shares, float_shares=excluded.float_shares,
            ingested_at=excluded.ingested_at
        """,
        (
            "symbol",
            "trade_date",
            "close",
            "pe_ttm",
            "pe_static",
            "pb",
            "ps_ttm",
            "pcf_ttm",
            "peg",
            "total_mv",
            "float_mv",
            "total_shares",
            "float_shares",
            "source",
        ),
    ),
    "holder": (
        """
        INSERT INTO raw_holder_count (
            batch_id, symbol, asof_date, announce_date, holder_count,
            holder_count_prev, holder_change, holder_change_pct,
            avg_market_cap, avg_shares, total_mv, total_shares, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, asof_date, source) DO UPDATE SET
            batch_id=excluded.batch_id,
            announce_date=excluded.announce_date,
            holder_count=excluded.holder_count,
            holder_count_prev=excluded.holder_count_prev,
            holder_change=excluded.holder_change,
            holder_change_pct=excluded.holder_change_pct,
            avg_market_cap=excluded.avg_market_cap,
            avg_shares=excluded.avg_shares,
            total_mv=excluded.total_mv,
            total_shares=excluded.total_shares,
            ingested_at=excluded.ingested_at
        """,
        (
            "symbol",
            "asof_date",
            "announce_date",
            "holder_count",
            "holder_count_prev",
            "holder_change",
            "holder_change_pct",
            "avg_market_cap",
            "avg_shares",
            "total_mv",
            "total_shares",
            "source",
        ),
    ),
}

_EXIST_SQL: dict[IngestKind, tuple[str, tuple[str, ...]]] = {
    "statement": (
        """
        SELECT 1 FROM raw_fund_statement
        WHERE symbol=? AND statement_type=? AND report_period=? AND item_code=? AND source=?
        """,
        ("symbol", "statement_type", "report_period", "item_code", "source"),
    ),
    "indicator": (
        """
        SELECT 1 FROM raw_fund_indicator
        WHERE symbol=? AND report_period=? AND indicator_code=? AND source=?
        """,
        ("symbol", "report_period", "indicator_code", "source"),
    ),
    "consensus": (
        """
        SELECT 1 FROM raw_consensus_estimate
        WHERE symbol=? AND asof_date=? AND metric=? AND period_year=? AND source=? AND version=?
        """,
        ("symbol", "asof_date", "metric", "period_year", "source", "version"),
    ),
    "valuation": (
        "SELECT 1 FROM raw_valuation_1d WHERE symbol=? AND trade_date=? AND source=?",
        ("symbol", "trade_date", "source"),
    ),
    "holder": (
        "SELECT 1 FROM raw_holder_count WHERE symbol=? AND asof_date=? AND source=?",
        ("symbol", "asof_date", "source"),
    ),
}


class FundamentalRepository:
    def upsert_bundle(self, batch_id: str, bundle: FetchBundle) -> UpsertStats:
        if not bundle.rows:
            return UpsertStats()
        sql, value_keys = _UPSERT_SQL[bundle.kind]
        exist_sql, exist_keys = _EXIST_SQL[bundle.kind]
        with get_conn() as conn:
            stats = upsert_rows(
                conn,
                sql=sql,
                value_keys=value_keys,
                rows=bundle.rows,
                batch_id=batch_id,
                ingested_at=utc_now_iso(),
                exist_sql=exist_sql,
                exist_keys=exist_keys,
                log_label=bundle.kind,
            )
        return UpsertStats(inserted=stats.inserted, updated=stats.updated)

    def counts(self) -> dict[str, int]:
        tables = [
            "raw_fund_statement",
            "raw_fund_indicator",
            "raw_consensus_estimate",
            "raw_valuation_1d",
            "raw_holder_count",
        ]
        out: dict[str, int] = {}
        with get_conn() as conn:
            for t in tables:
                out[t] = int(
                    conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
                )
        return out
