from __future__ import annotations

from shared.timeutil import utc_now_iso
from data_ingest.alpha_flow.models import FetchBundle, IngestKind, UpsertStats
from shared.bulk_upsert import upsert_rows
from shared.db import get_conn

_UPSERT_SQL: dict[IngestKind, tuple[str, tuple[str, ...]]] = {
    "northbound": (
        """
        INSERT INTO raw_money_flow (
            batch_id, scope, trade_date, flow_type, net_amount, buy_amount,
            sell_amount, extra_json, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(scope, trade_date, flow_type, source) DO UPDATE SET
            batch_id=excluded.batch_id,
            net_amount=excluded.net_amount,
            buy_amount=excluded.buy_amount,
            sell_amount=excluded.sell_amount,
            extra_json=excluded.extra_json,
            ingested_at=excluded.ingested_at
        """,
        (
            "scope",
            "trade_date",
            "flow_type",
            "net_amount",
            "buy_amount",
            "sell_amount",
            "extra_json",
            "source",
        ),
    ),
    "stock_flow": (
        """
        INSERT INTO raw_money_flow (
            batch_id, scope, trade_date, flow_type, net_amount, buy_amount,
            sell_amount, extra_json, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(scope, trade_date, flow_type, source) DO UPDATE SET
            batch_id=excluded.batch_id,
            net_amount=excluded.net_amount,
            buy_amount=excluded.buy_amount,
            sell_amount=excluded.sell_amount,
            extra_json=excluded.extra_json,
            ingested_at=excluded.ingested_at
        """,
        (
            "scope",
            "trade_date",
            "flow_type",
            "net_amount",
            "buy_amount",
            "sell_amount",
            "extra_json",
            "source",
        ),
    ),
    "margin": (
        """
        INSERT INTO raw_margin (
            batch_id, symbol, trade_date, rzye, rqye, rzmre, rqyl, rzche, rqchl,
            rzrqye, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, trade_date, source) DO UPDATE SET
            batch_id=excluded.batch_id,
            rzye=excluded.rzye, rqye=excluded.rqye, rzmre=excluded.rzmre,
            rqyl=excluded.rqyl, rzche=excluded.rzche, rqchl=excluded.rqchl,
            rzrqye=excluded.rzrqye, ingested_at=excluded.ingested_at
        """,
        (
            "symbol",
            "trade_date",
            "rzye",
            "rqye",
            "rzmre",
            "rqyl",
            "rzche",
            "rqchl",
            "rzrqye",
            "source",
        ),
    ),
    "dragon_tiger": (
        """
        INSERT INTO raw_dragon_tiger (
            batch_id, symbol, trade_date, reason, close, pct_chg, net_amount,
            buy_amount, sell_amount, source_event_id, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, trade_date, source_event_id, source) DO UPDATE SET
            batch_id=excluded.batch_id,
            reason=excluded.reason, close=excluded.close, pct_chg=excluded.pct_chg,
            net_amount=excluded.net_amount, buy_amount=excluded.buy_amount,
            sell_amount=excluded.sell_amount, ingested_at=excluded.ingested_at
        """,
        (
            "symbol",
            "trade_date",
            "reason",
            "close",
            "pct_chg",
            "net_amount",
            "buy_amount",
            "sell_amount",
            "source_event_id",
            "source",
        ),
    ),
    "dragon_tiger_seat": (
        """
        INSERT INTO raw_dragon_tiger_seat (
            batch_id, trade_date, seat_name, seat_code, buy_count, sell_count,
            buy_amount, sell_amount, net_amount, related_stocks,
            source_event_id, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(trade_date, seat_name, source_event_id, source) DO UPDATE SET
            batch_id=excluded.batch_id,
            seat_code=excluded.seat_code,
            buy_count=excluded.buy_count,
            sell_count=excluded.sell_count,
            buy_amount=excluded.buy_amount,
            sell_amount=excluded.sell_amount,
            net_amount=excluded.net_amount,
            related_stocks=excluded.related_stocks,
            ingested_at=excluded.ingested_at
        """,
        (
            "trade_date",
            "seat_name",
            "seat_code",
            "buy_count",
            "sell_count",
            "buy_amount",
            "sell_amount",
            "net_amount",
            "related_stocks",
            "source_event_id",
            "source",
        ),
    ),
    "block_trade": (
        """
        INSERT INTO raw_block_trade (
            batch_id, symbol, trade_date, price, volume, amount, premium_rate,
            buyer, seller, source_event_id, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, trade_date, source_event_id, source) DO UPDATE SET
            batch_id=excluded.batch_id,
            price=excluded.price, volume=excluded.volume, amount=excluded.amount,
            premium_rate=excluded.premium_rate, buyer=excluded.buyer,
            seller=excluded.seller, ingested_at=excluded.ingested_at
        """,
        (
            "symbol",
            "trade_date",
            "price",
            "volume",
            "amount",
            "premium_rate",
            "buyer",
            "seller",
            "source_event_id",
            "source",
        ),
    ),
}

_EXIST_SQL: dict[IngestKind, tuple[str, tuple[str, ...]]] = {
    "northbound": (
        "SELECT 1 FROM raw_money_flow WHERE scope=? AND trade_date=? AND flow_type=? AND source=?",
        ("scope", "trade_date", "flow_type", "source"),
    ),
    "stock_flow": (
        "SELECT 1 FROM raw_money_flow WHERE scope=? AND trade_date=? AND flow_type=? AND source=?",
        ("scope", "trade_date", "flow_type", "source"),
    ),
    "margin": (
        "SELECT 1 FROM raw_margin WHERE symbol=? AND trade_date=? AND source=?",
        ("symbol", "trade_date", "source"),
    ),
    "dragon_tiger": (
        "SELECT 1 FROM raw_dragon_tiger WHERE symbol=? AND trade_date=? AND source_event_id=? AND source=?",
        ("symbol", "trade_date", "source_event_id", "source"),
    ),
    "dragon_tiger_seat": (
        "SELECT 1 FROM raw_dragon_tiger_seat WHERE trade_date=? AND seat_name=? AND source_event_id=? AND source=?",
        ("trade_date", "seat_name", "source_event_id", "source"),
    ),
    "block_trade": (
        "SELECT 1 FROM raw_block_trade WHERE symbol=? AND trade_date=? AND source_event_id=? AND source=?",
        ("symbol", "trade_date", "source_event_id", "source"),
    ),
}


class FlowRepository:
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
            "raw_money_flow",
            "raw_margin",
            "raw_dragon_tiger",
            "raw_dragon_tiger_seat",
            "raw_block_trade",
        ]
        out: dict[str, int] = {}
        with get_conn() as conn:
            for t in tables:
                out[t] = int(
                    conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
                )
        return out
