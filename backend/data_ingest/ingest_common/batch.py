from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from shared.db import get_conn


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class BatchInfo:
    batch_id: str
    ingest_module: str
    ingest_kind: str
    status: str


class BatchManager:
    """ingest_batch 生命周期：create -> commit / fail。未 commit 不得对外就绪。"""

    def create(
        self,
        *,
        ingest_module: str,
        ingest_kind: str,
        lane: str = "ALPHA",
        job_id: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> BatchInfo:
        batch_id = f"bat_{uuid.uuid4().hex}"
        now = _utcnow()
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO ingest_batch (
                    batch_id, ingest_module, ingest_kind, lane, status,
                    job_id, meta_json, created_at
                ) VALUES (?, ?, ?, ?, 'created', ?, ?, ?)
                """,
                (
                    batch_id,
                    ingest_module,
                    ingest_kind,
                    lane,
                    job_id,
                    json.dumps(meta or {}, ensure_ascii=False),
                    now,
                ),
            )
        return BatchInfo(batch_id, ingest_module, ingest_kind, "created")

    def commit(self, batch_id: str) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE ingest_batch
                SET status = 'committed', committed_at = ?
                WHERE batch_id = ? AND status = 'created'
                """,
                (_utcnow(), batch_id),
            )

    def fail(self, batch_id: str, error_message: str) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE ingest_batch
                SET status = 'failed', failed_at = ?, error_message = ?
                WHERE batch_id = ?
                """,
                (_utcnow(), error_message[:2000], batch_id),
            )
