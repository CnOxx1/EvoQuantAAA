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
class ProcessBatchInfo:
    process_batch_id: str
    process_module: str
    process_kind: str
    status: str


class ProcessBatchManager:
    """process_batch 生命周期：create → commit / fail。"""

    def create(
        self,
        *,
        process_kind: str,
        process_module: str = "data_process",
        job_id: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> ProcessBatchInfo:
        process_batch_id = f"pbat_{uuid.uuid4().hex}"
        now = _utcnow()
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO process_batch (
                    process_batch_id, process_module, process_kind, status,
                    job_id, meta_json, created_at
                ) VALUES (?, ?, ?, 'created', ?, ?, ?)
                """,
                (
                    process_batch_id,
                    process_module,
                    process_kind,
                    job_id,
                    json.dumps(meta or {}, ensure_ascii=False),
                    now,
                ),
            )
        return ProcessBatchInfo(
            process_batch_id, process_module, process_kind, "created"
        )

    def commit(self, process_batch_id: str) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE process_batch
                SET status = 'committed', committed_at = ?
                WHERE process_batch_id = ? AND status = 'created'
                """,
                (_utcnow(), process_batch_id),
            )

    def fail(self, process_batch_id: str, error_message: str) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE process_batch
                SET status = 'failed', failed_at = ?, error_message = ?
                WHERE process_batch_id = ?
                """,
                (_utcnow(), error_message[:2000], process_batch_id),
            )
