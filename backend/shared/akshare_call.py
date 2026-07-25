from __future__ import annotations

"""Akshare / HTTP 调用统一重试与限速（无业务编排语义）。"""

import logging
import random
import time
from collections import Counter
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

_fail_counts: Counter[str] = Counter()
_success_after_fail: Counter[str] = Counter()


def call_with_retry(
    fn: Callable[[], T],
    *,
    label: str,
    attempts: int = 3,
    pause: float = 0.12,
    backoff: float = 0.6,
    jitter: float = 0.15,
) -> T:
    """
    指数退避 + 抖动重试。同类失败聚合计数，避免 WARNING 刷屏；
    重试成功时仅在曾失败时打一条 INFO。
    """
    if attempts < 1:
        raise ValueError("attempts 必须 >= 1")
    last: Exception | None = None
    for i in range(attempts):
        if pause > 0:
            time.sleep(pause)
        try:
            result = fn()
            if _fail_counts[label] > 0:
                _success_after_fail[label] += 1
                logger.info(
                    "%s 重试成功（此前连续失败 %s 次）",
                    label,
                    _fail_counts[label],
                )
                _fail_counts[label] = 0
            return result
        except Exception as exc:  # noqa: BLE001
            last = exc
            _fail_counts[label] += 1
            n = _fail_counts[label]
            # 同类错误：第 1/3/10… 次打 WARNING，其余 DEBUG
            if n == 1 or n % 3 == 0:
                logger.warning("%s 失败(%s/%s): %s", label, i + 1, attempts, exc)
            else:
                logger.debug("%s 失败(%s/%s): %s", label, i + 1, attempts, exc)
            if i + 1 < attempts:
                delay = backoff * (i + 1) + random.uniform(0, jitter)
                time.sleep(delay)
    assert last is not None
    raise last


def fail_stats() -> dict[str, Any]:
    """可选：接口健康快照。"""
    return {
        "fail_counts": dict(_fail_counts),
        "recovered": dict(_success_after_fail),
    }
