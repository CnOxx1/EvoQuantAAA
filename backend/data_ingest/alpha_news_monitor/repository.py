from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from data_ingest.alpha_announcement.timeutil import utc_now_iso
from data_ingest.alpha_news_monitor.dedupe import title_hash
from data_ingest.alpha_news_monitor.models import NewsRecord, UpsertStats
from shared.bulk_upsert import upsert_rows
from shared.db import get_conn


def lookback_watermark(watermark: str | None, *, hours: int = 24) -> str | None:
    """水位回看：since = watermark - hours（解析失败则原样返回）。"""
    if not watermark:
        return None
    raw = watermark.strip()
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (dt - timedelta(hours=hours)).isoformat()
    except ValueError:
        return watermark


class NewsRepository:
    def upsert_many(self, batch_id: str, rows: list[NewsRecord]) -> UpsertStats:
        if not rows:
            return UpsertStats()
        dict_rows = [
            {
                "source_news_id": r.source_news_id,
                "symbol": r.symbol,
                "title": r.title,
                "summary": r.summary,
                "publish_time": r.publish_time,
                "url": r.url,
                "media_source": r.media_source,
                "channel": r.channel,
                "content_type": r.content_type,
                "extra_json": r.extra_json,
                "source": r.source,
            }
            for r in rows
        ]
        sql = """
            INSERT INTO raw_news_media (
                batch_id, source_news_id, symbol, title, summary,
                publish_time, url, media_source, channel, content_type,
                extra_json, source, ingested_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (source_news_id, source) DO UPDATE SET
                batch_id=excluded.batch_id,
                symbol=excluded.symbol,
                title=excluded.title,
                summary=excluded.summary,
                publish_time=excluded.publish_time,
                url=excluded.url,
                media_source=excluded.media_source,
                channel=excluded.channel,
                content_type=excluded.content_type,
                extra_json=excluded.extra_json,
                ingested_at=excluded.ingested_at
        """
        value_keys = (
            "source_news_id",
            "symbol",
            "title",
            "summary",
            "publish_time",
            "url",
            "media_source",
            "channel",
            "content_type",
            "extra_json",
            "source",
        )
        exist_sql = (
            "SELECT 1 FROM raw_news_media WHERE source_news_id=? AND source=?"
        )
        with get_conn() as conn:
            stats = upsert_rows(
                conn,
                sql=sql,
                value_keys=value_keys,
                rows=dict_rows,
                batch_id=batch_id,
                ingested_at=utc_now_iso(),
                exist_sql=exist_sql,
                exist_keys=("source_news_id", "source"),
                log_label="news_media",
            )
        return UpsertStats(inserted=stats.inserted, updated=stats.updated)

    def get_watermark(self, source: str, channel: str, watch_key: str = "") -> str | None:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT watermark FROM ingest_news_watermark
                WHERE source = ? AND channel = ? AND watch_key = ?
                """,
                (source, channel, watch_key),
            ).fetchone()
            return None if row is None else str(row["watermark"])

    def set_watermark(
        self, source: str, channel: str, watermark: str, watch_key: str = ""
    ) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO ingest_news_watermark
                    (source, channel, watch_key, watermark, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (source, channel, watch_key) DO UPDATE SET
                    watermark=excluded.watermark,
                    updated_at=excluded.updated_at
                """,
                (source, channel, watch_key, watermark, utc_now_iso()),
            )

    def count_news(self) -> int:
        with get_conn() as conn:
            return int(
                conn.execute("SELECT COUNT(*) AS n FROM raw_news_media").fetchone()["n"]
            )

    def load_recent_title_keys(self, *, hours: int = 24) -> dict[str, dict[str, Any]]:
        """近窗已入库标题 hash → 元数据（用于去重）。"""
        cutoff = (
            datetime.now(timezone.utc) - timedelta(hours=hours)
        ).replace(microsecond=0).isoformat()
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT title, publish_time, source, source_news_id, ingested_at
                FROM raw_news_media
                WHERE ingested_at>=? OR publish_time>=?
                """,
                (cutoff, cutoff),
            ).fetchall()
        out: dict[str, dict[str, Any]] = {}
        for r in rows:
            h = title_hash(str(r["title"] or ""))
            if not h:
                continue
            prev = out.get(h)
            pub = str(r["publish_time"] or "")
            if prev is None or pub < str(prev.get("publish_time") or ""):
                out[h] = {
                    "publish_time": pub,
                    "source": str(r["source"]),
                    "source_news_id": str(r["source_news_id"]),
                }
        return out

    def load_listing_name_map(self) -> dict[str, str]:
        """简称/名称 → symbol（点时取最新 effective_date）。"""
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT ON (symbol) symbol, name
                FROM raw_security_listing
                WHERE name IS NOT NULL AND name <> ''
                ORDER BY symbol, effective_date DESC
                """
            ).fetchall()
        out: dict[str, str] = {}
        for r in rows:
            name = str(r["name"]).strip()
            if name:
                out[name] = str(r["symbol"])
        return out
