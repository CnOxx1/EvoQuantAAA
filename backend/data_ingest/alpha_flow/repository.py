from __future__ import annotations

from data_ingest.alpha_announcement.timeutil import utc_now_iso
from data_ingest.alpha_flow.models import FetchBundle, IngestKind, UpsertStats
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
    "block_trade": (
        "SELECT 1 FROM raw_block_trade WHERE symbol=? AND trade_date=? AND source_event_id=? AND source=?",
        ("symbol", "trade_date", "source_event_id", "source"),
    ),
}


class FlowRepository:
    def upsert_bundle(self, batch_id: str, bundle: FetchBundle) -> UpsertStats:
        stats = UpsertStats()
        if not bundle.rows:
            return stats
        # northbound/stock_flow share same SQL keying via kind name in map
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
            "raw_money_flow",
            "raw_margin",
            "raw_dragon_tiger",
            "raw_block_trade",
        ]
        out: dict[str, int] = {}
        with get_conn() as conn:
            for t in tables:
                out[t] = int(
                    conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
                )
        return out
