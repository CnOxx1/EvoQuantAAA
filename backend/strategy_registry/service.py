from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

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
            meta={"retired": [v for v, _ in retire]},
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
