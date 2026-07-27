from __future__ import annotations

import os


def expected_token() -> str | None:
    """ASHARE_API_TOKEN；未设置则开发机开放（除非 REQUIRE）。"""
    raw = os.getenv("ASHARE_API_TOKEN", "").strip()
    return raw or None


def require_token_configured() -> bool:
    """ASHARE_API_REQUIRE_TOKEN=1/true 时，未配置 token 一律拒绝。"""
    flag = os.getenv("ASHARE_API_REQUIRE_TOKEN", "").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def check_bearer(authorization: str | None) -> tuple[bool, str | None]:
    """
    返回 (allowed, actor_or_error)。
    token 未配置 → 允许，actor=anonymous（开发机）；REQUIRE 开启则拒绝。
    """
    want = expected_token()
    if want is None:
        if require_token_configured():
            return False, "ASHARE_API_TOKEN required (ASHARE_API_REQUIRE_TOKEN=1)"
        return True, "anonymous"
    if not authorization:
        return False, "missing Authorization Bearer token"
    parts = authorization.strip().split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return False, "Authorization 须为 Bearer <token>"
    if parts[1].strip() != want:
        return False, "invalid token"
    return True, "token"
