from __future__ import annotations

"""通用批量 UPSERT（无业务编排语义）。"""

import logging
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from shared.db import ConnectionProxy

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 500
DEFAULT_LARGE_THRESHOLD = 500
_LOG_EVERY = 5000


@dataclass
class BulkUpsertStats:
    inserted: int = 0
    updated: int = 0


def upsert_rows(
    conn: ConnectionProxy,
    *,
    sql: str,
    value_keys: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
    batch_id: str,
    ingested_at: str,
    exist_sql: str | None = None,
    exist_keys: Sequence[str] | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    large_threshold: int = DEFAULT_LARGE_THRESHOLD,
    log_label: str | None = None,
) -> BulkUpsertStats:
    """
    幂等写入：
    - 大包（>= large_threshold）：跳过 EXISTS，分块 executemany；统计全部计入 inserted
    - 小包：逐行 EXISTS + UPSERT，区分 inserted/updated
    """
    stats = BulkUpsertStats()
    if not rows:
        return stats
    if chunk_size < 1:
        raise ValueError("chunk_size 必须 >= 1")

    large = len(rows) >= large_threshold
    if large or exist_sql is None or exist_keys is None:
        params_seq = [
            (batch_id, *(row[k] for k in value_keys), ingested_at) for row in rows
        ]
        total = len(params_seq)
        for i in range(0, total, chunk_size):
            part = params_seq[i : i + chunk_size]
            conn.executemany(sql, part)
            done = min(i + len(part), total)
            if log_label and (done % _LOG_EVERY < chunk_size or done == total):
                logger.info(
                    "upsert %s progress %s/%s batch_id=%s",
                    log_label,
                    done,
                    total,
                    batch_id,
                )
        stats.inserted = total
        return stats

    for row in rows:
        existed = conn.execute(
            exist_sql, tuple(row[k] for k in exist_keys)
        ).fetchone()
        conn.execute(sql, (batch_id, *(row[k] for k in value_keys), ingested_at))
        if existed:
            stats.updated += 1
        else:
            stats.inserted += 1
    return stats
