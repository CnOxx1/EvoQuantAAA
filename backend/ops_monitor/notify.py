from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any

from shared.db import get_conn

logger = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def collect_failures(
    *,
    since: str,
    job_id: str | None = None,
) -> list[dict[str, Any]]:
    """汇总 since 之后（及可选 job_id）的 failed 批次/DQ。"""
    out: list[dict[str, Any]] = []
    with get_conn() as conn:
        # ingest_batch
        sql_i = """
            SELECT batch_id AS ref_id, ingest_module AS module, ingest_kind AS kind,
                   status, error_message, created_at, job_id
            FROM ingest_batch
            WHERE status='failed' AND created_at>=?
        """
        params_i: list[Any] = [since]
        if job_id:
            sql_i += " AND job_id=?"
            params_i.append(job_id)
        for r in conn.execute(sql_i, tuple(params_i)).fetchall():
            out.append(
                {
                    "source": "ingest_batch",
                    "ref_id": str(r["ref_id"]),
                    "severity": "error",
                    "message": f"ingest failed {r['module']}/{r['kind']}: {r['error_message'] or ''}",
                    "detail": dict(r),
                }
            )

        sql_p = """
            SELECT process_batch_id AS ref_id, process_kind AS kind,
                   status, error_message, created_at, job_id
            FROM process_batch
            WHERE status='failed' AND created_at>=?
        """
        params_p: list[Any] = [since]
        if job_id:
            sql_p += " AND job_id=?"
            params_p.append(job_id)
        for r in conn.execute(sql_p, tuple(params_p)).fetchall():
            out.append(
                {
                    "source": "process_batch",
                    "ref_id": str(r["ref_id"]),
                    "severity": "error",
                    "message": f"process failed {r['kind']}: {r['error_message'] or ''}",
                    "detail": dict(r),
                }
            )

        sql_d = """
            SELECT dq_run_id AS ref_id, scope, status, summary_json, created_at, job_id
            FROM dq_run
            WHERE status='failed' AND created_at>=?
        """
        params_d: list[Any] = [since]
        if job_id:
            sql_d += " AND job_id=?"
            params_d.append(job_id)
        for r in conn.execute(sql_d, tuple(params_d)).fetchall():
            out.append(
                {
                    "source": "dq_run",
                    "ref_id": str(r["ref_id"]),
                    "severity": "error",
                    "message": f"dq failed scope={r['scope']}",
                    "detail": dict(r),
                }
            )
    return out


def write_alerts(
    failures: list[dict[str, Any]],
    *,
    job_id: str | None,
) -> list[str]:
    ids: list[str] = []
    if not failures:
        return ids
    created = _utcnow()
    with get_conn() as conn:
        for f in failures:
            aid = f"al_{uuid.uuid4().hex}"
            conn.execute(
                """
                INSERT INTO ops_alert (
                    alert_id, job_id, severity, source, ref_id,
                    message, detail_json, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?)
                """,
                (
                    aid,
                    job_id,
                    f.get("severity") or "error",
                    f.get("source") or "unknown",
                    f.get("ref_id"),
                    str(f.get("message") or "failure"),
                    json.dumps(f.get("detail") or {}, ensure_ascii=False, default=str),
                    created,
                ),
            )
            ids.append(aid)
    return ids


def post_webhook(payload: dict[str, Any]) -> bool:
    url = (os.environ.get("ASHARE_ALERT_WEBHOOK") or "").strip()
    if not url:
        return False
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            logger.info("alert webhook status=%s", getattr(resp, "status", "?"))
        return True
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.warning("alert webhook failed: %s", exc)
        return False


def notify_round(
    *,
    job_id: str,
    as_of: str,
    since: str,
) -> dict[str, Any]:
    failures = collect_failures(since=since, job_id=job_id)
    alert_ids = write_alerts(failures, job_id=job_id)
    summary = {
        "job_id": job_id,
        "as_of": as_of,
        "failure_count": len(failures),
        "alert_ids": alert_ids,
        "failures": [
            {"source": f["source"], "ref_id": f.get("ref_id"), "message": f["message"]}
            for f in failures
        ],
    }
    lines = [
        "=" * 60,
        f"OPS ALERT SUMMARY job={job_id} as_of={as_of}",
        f"failures={len(failures)} alerts_written={len(alert_ids)}",
    ]
    for f in failures[:20]:
        lines.append(f"  - [{f['source']}] {f['ref_id']}: {f['message']}")
    if not failures:
        lines.append("  (no failures)")
    lines.append("=" * 60)
    text = "\n".join(lines)
    print(text)
    webhook_sent = post_webhook({"text": text, **summary})
    summary["webhook_sent"] = webhook_sent
    return summary
