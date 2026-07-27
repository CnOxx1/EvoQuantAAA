from __future__ import annotations

from shared.timeutil import utc_now_iso
from data_ingest.core_market.models import FetchBundle, IngestKind, UpsertStats
from shared.bulk_upsert import upsert_rows
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
    "market_rank": (
        """
        INSERT INTO raw_market_rank_1d (
            batch_id, trade_date, rank_type, rank_no, symbol, name,
            metric_value, close, pct_chg, volume, amount, turnover,
            extra_json, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(trade_date, rank_type, symbol, source) DO UPDATE SET
            batch_id=excluded.batch_id,
            rank_no=excluded.rank_no,
            name=excluded.name,
            metric_value=excluded.metric_value,
            close=excluded.close,
            pct_chg=excluded.pct_chg,
            volume=excluded.volume,
            amount=excluded.amount,
            turnover=excluded.turnover,
            extra_json=excluded.extra_json,
            ingested_at=excluded.ingested_at
        """,
        (
            "trade_date",
            "rank_type",
            "rank_no",
            "symbol",
            "name",
            "metric_value",
            "close",
            "pct_chg",
            "volume",
            "amount",
            "turnover",
            "extra_json",
            "source",
        ),
    ),
    "abnormal_move": (
        """
        INSERT INTO raw_abnormal_move (
            batch_id, trade_date, event_time, symbol, name, change_type,
            related_info, extra_json, source_event_id, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(trade_date, change_type, symbol, source_event_id, source) DO UPDATE SET
            batch_id=excluded.batch_id,
            event_time=excluded.event_time,
            name=excluded.name,
            related_info=excluded.related_info,
            extra_json=excluded.extra_json,
            ingested_at=excluded.ingested_at
        """,
        (
            "trade_date",
            "event_time",
            "symbol",
            "name",
            "change_type",
            "related_info",
            "extra_json",
            "source_event_id",
            "source",
        ),
    ),
    "board_1d": (
        """
        INSERT INTO raw_board_bar_1d (
            batch_id, board_type, board_code, board_name, trade_date,
            open, high, low, close, volume, amount, pct_chg, turnover,
            source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(board_type, board_name, trade_date, source) DO UPDATE SET
            batch_id=excluded.batch_id,
            board_code=excluded.board_code,
            open=excluded.open, high=excluded.high, low=excluded.low,
            close=excluded.close, volume=excluded.volume, amount=excluded.amount,
            pct_chg=excluded.pct_chg, turnover=excluded.turnover,
            ingested_at=excluded.ingested_at
        """,
        (
            "board_type",
            "board_code",
            "board_name",
            "trade_date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
            "pct_chg",
            "turnover",
            "source",
        ),
    ),
    "equity_15m": (
        """
        INSERT INTO raw_equity_bar_min (
            batch_id, symbol, bar_time, freq, open, high, low, close,
            volume, amount, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, bar_time, freq, source) DO UPDATE SET
            batch_id=excluded.batch_id,
            open=excluded.open, high=excluded.high, low=excluded.low,
            close=excluded.close, volume=excluded.volume, amount=excluded.amount,
            ingested_at=excluded.ingested_at
        """,
        (
            "symbol",
            "bar_time",
            "freq",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
            "source",
        ),
    ),
    "equity_60m": (
        """
        INSERT INTO raw_equity_bar_min (
            batch_id, symbol, bar_time, freq, open, high, low, close,
            volume, amount, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, bar_time, freq, source) DO UPDATE SET
            batch_id=excluded.batch_id,
            open=excluded.open, high=excluded.high, low=excluded.low,
            close=excluded.close, volume=excluded.volume, amount=excluded.amount,
            ingested_at=excluded.ingested_at
        """,
        (
            "symbol",
            "bar_time",
            "freq",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
            "source",
        ),
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
    "market_rank": (
        "SELECT 1 FROM raw_market_rank_1d WHERE trade_date=? AND rank_type=? AND symbol=? AND source=?",
        ("trade_date", "rank_type", "symbol", "source"),
    ),
    "abnormal_move": (
        "SELECT 1 FROM raw_abnormal_move WHERE trade_date=? AND change_type=? AND symbol=? AND source_event_id=? AND source=?",
        ("trade_date", "change_type", "symbol", "source_event_id", "source"),
    ),
    "board_1d": (
        "SELECT 1 FROM raw_board_bar_1d WHERE board_type=? AND board_name=? AND trade_date=? AND source=?",
        ("board_type", "board_name", "trade_date", "source"),
    ),
    "equity_15m": (
        "SELECT 1 FROM raw_equity_bar_min WHERE symbol=? AND bar_time=? AND freq=? AND source=?",
        ("symbol", "bar_time", "freq", "source"),
    ),
    "equity_60m": (
        "SELECT 1 FROM raw_equity_bar_min WHERE symbol=? AND bar_time=? AND freq=? AND source=?",
        ("symbol", "bar_time", "freq", "source"),
    ),
}


class CoreMarketRepository:
    def upsert_bundle(self, batch_id: str, bundle: FetchBundle) -> UpsertStats:
        """幂等写入：大包分块 executemany，小包保留 EXISTS 统计。"""
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
            "raw_equity_bar_1d",
            "raw_adj_factor",
            "raw_suspend",
            "raw_limit_board",
            "raw_index_bar_1d",
            "raw_corp_action",
            "raw_market_rank_1d",
            "raw_abnormal_move",
            "raw_board_bar_1d",
            "raw_equity_bar_min",
        ]
        out: dict[str, int] = {}
        with get_conn() as conn:
            for t in tables:
                out[t] = int(
                    conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
                )
        return out
