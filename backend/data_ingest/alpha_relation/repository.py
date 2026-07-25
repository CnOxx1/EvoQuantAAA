from __future__ import annotations

from data_ingest.alpha_announcement.timeutil import utc_now_iso
from data_ingest.alpha_relation.models import FetchBundle, UpsertStats
from shared.bulk_upsert import upsert_rows
from shared.db import get_conn

_SQL = """
INSERT INTO raw_stock_relation (
    batch_id, src_symbol, dst_symbol, relation_type, as_of_date, weight,
    board_name, holder_name, holder_type, coop_holder_name, extra_json,
    source_event_id, source, ingested_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(src_symbol, dst_symbol, relation_type, as_of_date, source_event_id, source)
DO UPDATE SET
    batch_id=excluded.batch_id,
    weight=excluded.weight,
    board_name=excluded.board_name,
    holder_name=excluded.holder_name,
    holder_type=excluded.holder_type,
    coop_holder_name=excluded.coop_holder_name,
    extra_json=excluded.extra_json,
    ingested_at=excluded.ingested_at
"""

_KEYS = (
    "src_symbol",
    "dst_symbol",
    "relation_type",
    "as_of_date",
    "weight",
    "board_name",
    "holder_name",
    "holder_type",
    "coop_holder_name",
    "extra_json",
    "source_event_id",
    "source",
)


class RelationRepository:
    def upsert_bundle(self, batch_id: str, bundle: FetchBundle) -> UpsertStats:
        if not bundle.rows:
            return UpsertStats()
        now = utc_now_iso()
        with get_conn() as conn:
            stats = upsert_rows(
                conn,
                sql=_SQL,
                value_keys=_KEYS,
                rows=bundle.rows,
                batch_id=batch_id,
                ingested_at=now,
                exist_sql=(
                    "SELECT 1 FROM raw_stock_relation WHERE src_symbol=? AND dst_symbol=? "
                    "AND relation_type=? AND as_of_date=? AND source_event_id=? AND source=? "
                    "LIMIT 1"
                ),
                exist_keys=(
                    "src_symbol",
                    "dst_symbol",
                    "relation_type",
                    "as_of_date",
                    "source_event_id",
                    "source",
                ),
                log_label="stock_relation",
            )
        return UpsertStats(inserted=stats.inserted, updated=stats.updated)

    def count(self, *, source: str | None = None, relation_type: str | None = None) -> int:
        sql = "SELECT COUNT(*) AS n FROM raw_stock_relation WHERE 1=1"
        params: list[str] = []
        if source:
            sql += " AND source=?"
            params.append(source)
        if relation_type:
            sql += " AND relation_type=?"
            params.append(relation_type)
        with get_conn() as conn:
            row = conn.execute(sql, tuple(params)).fetchone()
        return int(row["n"] if row else 0)
