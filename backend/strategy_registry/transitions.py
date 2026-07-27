from __future__ import annotations

from strategy_registry.models import ALLOWED_TRANSITIONS, StrategyStatus


def can_transition(from_status: str, to_status: str) -> bool:
    return (from_status, to_status) in ALLOWED_TRANSITIONS


def validate_transition(
    from_status: str, to_status: StrategyStatus
) -> str | None:
    """返回错误信息；合法则 None。"""
    if from_status == to_status:
        return f"已是 {to_status}，无需迁移"
    if from_status == "RETIRED":
        return "RETIRED 为终态，不可再晋升"
    if not can_transition(from_status, to_status):
        return f"不允许 {from_status} → {to_status}"
    return None
