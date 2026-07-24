from __future__ import annotations

from data_ingest.alpha_announcement.timeutil import utc_now_iso
from data_ingest.alpha_fundamental.models import FetchBundle, IngestKind, UpsertStats
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
}


class FundamentalRepository:
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
                conn.execute(sql, (batch_id, *(row[k] for k in value_keys), ingested_at))
                if existed:
                    stats.updated += 1
                else:
                    stats.inserted += 1
        return stats

    def counts(self) -> dict[str, int]:
        tables = [
            "raw_fund_statement",
            "raw_fund_indicator",
            "raw_consensus_estimate",
        ]
        out: dict[str, int] = {}
        with get_conn() as conn:
            for t in tables:
                out[t] = int(
                    conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
                )
        return out
