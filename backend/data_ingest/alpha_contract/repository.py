from __future__ import annotations

from shared.timeutil import utc_now_iso
from data_ingest.alpha_contract.models import FetchBundle, UpsertStats
from shared.bulk_upsert import upsert_rows
from shared.db import get_conn

_SQL = """
INSERT INTO raw_major_contract (
    batch_id, symbol, name, announce_date, sign_date, contract_type,
    contract_name, amount, revenue_prev_year, amount_rev_ratio, revenue_latest,
    party_self, party_self_relation, party_other, party_other_relation,
    is_win_bid, source_event_id, source, ingested_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(symbol, announce_date, source_event_id, source) DO UPDATE SET
    batch_id=excluded.batch_id,
    name=excluded.name,
    sign_date=excluded.sign_date,
    contract_type=excluded.contract_type,
    contract_name=excluded.contract_name,
    amount=excluded.amount,
    revenue_prev_year=excluded.revenue_prev_year,
    amount_rev_ratio=excluded.amount_rev_ratio,
    revenue_latest=excluded.revenue_latest,
    party_self=excluded.party_self,
    party_self_relation=excluded.party_self_relation,
    party_other=excluded.party_other,
    party_other_relation=excluded.party_other_relation,
    is_win_bid=excluded.is_win_bid,
    ingested_at=excluded.ingested_at
"""

_KEYS = (
    "symbol",
    "name",
    "announce_date",
    "sign_date",
    "contract_type",
    "contract_name",
    "amount",
    "revenue_prev_year",
    "amount_rev_ratio",
    "revenue_latest",
    "party_self",
    "party_self_relation",
    "party_other",
    "party_other_relation",
    "is_win_bid",
    "source_event_id",
    "source",
)


class ContractRepository:
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
                    "SELECT 1 FROM raw_major_contract "
                    "WHERE symbol=? AND announce_date=? AND source_event_id=? AND source=? LIMIT 1"
                ),
                exist_keys=("symbol", "announce_date", "source_event_id", "source"),
                log_label="major_contract",
            )
        return UpsertStats(inserted=stats.inserted, updated=stats.updated)

    def count(self, *, source: str | None = None, win_bid_only: bool = False) -> int:
        sql = "SELECT COUNT(*) AS n FROM raw_major_contract WHERE 1=1"
        params: list[str | int] = []
        if source:
            sql += " AND source=?"
            params.append(source)
        if win_bid_only:
            sql += " AND is_win_bid=1"
        with get_conn() as conn:
            row = conn.execute(sql, tuple(params)).fetchone()
        return int(row["n"] if row else 0)
