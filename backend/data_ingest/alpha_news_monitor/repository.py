from __future__ import annotations

from data_ingest.alpha_announcement.timeutil import utc_now_iso
from data_ingest.alpha_news_monitor.models import NewsRecord, UpsertStats
from shared.db import get_conn


class NewsRepository:
    def upsert_many(self, batch_id: str, rows: list[NewsRecord]) -> UpsertStats:
        stats = UpsertStats()
        if not rows:
            return stats
        ingested_at = utc_now_iso()
        with get_conn() as conn:
            for r in rows:
                existed = conn.execute(
                    """
                    SELECT 1 FROM raw_news_media
                    WHERE source_news_id = ? AND source = ?
                    """,
                    (r.source_news_id, r.source),
                ).fetchone()
                conn.execute(
                    """
                    INSERT INTO raw_news_media (
                        batch_id, source_news_id, symbol, title, summary,
                        publish_time, url, media_source, channel, source, ingested_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (source_news_id, source) DO UPDATE SET
                        batch_id=excluded.batch_id,
                        symbol=excluded.symbol,
                        title=excluded.title,
                        summary=excluded.summary,
                        publish_time=excluded.publish_time,
                        url=excluded.url,
                        media_source=excluded.media_source,
                        channel=excluded.channel,
                        ingested_at=excluded.ingested_at
                    """,
                    (
                        batch_id,
                        r.source_news_id,
                        r.symbol,
                        r.title,
                        r.summary,
                        r.publish_time,
                        r.url,
                        r.media_source,
                        r.channel,
                        r.source,
                        ingested_at,
                    ),
                )
                if existed:
                    stats.updated += 1
                else:
                    stats.inserted += 1
        return stats

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
