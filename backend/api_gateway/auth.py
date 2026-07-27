from __future__ import annotations

import os


def expected_token() -> str | None:
    """ASHARE_API_TOKEN；未设置则开发机开放（无鉴权）。"""
    raw = os.getenv("ASHARE_API_TOKEN", "").strip()
    return raw or None


def check_bearer(authorization: str | None) -> tuple[bool, str | None]:
    """
    返回 (allowed, actor_or_error)。
    token 未配置 → 允许，actor=anonymous。
    """
    want = expected_token()
    if want is None:
        return True, "anonymous"
    if not authorization:
        return False, "missing Authorization Bearer token"
    parts = authorization.strip().split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return False, "Authorization 须为 Bearer <token>"
    if parts[1].strip() != want:
        return False, "invalid token"
    return True, "token"
