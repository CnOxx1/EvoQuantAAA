from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from strategy_registry.gates import (
    DEFAULT_GATE_VERSION,
    GATED_STATUSES,
    evaluate_promotion_gates,
    parse_thresholds,
)
from strategy_registry.models import (
    STRATEGY_KINDS,
    PromoteRequest,
    RegisterRequest,
    RegistryResult,
    StrategyRecord,
)
from strategy_registry.repository import StrategyRegistryRepository
from strategy_registry.transitions import validate_transition

logger = logging.getLogger(__name__)

_CODE_RE = re.compile(r"^[A-Za-z0-9_]{2,64}$")


def _gate_version(explicit: str | None) -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    env = (os.environ.get("ASHARE_PROMOTION_GATE_VERSION") or "").strip()
    return env or DEFAULT_GATE_VERSION


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _artifact_hash(kind: str, params: dict[str, Any]) -> str:
    payload = json.dumps(
        {"kind": kind, "params": params}, sort_keys=True, ensure_ascii=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _normalize_factor_top_n_params(params: dict[str, Any]) -> dict[str, Any]:
    factor = str(params.get("factor_code") or "").strip()
    if not factor:
        raise ValueError("FACTOR_TOP_N 需要 params.factor_code")
    top_n = int(params.get("top_n") or 0)
    rebalance_days = int(params.get("rebalance_days") or 0)
    if top_n <= 0:
        raise ValueError("top_n 必须 > 0")
    if rebalance_days <= 0:
        raise ValueError("rebalance_days 必须 > 0")
    universe = str(params.get("universe_code") or "TOP100").strip() or "TOP100"
    factor_type = str(params.get("factor_type") or "qfq").strip() or "qfq"
    return {
        "factor_code": factor,
        "top_n": top_n,
        "rebalance_days": rebalance_days,
        "universe_code": universe,
        "factor_type": factor_type,
    }


class StrategyRegistryService:
    def __init__(self, *, repo: StrategyRegistryRepository | None = None) -> None:
        self.repo = repo or StrategyRegistryRepository()

    def register(self, request: RegisterRequest) -> RegistryResult:
        code = (request.strategy_code or "").strip()
        if not _CODE_RE.match(code):
            return RegistryResult(
                status="invalid",
                message="strategy_code 需匹配 ^[A-Za-z0-9_]{2,64}$",
            )
        if request.strategy_kind not in STRATEGY_KINDS:
            return RegistryResult(
                status="invalid",
                message=f"不支持的 strategy_kind: {request.strategy_kind}",
            )
        try:
            if request.strategy_kind == "FACTOR_TOP_N":
                params = _normalize_factor_top_n_params(request.params)
            else:
                params = dict(request.params)
        except ValueError as exc:
            return RegistryResult(status="invalid", message=str(exc))

        if request.research_run_id and not self.repo.research_exists(
            request.research_run_id
        ):
            return RegistryResult(
                status="failed",
                message=f"research_run 不存在或未 committed: {request.research_run_id}",
            )
        if request.backtest_run_id and not self.repo.backtest_exists(
            request.backtest_run_id
        ):
            return RegistryResult(
                status="failed",
                message=f"backtest_run 不存在或未 committed: {request.backtest_run_id}",
            )

        now = _utcnow()
        version = f"sv_{uuid.uuid4().hex}"
        self.repo.insert_version(
            {
                "strategy_version": version,
                "strategy_code": code,
                "strategy_kind": request.strategy_kind,
                "status": "DRAFT",
                "params": params,
                "research_run_id": request.research_run_id,
                "backtest_run_id": request.backtest_run_id,
                "artifact_hash": _artifact_hash(request.strategy_kind, params),
                "note": request.note,
                "created_at": now,
                "updated_at": now,
                "transition_id": f"st_{uuid.uuid4().hex}",
                "actor": request.actor,
            }
        )
        logger.info("strategy registered version=%s code=%s", version, code)
        return RegistryResult(
            status="ok",
            strategy_version=version,
            strategy_code=code,
            from_status="NONE",
            to_status="DRAFT",
            meta={"params": params},
        )

    def promote(self, request: PromoteRequest) -> RegistryResult:
        rec = self.repo.get(request.strategy_version)
        if not rec:
            return RegistryResult(
                status="failed",
                strategy_version=request.strategy_version,
                message="strategy_version 不存在",
            )
        err = validate_transition(rec.status, request.to_status)
        if err:
            return RegistryResult(
                status="invalid",
                strategy_version=rec.strategy_version,
                strategy_code=rec.strategy_code,
                from_status=rec.status,
                to_status=request.to_status,
                message=err,
            )

        bt_id = request.backtest_run_id or rec.backtest_run_id
        if request.to_status == "BACKTESTED":
            if not bt_id:
                return RegistryResult(
                    status="invalid",
                    strategy_version=rec.strategy_version,
                    strategy_code=rec.strategy_code,
                    from_status=rec.status,
                    to_status=request.to_status,
                    message="晋升 BACKTESTED 需要 --backtest-run",
                )
            if not self.repo.backtest_exists(bt_id):
                return RegistryResult(
                    status="failed",
                    strategy_version=rec.strategy_version,
                    message=f"backtest_run 不存在或未 committed: {bt_id}",
                )

        gate_meta: dict[str, Any] = {}
        if request.to_status in GATED_STATUSES:
            gate_res = self._run_promotion_gates(
                request=request,
                rec=rec,
                bt_id=bt_id,
            )
            if gate_res is not None:
                return gate_res
            # _run_promotion_gates 把通过信息挂到 request 上不便；再读一次最近结果
            gate_meta = {"gates_passed": True}

        retire: list[tuple[str, str]] = []
        if request.to_status == "LIVE":
            live = self.repo.find_live(rec.strategy_code)
            if live and live.strategy_version != rec.strategy_version:
                if not request.retire_previous_live:
                    return RegistryResult(
                        status="failed",
                        strategy_version=rec.strategy_version,
                        strategy_code=rec.strategy_code,
                        message=(
                            f"已有 LIVE {live.strategy_version}；"
                            "加 --retire-previous 或先 retire 旧版"
                        ),
                    )
                retire.append((live.strategy_version, f"st_{uuid.uuid4().hex}"))

        now = _utcnow()
        tid = f"st_{uuid.uuid4().hex}"
        try:
            self.repo.apply_transition(
                strategy_version=rec.strategy_version,
                from_status=rec.status,
                to_status=request.to_status,
                transition_id=tid,
                actor=request.actor,
                reason=request.reason,
                updated_at=now,
                backtest_run_id=bt_id if request.to_status == "BACKTESTED" else None,
                retire_versions=retire,
            )
        except RuntimeError as exc:
            return RegistryResult(
                status="failed",
                strategy_version=rec.strategy_version,
                strategy_code=rec.strategy_code,
                from_status=rec.status,
                to_status=request.to_status,
                message=str(exc),
            )
        logger.info(
            "strategy promote %s: %s → %s",
            rec.strategy_version,
            rec.status,
            request.to_status,
        )
        return RegistryResult(
            status="ok",
            strategy_version=rec.strategy_version,
            strategy_code=rec.strategy_code,
            from_status=rec.status,
            to_status=request.to_status,
            meta={"retired": [v for v, _ in retire], **gate_meta},
        )

    def _run_promotion_gates(
        self,
        *,
        request: PromoteRequest,
        rec: StrategyRecord,
        bt_id: str | None,
    ) -> RegistryResult | None:
        """返回 RegistryResult 表示拦截；None 表示通过（含 skip）。"""
        now = _utcnow()
        gate_ver = _gate_version(request.gate_version)
        params = self.repo.get_gate_params(gate_ver)
        if not params:
            return RegistryResult(
                status="failed",
                strategy_version=rec.strategy_version,
                strategy_code=rec.strategy_code,
                from_status=rec.status,
                to_status=request.to_status,
                message=f"promotion_gate_params 版本不存在: {gate_ver}",
            )

        if request.skip_gates:
            if not (request.reason or "").strip():
                return RegistryResult(
                    status="invalid",
                    strategy_version=rec.strategy_version,
                    strategy_code=rec.strategy_code,
                    from_status=rec.status,
                    to_status=request.to_status,
                    message="--skip-gates 必须提供 --reason",
                )
            self.repo.insert_gate_result(
                {
                    "gate_id": f"pg_{uuid.uuid4().hex}",
                    "strategy_version": rec.strategy_version,
                    "to_status": request.to_status,
                    "gate_version": gate_ver,
                    "passed": True,
                    "skipped": True,
                    "backtest_run_id": bt_id,
                    "research_run_id": rec.research_run_id,
                    "metrics": {"skipped": True},
                    "checks": [
                        {
                            "name": "skip_gates",
                            "ok": True,
                            "actual": True,
                            "threshold": "explicit skip",
                            "message": request.reason,
                        }
                    ],
                    "actor": request.actor,
                    "reason": request.reason,
                    "created_at": now,
                }
            )
            logger.warning(
                "promotion gates skipped version=%s to=%s actor=%s reason=%s",
                rec.strategy_version,
                request.to_status,
                request.actor,
                request.reason,
            )
            return None

        thresholds = parse_thresholds(params.get("thresholds_json"))
        backtest = self.repo.get_backtest_metrics(bt_id) if bt_id else None
        research_meta = None
        research_id = rec.research_run_id
        if research_id:
            st, meta = self.repo.get_research_meta(research_id)
            if st == "committed":
                research_meta = meta
            else:
                research_id = None

        evaluation = evaluate_promotion_gates(
            to_status=request.to_status,
            thresholds_by_status=thresholds,
            gate_version=gate_ver,
            backtest=backtest,
            research_meta=research_meta,
            research_run_id=research_id,
        )
        self.repo.insert_gate_result(
            {
                "gate_id": f"pg_{uuid.uuid4().hex}",
                "strategy_version": rec.strategy_version,
                "to_status": request.to_status,
                "gate_version": gate_ver,
                "passed": evaluation.passed,
                "skipped": False,
                "backtest_run_id": bt_id,
                "research_run_id": research_id,
                "metrics": evaluation.metrics,
                "checks": [c.as_dict() for c in evaluation.checks],
                "actor": request.actor,
                "reason": request.reason,
                "created_at": now,
            }
        )
        if evaluation.passed:
            return None
        return RegistryResult(
            status="failed",
            strategy_version=rec.strategy_version,
            strategy_code=rec.strategy_code,
            from_status=rec.status,
            to_status=request.to_status,
            message=evaluation.message or "质量门未通过",
            meta={
                "gates_passed": False,
                "gate_version": gate_ver,
                "failing": evaluation.failing_names(),
                "metrics": evaluation.metrics,
            },
        )

    def retire(
        self, *, strategy_version: str, reason: str | None = None, actor: str = "cli"
    ) -> RegistryResult:
        return self.promote(
            PromoteRequest(
                strategy_version=strategy_version,
                to_status="RETIRED",
                reason=reason or "retire",
                actor=actor,
            )
        )

    def get(self, strategy_version: str) -> StrategyRecord | None:
        return self.repo.get(strategy_version)

    def list(
        self,
        *,
        status: str | None = None,
        strategy_code: str | None = None,
        limit: int = 50,
    ) -> list[StrategyRecord]:
        return self.repo.list_versions(
            status=status, strategy_code=strategy_code, limit=limit
        )

    def list_runnable(self) -> list[StrategyRecord]:
        return self.repo.list_runnable()
