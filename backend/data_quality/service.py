from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from data_quality.models import DqRequest, DqRunResult
from data_quality.repository import DqRepository
from data_quality.rules import run_core_rules

logger = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class DataQualityService:
    def __init__(self, *, repo: DqRepository | None = None) -> None:
        self.repo = repo or DqRepository()

    def run_core(self, request: DqRequest) -> DqRunResult:
        if not (request.start and request.end):
            raise ValueError("CORE DQ 需要 --start 与 --end")

        start = request.start[:10]
        end = request.end[:10]
        indexes = list(request.index_symbols) or ["000300"]
        dq_run_id = f"dq_{uuid.uuid4().hex}"
        now = _utcnow()

        self.repo.create_run(
            dq_run_id=dq_run_id,
            scope="CORE",
            start=start,
            end=end,
            factor_type=request.factor_type,
            job_id=request.job_id,
            meta={
                "symbols": request.symbols,
                "index_symbols": indexes,
            },
            created_at=now,
        )

        try:
            equity = self.repo.load_processed_equity(
                start=start,
                end=end,
                symbols=request.symbols,
                factor_type=request.factor_type,
            )
            index_rows = self.repo.load_processed_index(
                start=start, end=end, index_symbols=indexes
            )
            calendar = self.repo.load_open_calendar_dates(start=start, end=end)
            outcomes = run_core_rules(
                equity_rows=equity,
                index_rows=index_rows,
                calendar_open_dates=calendar or None,
                expected_symbols=request.symbols,
                expected_indexes=indexes,
            )
            checked_at = _utcnow()
            self.repo.write_results(
                dq_run_id=dq_run_id, outcomes=outcomes, checked_at=checked_at
            )

            error_fails = sum(
                1
                for o in outcomes
                if o.severity == "error" and o.status == "fail"
            )
            warn_fails = sum(
                1 for o in outcomes if o.severity == "warn" and o.status == "fail"
            )
            gate_status = "passed" if error_fails == 0 else "failed"
            summary = {
                "error_fails": error_fails,
                "warn_fails": warn_fails,
                "rules": [
                    {
                        "rule_code": o.rule_code,
                        "severity": o.severity,
                        "status": o.status,
                        "message": o.message,
                    }
                    for o in outcomes
                ],
            }
            finished = _utcnow()
            self.repo.finish_run(
                dq_run_id=dq_run_id,
                status=gate_status,
                summary=summary,
                finished_at=finished,
            )
            self.repo.upsert_gate(
                scope="CORE",
                start=start,
                end=end,
                factor_type=request.factor_type,
                status=gate_status,
                dq_run_id=dq_run_id,
                updated_at=finished,
            )
            logger.info(
                "data_quality CORE %s run=%s errors=%s warns=%s",
                gate_status,
                dq_run_id,
                error_fails,
                warn_fails,
            )
            return DqRunResult(
                dq_run_id=dq_run_id,
                scope="CORE",
                status=gate_status,
                start=start,
                end=end,
                factor_type=request.factor_type,
                error_fails=error_fails,
                warn_fails=warn_fails,
                rule_count=len(outcomes),
            )
        except Exception as exc:
            logger.exception("data_quality failed")
            self.repo.finish_run(
                dq_run_id=dq_run_id,
                status="failed",
                summary={"error": str(exc)},
                finished_at=_utcnow(),
            )
            return DqRunResult(
                dq_run_id=dq_run_id,
                scope="CORE",
                status="failed",
                start=start,
                end=end,
                factor_type=request.factor_type,
                message=str(exc),
            )
