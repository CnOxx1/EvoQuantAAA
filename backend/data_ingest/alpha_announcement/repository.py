from __future__ import annotations

from dataclasses import dataclass

from data_ingest.alpha_announcement.models import AnnouncementRecord
from shared.timeutil import utc_now_iso
from shared.db import get_conn


@dataclass
class UpsertStats:
    inserted: int = 0
    updated: int = 0


class AnnouncementRepository:
    def upsert_many(self, batch_id: str, rows: list[AnnouncementRecord]) -> UpsertStats:
        stats = UpsertStats()
        if not rows:
            return stats
        ingested_at = utc_now_iso()
        with get_conn() as conn:
            for r in rows:
                existed = conn.execute(
                    """
                    SELECT 1 FROM raw_announcement
                    WHERE source_ann_id = ? AND source = ?
                    """,
                    (r.source_ann_id, r.source),
                ).fetchone()
                conn.execute(
                    """
                    INSERT INTO raw_announcement (
                        batch_id, source_ann_id, symbol, title, publish_time,
                        category_raw, category_norm, url, content_uri, content_hash,
                        channel, source, ingested_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_ann_id, source) DO UPDATE SET
                        batch_id=excluded.batch_id,
                        symbol=excluded.symbol,
                        title=excluded.title,
                        publish_time=excluded.publish_time,
                        category_raw=excluded.category_raw,
                        category_norm=COALESCE(excluded.category_norm, raw_announcement.category_norm),
                        url=excluded.url,
                        content_uri=COALESCE(excluded.content_uri, raw_announcement.content_uri),
                        content_hash=COALESCE(excluded.content_hash, raw_announcement.content_hash),
                        channel=excluded.channel,
                        ingested_at=excluded.ingested_at
                    """,
                    (
                        batch_id,
                        r.source_ann_id,
                        r.symbol,
                        r.title,
                        r.publish_time,
                        r.category_raw,
                        r.category_norm,
                        r.url,
                        r.content_uri,
                        r.content_hash,
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
                SELECT watermark FROM ingest_announcement_watermark
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
                INSERT INTO ingest_announcement_watermark
                    (source, channel, watch_key, watermark, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source, channel, watch_key) DO UPDATE SET
                    watermark=excluded.watermark,
                    updated_at=excluded.updated_at
                """,
                (source, channel, watch_key, watermark, utc_now_iso()),
            )

    def count_announcements(self) -> int:
        with get_conn() as conn:
            return int(conn.execute("SELECT COUNT(*) AS n FROM raw_announcement").fetchone()["n"])
